"""
analytics/utils.py
==================
Core snapshot builder. Called by:
  - analytics.signals  (automatic, on Vacancy save)
  - analytics views    (manual refresh button)

Never import this at module level in signals.py — import inside the function
to avoid circular imports during Django startup.
"""

import logging
from collections import Counter
from decimal import Decimal

from django.db.models import Avg, Max, Min, StdDev
from django.utils import timezone

logger = logging.getLogger(__name__)


# ── Education level rank map ───────────────────────────────────────────────────
# Used to find the highest qualification per applicant from snapshot_academic
EDU_RANK = {
    'kcpe': 1,
    'kenya certificate of primary education (kcpe)': 1,
    'kcse': 2,
    'kenya certificate of secondary education (kcse)': 2,
    'o-levels': 2, 'o levels': 2, 'igcse': 2,
    'a-levels': 3, 'a levels': 3,
    'certificate': 4,
    'diploma': 5,
    'higher national diploma': 6, 'hnd': 6,
    "bachelor's degree": 7, 'bachelors degree': 7, 'degree': 7,
    'postgraduate diploma': 8,
    "master's degree": 9, 'masters degree': 9, 'msc': 9, 'mba': 9,
    'phd': 10, 'doctorate': 10,
    'other foreign qualification': 11,
}


def _rate(numerator, denominator):
    """Safe percentage calculation."""
    if not denominator:
        return Decimal('0')
    return round(Decimal(numerator) / Decimal(denominator) * 100, 2)


def _stage_days(vacancy, from_code, to_code):
    """
    Days between first appearance of from_code and first appearance of to_code
    in the status log for this vacancy. Returns None if either entry is missing.
    """
    from recruitment.models import JobApplicationStatusLog

    from_entry = (
        JobApplicationStatusLog.objects
        .filter(application__vacancy=vacancy, to_status__code=from_code)
        .order_by('changed_at')
        .values('changed_at')
        .first()
    )
    to_entry = (
        JobApplicationStatusLog.objects
        .filter(application__vacancy=vacancy, to_status__code=to_code)
        .order_by('changed_at')
        .values('changed_at')
        .first()
    )
    if from_entry and to_entry:
        delta = to_entry['changed_at'] - from_entry['changed_at']
        return max(delta.days, 0)
    return None


def _highest_edu_label(academic_list):
    """Return the label of the highest education level in a snapshot_academic list."""
    if not academic_list:
        return None
    best_rank  = -1
    best_label = None
    for entry in academic_list:
        label = (entry.get('education_level') or '').strip()
        rank  = EDU_RANK.get(label.lower(), 0)
        if rank > best_rank:
            best_rank  = rank
            best_label = label
    return best_label


def build_snapshot(vacancy):
    """
    Build or replace the VacancyAnalyticsSnapshot for a single vacancy.

    Safe to call multiple times — uses update_or_create so it always
    replaces rather than accumulates.

    Returns the snapshot instance.
    """
    from recruitment.models import (
        JobApplication,
        JobApplicationStatusLog,
        InterviewResult,
        InterviewLog,
        ShortlistingCommittee,
        ShortlistLog,
    )
    from analytics.models import VacancyAnalyticsSnapshot

    # ── 1. Stage counts ───────────────────────────────────────────────────────
    apps = JobApplication.objects.filter(vacancy=vacancy).select_related('status')

    def _count(code):
        return apps.filter(status__code=code).count()

    total          = apps.count()
    longlisted     = _count('longlisted')
    final_ll       = _count('final_longlisted')
    shortlisted    = _count('shortlisted')
    interviewed    = _count('interviewed')
    top_candidate  = _count('top_candidate')
    appointed      = _count('appointed')
    not_selected   = _count('not_selected')

    # ── 2. Funnel rates ───────────────────────────────────────────────────────
    longlist_rate    = _rate(longlisted,    total)
    shortlist_rate   = _rate(shortlisted,   longlisted)
    interview_rate   = _rate(interviewed,   shortlisted)
    appointment_rate = _rate(appointed,     interviewed)

    # ── 3. Cycle times ────────────────────────────────────────────────────────
    days_open = (
        (vacancy.end_date - vacancy.start_date).days
        if vacancy.start_date and vacancy.end_date
        else None
    )
    days_longlisting  = _stage_days(vacancy, 'longlisted',      'final_longlisted')
    days_shortlisting = _stage_days(vacancy, 'final_longlisted', 'shortlisted')
    days_interviews   = _stage_days(vacancy, 'shortlisted',      'interviewed')

    # Total: first submitted → appointed
    first_submitted = (
        JobApplicationStatusLog.objects
        .filter(application__vacancy=vacancy, to_status__code='submitted')
        .order_by('changed_at')
        .values('changed_at')
        .first()
    )
    appointed_entry = (
        JobApplicationStatusLog.objects
        .filter(application__vacancy=vacancy, to_status__code='appointed')
        .order_by('changed_at')
        .values('changed_at')
        .first()
    )
    days_total = None
    if first_submitted and appointed_entry:
        delta = appointed_entry['changed_at'] - first_submitted['changed_at']
        days_total = max(delta.days, 0)

    # ── 4. Interview scoring ──────────────────────────────────────────────────
    results_qs  = InterviewResult.objects.filter(vacancy=vacancy)
    score_agg   = results_qs.aggregate(
        avg=Avg('total_score'),
        mx=Max('total_score'),
        mn=Min('total_score'),
        std=StdDev('total_score'),
    )

    # CEO selected rank — check ceo_selected or appointed
    ceo_app = (
        apps.filter(status__code='ceo_selected').first() or
        apps.filter(status__code='appointed').first()
    )
    ceo_selected_rank   = None
    ceo_override_flag   = False

    if ceo_app:
        try:
            result = InterviewResult.objects.get(vacancy=vacancy, application=ceo_app)
            ceo_selected_rank = result.rank
        except InterviewResult.DoesNotExist:
            pass

        ceo_override_flag = InterviewLog.objects.filter(
            vacancy=vacancy,
            action='ceo_selection_made',
            metadata__is_override=True,
        ).exists()

    # ── 5. Committee ──────────────────────────────────────────────────────────
    committee_size      = ShortlistingCommittee.objects.filter(
        vacancy=vacancy, is_active=True
    ).count()
    committee_coi_count = ShortlistingCommittee.objects.filter(
        vacancy=vacancy, has_conflict=True
    ).count()
    shortlist_overrides = ShortlistLog.objects.filter(
        vacancy=vacancy, action='override_approved'
    ).count()

    # ── 6. Demographics from snapshot_basic (frozen at submission time) ───────
    gender_counter = Counter()
    county_counter = Counter()
    edu_counter    = Counter()
    pwd_count      = 0

    # Single queryset — only fetch the JSON fields we need
    for app in apps.only('snapshot_basic', 'snapshot_academic'):
        b = app.snapshot_basic or {}

        gender = (b.get('gender') or 'Unknown').strip() or 'Unknown'
        gender_counter[gender] += 1

        county = (b.get('home_county') or 'Unknown').strip() or 'Unknown'
        county_counter[county] += 1

        disability = (b.get('disability_status') or '').lower()
        if disability and disability not in ('', 'none', 'no', 'false'):
            pwd_count += 1

        highest = _highest_edu_label(app.snapshot_academic or [])
        if highest:
            edu_counter[highest] += 1

    # ── 7. Write snapshot ─────────────────────────────────────────────────────
    snapshot, _ = VacancyAnalyticsSnapshot.objects.update_or_create(
        vacancy=vacancy,
        defaults={
            'snapped_at':              timezone.now(),
            # Stage counts
            'total_apps':              total,
            'longlisted':              longlisted,
            'final_longlisted':        final_ll,
            'shortlisted':             shortlisted,
            'interviewed':             interviewed,
            'top_candidate':           top_candidate,
            'appointed':               appointed,
            'not_selected':            not_selected,
            # Rates
            'longlist_rate':           longlist_rate,
            'shortlist_rate':          shortlist_rate,
            'interview_rate':          interview_rate,
            'appointment_rate':        appointment_rate,
            # Cycle times
            'days_open':               days_open,
            'days_longlisting':        days_longlisting,
            'days_shortlisting':       days_shortlisting,
            'days_interviews':         days_interviews,
            'days_total':              days_total,
            # Scoring
            'avg_interview_score':     score_agg['avg'],
            'max_interview_score':     score_agg['mx'],
            'min_interview_score':     score_agg['mn'],
            'score_std_dev':           score_agg['std'],
            'ceo_selected_rank':       ceo_selected_rank,
            'ceo_override':            ceo_override_flag,
            # Committee
            'committee_size':          committee_size,
            'committee_coi_count':     committee_coi_count,
            'shortlist_override_count':shortlist_overrides,
            # Demographics
            'gender_breakdown':        dict(gender_counter),
            'county_breakdown':        dict(county_counter.most_common(20)),
            'edu_level_breakdown':     dict(edu_counter),
            'pwd_count':               pwd_count,
        },
    )

    logger.debug(
        f"Snapshot built for vacancy {vacancy.reference_number} "
        f"({total} apps, stage={vacancy.status})"
    )
    return snapshot