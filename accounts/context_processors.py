from recruitment.views import _send_html_email
from .models import JobseekerAccount
from recruitment.models import JobApplicationNotification

def logged_in_user(request):
    user_id = request.session.get('user_id')

    user = None
    if user_id:
        user = JobseekerAccount.objects.filter(pk=user_id).first()

    return {
        'logged_user': user
    }

def notifications(request):
    user_id = request.session.get('user_id')
    if not user_id:
        return {'notifications': [], 'unread_notif_count': 0}

    notifs = (
        JobApplicationNotification.objects
        .filter(user_id=user_id)
        .select_related('related_application__vacancy')
        .order_by('-created_at')[:10]   # latest 10 shown in dropdown
    )
    unread = JobApplicationNotification.objects.filter(
        user_id=user_id, is_read=False
    ).count()

    return {
        'notifications':      notifs,
        'unread_notif_count': unread,
    }

"""
recruitment/context_processors.py

Add to TEMPLATES[0]['OPTIONS']['context_processors'] in settings.py:
    'recruitment.context_processors.auto_close_vacancies',

This fires on every request from an authenticated user — HR or applicant.
Cost: one lightweight queryset check per request.
Auto-close and auto-longlist run in a single atomic transaction.
"""

import logging
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)


def auto_close_vacancies(request):
    """
    On every authenticated request:
    1. Find open vacancies past their end_date
    2. Close them AND run screening immediately — one atomic transaction
    3. Log every action to JobApplicationStatusLog

    Safe to run multiple times — vacancy moves to 'longlisting'
    after first run so subsequent checks skip it.
    """
    if not request.user.is_authenticated:
        return {}

    try:
        _process_expired_vacancies()
    except Exception as e:
        # Never crash a page load — log and move on
        logger.error(f"auto_close_vacancies error: {e}", exc_info=True)

    return {}


def _process_expired_vacancies():
    """Find and process all expired open vacancies."""
    # Import here to avoid circular imports at module load time
    from recruitment.models import Vacancy, JobApplication, JobApplicationStatus
    from recruitment.screening import run_screening

    today = timezone.now().date()

    # Only vacancies that are still 'open' and past end_date
    expired = Vacancy.objects.filter(
        status='open',
        end_date__lt=today,
    ).prefetch_related('jobapplication_set__status')

    for vacancy in expired:
        _close_and_screen(vacancy, today)


def _close_and_screen(vacancy, today):
    """
    Atomically:
    1. Close the vacancy (open → closed → longlisting)
    2. Screen all submitted applications
    3. Update application statuses
    4. Log everything
    """
    from recruitment.models import (
        JobApplication, JobApplicationStatus,
        JobApplicationStatusLog, LonglistReviewLog,
    )
    from recruitment.screening import run_screening

    submitted_status   = _get_status('submitted')
    longlisted_status  = _get_status('longlisted')
    rejected_status    = _get_status('not_selected')

    if not all([submitted_status, longlisted_status, rejected_status]):
        logger.error(
            f"Missing JobApplicationStatus codes for vacancy {vacancy.id}. "
            f"Ensure submitted/longlisted/not_selected statuses exist."
        )
        return

    applications = JobApplication.objects.filter(
        vacancy  = vacancy,
        status   = submitted_status,
    ).select_related('user', 'status')

    with transaction.atomic():

        # ── 1. Move vacancy: open → longlisting ──────────────────────
        vacancy.status = 'longlisting'
        vacancy.save(update_fields=['status'])

        logger.info(
            f"Vacancy {vacancy.reference_number} auto-closed and "
            f"moved to longlisting. {applications.count()} applications to screen."
        )

        passed_count   = 0
        rejected_count = 0
        to_notify      = []   # collect rejected apps for post-transaction emails

        for app in applications:
            snapshot = _build_snapshot(app)
            result   = run_screening(
                snapshot         = snapshot,
                criteria         = vacancy.screening_criteria or {},
                submitted_at     = app.submitted_at,
                vacancy_end_date = vacancy.end_date,
            )

            app.screening_passed  = result['passed']
            app.screening_reasons = result['reasons']
            app.screening_flags   = result['flags']
            app.screening_ran_at  = timezone.now()

            if result['passed']:
                app.status = longlisted_status
                passed_count += 1
                new_status_label = 'longlisted'
            else:
                app.status = rejected_status
                rejected_count += 1
                new_status_label = 'not_selected'
                to_notify.append(app)

            app.save(update_fields=[
                'status', 'screening_passed', 'screening_reasons',
                'screening_flags', 'screening_ran_at',
            ])

            # Log to JobApplicationStatusLog
            JobApplicationStatusLog.objects.create(
                application = app,
                from_status = submitted_status,
                to_status   = app.status,
                changed_by  = None,   # system action
                notes       = (
                    f"Auto-screened by system. "
                    f"Result: {new_status_label}. "
                    f"Reasons: {result['reasons']}. "
                    f"Flags: {result['flags']}"
                ),
            )

        # Log vacancy-level screening event
        LonglistReviewLog.objects.create(
            vacancy     = vacancy,
            application = None,
            officer     = None,   # system action
            action      = 'system_screening',
            notes       = (
                f"Auto-screening completed. "
                f"Longlisted: {passed_count}. "
                f"Rejected: {rejected_count}."
            ),
            metadata    = {
                'criteria':        vacancy.screening_criteria,
                'passed_count':    passed_count,
                'rejected_count':  rejected_count,
                'triggered_by':    'auto_close',
                'ran_at':          timezone.now().isoformat(),
            },
        )

    # ── 2. Send regret emails AFTER transaction commits ───────────────
    # Done outside transaction so email failure doesn't roll back DB changes
    for app in to_notify:
        _send_regret_email(app, vacancy)

    logger.info(
        f"Vacancy {vacancy.reference_number}: "
        f"{passed_count} longlisted, {rejected_count} rejected."
    )


def _build_snapshot(app) -> dict:
    """
    Merge all snapshot JSONFields into one flat dict
    for the screening engine.
    """
    return {
        'basic':       app.snapshot_basic        or {},
        'additional':  app.snapshot_additional   or {},
        'academic':    app.snapshot_academic      or [],
        'professional':app.snapshot_professional  or [],
        'work':        app.snapshot_work          or [],
        'memberships': app.snapshot_memberships   or [],
        'referees':    app.snapshot_referees      or [],
        # Flatten common additional fields to top level for engine convenience
        'cv':              (app.snapshot_additional or {}).get('cv'),
        'cover_letter':    (app.snapshot_additional or {}).get('cover_letter'),
        'expected_salary': (app.snapshot_additional or {}).get('expected_salary'),
        'availability':    (app.snapshot_additional or {}).get('availability'),
    }


def _get_status(code: str):
    """Safely fetch a JobApplicationStatus by code."""
    from recruitment.models import JobApplicationStatus
    try:
        return JobApplicationStatus.objects.get(code=code)
    except JobApplicationStatus.DoesNotExist:
        logger.error(f"JobApplicationStatus with code='{code}' not found.")
        return None


def _send_regret_email(app, vacancy):
    try:
        applicant_name = ' '.join(filter(None, [
            (app.snapshot_basic or {}).get('first_name', ''),
            (app.snapshot_basic or {}).get('surname', ''),
        ])) or app.user.email

        subject = f"Application Update — {vacancy.title} ({vacancy.reference_number})"

        message_html = f"""
        <p>Dear <strong>{applicant_name}</strong>,</p>

        <p>Thank you for your interest in the position of 
        <strong>{vacancy.title}</strong> 
        (Ref: <span style="font-family:monospace;">{vacancy.reference_number}</span>) 
        at the Unclaimed Financial Assets Authority (UFAA).</p>

        <p>After careful review of applications received for this position, we regret 
        to inform you that your application was <strong>unsuccessful</strong> at this 
        stage of the recruitment process.</p>

        <p>We appreciate the time you invested in applying and encourage you to continue 
        monitoring our careers portal for future opportunities that match your 
        qualifications and experience.</p>

        <p style="margin-top:24px;">
            <a href="https://careers.ufaa.go.ke" 
               style="background:#1D255B; color:#F9E6A1; padding:10px 22px; 
                      border-radius:5px; text-decoration:none; font-weight:bold;
                      font-size:13px;">
                View Current Vacancies
            </a>
        </p>

        <p style="margin-top:24px; color:#6b7280; font-size:13px;">
            Yours sincerely,<br>
            <strong style="color:#1D255B;">Human Resources &amp; Administration</strong><br>
            Unclaimed Financial Assets Authority (UFAA)
        </p>
        """

        _send_html_email(subject, app.user.email, message_html)

    except Exception as e:
        logger.error(f"Regret email failed for app {app.id}: {e}", exc_info=True)