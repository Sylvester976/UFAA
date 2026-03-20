import json
import logging
import os
import re
from datetime import datetime
from datetime import timedelta
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.mail import EmailMultiAlternatives
from django.db.models import Prefetch
from django.http import FileResponse, Http404
from django.template.loader import render_to_string

from accounts.models import User, JobseekerAccount
from core.decorators import role_required
# from recruitment.utils import check_and_lock_application
from roles.models import Role
from .models import Application, Appointment, CEODecision, Gender, EthnicGroup, InterviewScore, \
 \
    ProfessionalQualification, WorkHistory, \
    AdditionalDetail, ProfessionalBodyMembership, Referee, \
    JobApplicationNotification, VacancyApplicationCounter, CommitteeVote, InterviewPanel, InterviewLog, InterviewResult, \
    InterviewCriterion, InterviewSlot, InterviewSchedule
from .models import County, Constituency, SubCounty, Ward, JobSeekerProfile, AcademicQualification, \
    EducationLevel, DocumentType, Document
from .models import (
    ShortlistingCommittee,
    ShortlistResult,
    ShortlistLog,
)
from .services import aggregate_shortlist, build_profile_snapshot, is_shortlisting_complete

User = get_user_model()
logger = logging.getLogger(__name__)


# ── Helper ───────────────────────────────────────────────────
def get_logged_in_user(request):
    user_id = request.session.get('user_id')
    if not user_id:
        return None
    return JobseekerAccount.objects.filter(id=user_id).first()


def view_jobs(request):
    today = timezone.now().date()

    # Close vacancies whose end date is today
    Vacancy.objects.filter(
        status='open',
        end_date=today
    ).update(status='closed')

    # Only show vacancies that start today or later
    vacancies = Vacancy.objects.filter(
        status='open',
        start_date__gte=today
    ).order_by('start_date')  # earliest starting first

    return render(request, 'Jobseekers/jobs.html', {'vacancies': vacancies})


def instrutions_view(request):
    return render(request, 'Jobseekers/instructions.html')


# ── In recruitment/views.py ───────────────────────────────────
# Add/replace dashboard_view:

def dashboard(request):
    user_id = request.session.get('user_id')
    if not user_id:
        return redirect('index')

    user = JobseekerAccount.objects.filter(pk=user_id).first()
    if not user:
        request.session.flush()
        return redirect('index')

    profile = JobSeekerProfile.objects.filter(user=user).first()
    completion = calculate_profile_completion(user)
    detail = AdditionalDetail.objects.filter(user=user).first()

    academic_count = AcademicQualification.objects.filter(user=user).count()
    professional_count = ProfessionalQualification.objects.filter(user=user).count()
    work_history = WorkHistory.objects.filter(user=user).order_by('-start_year', '-start_month')
    work_count = work_history.count()
    membership_count = ProfessionalBodyMembership.objects.filter(user=user).count()  # ← new
    referee_count = Referee.objects.filter(user=user).count()  # ← new

    # Section completion % — weights now 30/15/10/10/10/15/10
    sections = {
        'Basic Details': min(int(_basic_score(profile) / 30 * 100), 100) if profile else 0,
        'Academic': 100 if academic_count > 0 else 0,
        'Professional': 100 if professional_count > 0 else 0,
        'Work History': 100 if work_count > 0 else 0,
        'Memberships': 100 if membership_count > 0 else 0,  # ← new
        'Referees': 100 if referee_count >= 2 else (50 if referee_count == 1 else 0),  # ← new
        'Additional': _additional_score(detail),
    }

    # Nudge items
    incomplete = []
    if not profile or not profile.first_name:
        incomplete.append({'label': 'Complete your basic details',
                           'url': 'profile', 'icon': 'fa-user'})
    if academic_count == 0:
        incomplete.append({'label': 'Add academic qualifications',
                           'url': 'academic_qualifications', 'icon': 'fa-graduation-cap'})
    if professional_count == 0:
        incomplete.append({'label': 'Add professional qualifications',
                           'url': 'professional_qualifications', 'icon': 'fa-certificate'})
    if work_count == 0:
        incomplete.append({'label': 'Add work history',
                           'url': 'work_history', 'icon': 'fa-briefcase'})
    if membership_count == 0:  # ← new
        incomplete.append({'label': 'Add professional body memberships',
                           'url': 'memberships', 'icon': 'fa-users'})
    if referee_count < 2:  # ← new
        incomplete.append({
            'label': 'Add both referees' if referee_count == 0 else 'Add second referee',
            'url': 'referees', 'icon': 'fa-user-tie'
        })
    if not detail or not detail.cv:
        incomplete.append({'label': 'Upload your CV',
                           'url': 'additional_details', 'icon': 'fa-file-pdf'})

    applications = Application.objects.filter(
        applicant=JobseekerAccount.objects.filter(pk=user_id).first()
    )
    context = {
        'user': user,
        'profile': profile,
        'detail': detail,
        'completion': completion,
        'academic_count': academic_count,
        'professional_count': professional_count,
        'work_count': work_count,
        'work_history': work_history[:5],
        'membership_count': membership_count,  # ← new
        'referee_count': referee_count,  # ← new
        'sections': sections,
        'incomplete': incomplete,
        'has_academic': academic_count > 0,
        'has_professional': professional_count > 0,
        'has_work_history': work_count > 0,
        'has_memberships': membership_count > 0,  # ← new
        'has_referees': referee_count >= 2,  # ← new
        'has_additional': detail is not None,
        'page': 'Dashboard',
        'applications': applications
    }
    return render(request, 'Jobseekers/dashboard.html', context)


def _basic_score(profile):
    """Return the raw basic-details score (0–40)."""
    if not profile:
        return 0
    fields = [
        profile.salutation, profile.surname, profile.first_name,
        profile.date_of_birth, profile.gender_id, profile.ethnic_group_id,
        profile.home_county_id, profile.constituency_id, profile.disability_status,
    ]
    filled = sum(1 for f in fields if f)
    return int((filled / len(fields)) * 40)


def _additional_score(detail):
    if not detail:
        return 0
    score = 0
    if detail.cv:               score += 3
    if detail.cover_letter:     score += 2
    if detail.availability:     score += 2  # was 1 — now mandatory, more weight
    if detail.expected_salary:  score += 2  # was 0 — now mandatory, add points
    if detail.languages:        score += 1
    return min(int(score / 10 * 100), 100)


def get_next_step(user):
    if not hasattr(user, "profile"):
        return "profile"
    if not user.academic_qualifications.exists():
        return "academic_qualifications"
    if not user.professional_qualifications.exists():
        return "professional_qualifications"
    if not user.work_history.exists():
        return "work_history"
    if not hasattr(user, "additional_detail"):
        return "additional_details"
    return "dashboard"


def enforce_step(user, current_step):
    next_required = get_next_step(user)
    if current_step != next_required:
        return redirect(next_required)
    return None


# ── Profile ──────────────────────────────────────────────────
def profile_view(request):
    user_id = request.session.get('user_id')
    if not user_id:
        return redirect('index')

    user = JobseekerAccount.objects.filter(id=user_id).first()
    if not user:
        request.session.flush()
        return redirect('index')

    profile, created = JobSeekerProfile.objects.get_or_create(user=user)
    completion = calculate_profile_completion(user)

    if request.method == 'POST':
        try:
            salutation        = request.POST.get('salutation', '').strip()
            surname           = request.POST.get('surname', '').strip()
            first_name        = request.POST.get('first_name', '').strip()
            second_name       = request.POST.get('second_name', '').strip()
            id_no             = request.POST.get('id_no', '').strip()
            date_of_birth     = request.POST.get('date_of_birth') or None
            gender_id         = request.POST.get('gender') or None
            ethnic_group_id   = request.POST.get('ethnic_group') or None
            home_county_id    = request.POST.get('home_county') or None
            constituency_id   = request.POST.get('constituency') or None
            sub_county_id     = request.POST.get('sub_county') or None
            ward_id           = request.POST.get('ward') or None
            disability_status = request.POST.get('disability_status', '').strip()
            disability_other  = request.POST.get('disability_other', '').strip()
            disability_no     = request.POST.get('disability_no', '').strip()
            is_employee       = request.POST.get('is_employee') == 'true'
            employee_number   = request.POST.get('employee_number', '').strip()

            # ── Phone: strip spaces/dashes, enforce 10–13 chars ──────
            phone_raw    = request.POST.get('phone_number', '').strip()
            phone_number = re.sub(r'[\s\-]', '', phone_raw)

            # ── Validations ───────────────────────────────────────────
            if not first_name:
                return JsonResponse({'status': 'error', 'message': 'First name is required.'})
            if not surname:
                return JsonResponse({'status': 'error', 'message': 'Surname is required.'})
            if not id_no:
                return JsonResponse({'status': 'error', 'message': 'ID number is required.'})
            if not date_of_birth:
                return JsonResponse({'status': 'error', 'message': 'Date of birth is required.'})
            if not phone_number:
                return JsonResponse({'status': 'error', 'message': 'Phone number is required.'})
            if len(phone_number) < 10:
                return JsonResponse({'status': 'error',
                                     'message': 'Phone number is too short. Minimum 10 digits (e.g. 0712345678).'})
            if len(phone_number) > 13:
                return JsonResponse({'status': 'error',
                                     'message': 'Phone number is too long. Maximum 13 characters (e.g. +254712345678).'})
            if is_employee and not employee_number:
                return JsonResponse({'status': 'error',
                                     'message': 'Please enter your UFAA employee number.'})
            if is_employee and employee_number:
                from recruitment.models import UFAAStaffNumber
                if not UFAAStaffNumber.objects.filter(staff_number=employee_number, is_active=True).exists():
                    return JsonResponse({'status': 'error',
                                         'message': (
                                             f'Employee number "{employee_number}" was not found in the '
                                             'UFAA staff register. Please check the number and try again, '
                                             'or contact HR if you believe this is an error.'
                                         )})
            if disability_status == 'Other' and not disability_other:
                return JsonResponse({'status': 'error', 'message': 'Please describe your disability.'})

            # Disability no — clear if no disability
            has_disability = disability_status not in ('', 'None')

            # ── Save profile ──────────────────────────────────────────
            profile.salutation       = salutation
            profile.surname          = surname
            profile.first_name       = first_name
            profile.second_name      = second_name
            profile.email            = user.email
            profile.id_no            = id_no
            profile.date_of_birth    = date_of_birth
            profile.gender_id        = gender_id
            profile.ethnic_group_id  = ethnic_group_id
            profile.home_county_id   = home_county_id
            profile.constituency_id  = constituency_id
            profile.sub_county_id    = sub_county_id
            profile.ward_id          = ward_id
            profile.disability_status = disability_status
            profile.disability_other  = disability_other if disability_status == 'Other' else ''
            profile.disability_no     = disability_no if has_disability else ''
            profile.employee_number   = employee_number if is_employee else ''
            profile.phone_number      = phone_number
            profile.save()

            # Save is_employee on account
            JobseekerAccount.objects.filter(id=user.id).update(is_employee=is_employee)

            return JsonResponse({
                'status':     'success',
                'message':    'Profile saved successfully.',
                'completion': calculate_profile_completion(user),
            })

        except Exception as e:
            return JsonResponse({'status': 'error', 'message': f'Something went wrong: {str(e)}'})

    context = {
        'profile':          profile,
        'user':             user,
        'page':             'Profile',
        'counties':         County.objects.all(),
        'constituencies':   Constituency.objects.all(),
        'sub_counties':     SubCounty.objects.all(),
        'wards':            Ward.objects.all(),
        'genders':          Gender.objects.all(),
        'ethnic_groups':    EthnicGroup.objects.all(),
        'completion':       completion,
        'has_academic':     AcademicQualification.objects.filter(user=user).exists(),
        'has_professional': ProfessionalQualification.objects.filter(user=user).exists(),
        'has_work_history': WorkHistory.objects.filter(user=user).exists(),
        'has_additional':   AdditionalDetail.objects.filter(user=user).exists(),
        'has_memberships':  ProfessionalBodyMembership.objects.filter(user=user).exists(),
        'has_referees':     Referee.objects.filter(user=user).count() >= 2,
    }
    return render(request, 'Jobseekers/profile.html', context)


# ── Academic Qualifications ──────────────────────────────────

def _doc_to_dict(doc):
    """Serialize a Document instance to a JSON-safe dict for the frontend."""
    return {
        'id': doc.id,
        'url': doc.file.url,
        'filename': doc.file.name.split('/')[-1],
        'type_name': doc.document_type.name,
    }


def academic_qualifications_view(request):
    user_id = request.session.get('user_id')
    if not user_id:
        return redirect('index')

    user = JobseekerAccount.objects.filter(id=user_id).first()
    if not user:
        request.session.flush()
        return redirect('index')

    profile = JobSeekerProfile.objects.filter(user=user).first()
    completion = calculate_profile_completion(user)

    if request.method == 'POST':
        action = request.POST.get('action', 'save')

        # ── DELETE ───────────────────────────────────────────
        if action == 'delete':
            try:
                qual_id = request.POST.get('qual_id')
                qual = AcademicQualification.objects.filter(id=qual_id, user=user).first()
                if not qual:
                    return JsonResponse({'status': 'error', 'message': 'Qualification not found.'})
                qual.delete()
                return JsonResponse({'status': 'success', 'message': 'Qualification deleted successfully.'})
            except Exception as e:
                logger.exception("Error while deleting academic qualification for user %s", user_id)
                return JsonResponse({'status': 'error', 'message': 'An error occurred while deleting the qualification.'})

        # ── EDIT ─────────────────────────────────────────────
        if action == 'edit':
            try:
                qual_id = request.POST.get('qual_id')
                qual = AcademicQualification.objects.filter(id=qual_id, user=user).first()
                if not qual:
                    return JsonResponse({'status': 'error', 'message': 'Qualification not found.'})

                level_id = request.POST.get('education_level')
                education_level = EducationLevel.objects.filter(id=level_id).first()
                if not education_level:
                    return JsonResponse({'status': 'error', 'message': 'Invalid education level.'})

                institution = request.POST.get('institution', '').strip()
                year = request.POST.get('year_completed', '').strip()

                if not institution:
                    return JsonResponse({'status': 'error', 'message': 'Institution is required.'})
                if not year:
                    return JsonResponse({'status': 'error', 'message': 'Year completed is required.'})

                qual.education_level = education_level
                qual.institution = institution
                qual.field_of_study = request.POST.get('field_of_study', '').strip()
                qual.year_completed = year
                qual.grade = request.POST.get('grade', '').strip()
                qual.cert_number = request.POST.get('cert_number', '').strip()
                qual.country = request.POST.get('country', 'Kenya').strip() or 'Kenya'
                qual.save()

                files = request.FILES.getlist('edit_files')
                doc_types = request.POST.getlist('edit_doc_types')

                for i, file in enumerate(files):
                    doc_type_id = doc_types[i] if i < len(doc_types) else None
                    doc_type = DocumentType.objects.filter(id=doc_type_id).first()
                    if file and doc_type:
                        Document.objects.create(
                            user=user,
                            profile=profile,
                            document_type=doc_type,
                            file=file,
                            academic_qualification=qual,
                        )

                # Return ALL docs for this qual (existing + newly uploaded)
                all_docs = list(
                    qual.documents.select_related('document_type').order_by('-uploaded_at')
                )

                return JsonResponse({
                    'status': 'success',
                    'message': 'Qualification updated successfully.',
                    'qual': {
                        'id': qual.id,
                        'level_id': education_level.id,
                        'level_name': education_level.name,
                        'institution': qual.institution,
                        'field_of_study': qual.field_of_study or '',
                        'year_completed': qual.year_completed,
                        'grade': qual.grade or '',
                        'cert_number': qual.cert_number or '',
                        'country': qual.country,
                        'doc_count': len(all_docs),
                        'docs': [_doc_to_dict(d) for d in all_docs],
                    }
                })

            except Exception as e:
                logger.exception("Error while editing academic qualification for user %s", user_id)
                return JsonResponse({'status': 'error', 'message': 'An error occurred while updating the qualification.'})

        # ── SAVE NEW ─────────────────────────────────────────
        try:
            qualifications = json.loads(request.POST.get('qualifications', '[]'))

            if not qualifications:
                return JsonResponse({'status': 'error', 'message': 'Please add at least one qualification.'})

            saved = []

            for idx, q in enumerate(qualifications):
                education_level = EducationLevel.objects.filter(id=q.get('education_level')).first()
                if not education_level:
                    continue

                institution = q.get('institution', '').strip()
                year = q.get('year_completed', '')
                if not institution or not year:
                    continue

                qual = AcademicQualification.objects.create(
                    user=user,
                    education_level=education_level,
                    institution=institution,
                    field_of_study=q.get('field_of_study', '').strip(),
                    country=q.get('country', 'Kenya').strip() or 'Kenya',
                    year_completed=year,
                    grade=q.get('grade', '').strip(),
                    cert_number=q.get('cert_number', '').strip(),
                )

                files = request.FILES.getlist(f'level_files_{idx}')
                doc_types = request.POST.getlist(f'level_doc_types_{idx}')
                doc_objs = []

                for i, file in enumerate(files):
                    doc_type_id = doc_types[i] if i < len(doc_types) else None
                    doc_type = DocumentType.objects.filter(id=doc_type_id).first()
                    if file and doc_type:
                        doc = Document.objects.create(
                            user=user,
                            profile=profile,
                            document_type=doc_type,
                            file=file,
                            academic_qualification=qual,
                        )
                        doc_objs.append(doc)

                saved.append({
                    'id': qual.id,
                    'level_id': education_level.id,
                    'level_name': education_level.name,
                    'institution': qual.institution,
                    'field_of_study': qual.field_of_study or '',
                    'year_completed': qual.year_completed,
                    'grade': qual.grade or '',
                    'cert_number': qual.cert_number or '',
                    'country': qual.country,
                    'doc_count': len(doc_objs),
                    'docs': [_doc_to_dict(d) for d in doc_objs],
                })

            if not saved:
                return JsonResponse({
                    'status': 'error',
                    'message': 'No valid qualifications were saved. Check all required fields.'
                })

            return JsonResponse({
                'status': 'success',
                'message': f'{len(saved)} qualification(s) saved successfully.',
                'saved': saved,
            })

        except Exception as e:
            logger.exception("Error while saving academic qualifications for user %s", user_id)
            return JsonResponse({
                'status': 'error',
                'message': 'An error occurred while saving your qualifications. Please try again later.'
            })

    # ── GET ───────────────────────────────────────────────────
    existing_qualifications = (
        AcademicQualification.objects
        .filter(user=user)
        .select_related('education_level')
        .prefetch_related(
            Prefetch(
                'documents',
                queryset=Document.objects.select_related('document_type').order_by('-uploaded_at'),
            )
        )
        .order_by('education_level__rank')
    )

    context = {
        'profile': profile,
        'user': user,
        'page': 'Academic Qualifications',
        'education_levels': EducationLevel.objects.all().order_by('rank'),
        'document_types': DocumentType.objects.all(),
        'existing_qualifications': existing_qualifications,
        'completion': completion,
        'has_academic': existing_qualifications.exists(),
        'has_professional': user.professional_qualifications.exists()
        if hasattr(user, 'professional_qualifications') else False,
        'has_work_history': user.work_history.exists()
        if hasattr(user, 'work_history') else False,
        'has_additional': hasattr(user, 'additional_detail'),
        'has_memberships': ProfessionalBodyMembership.objects.filter(user=user).exists(),
        'has_referees': Referee.objects.filter(user=user).count() >= 2,
    }
    return render(request, 'Jobseekers/academic.html', context)


# ── Progress Calculation ─────────────────────────────────────
def calculate_profile_completion(user):
    score = 0

    # ── Section 1: Basic Details (30 points) ──────────────────
    if hasattr(user, 'profile'):
        profile = user.profile
        fields = [
            profile.salutation,
            profile.surname,
            profile.first_name,
            profile.date_of_birth,
            profile.gender_id,
            profile.ethnic_group_id,
            profile.home_county_id,
            profile.constituency_id,
            profile.disability_status,
            profile.phone_number,  # ← new
        ]
        filled = sum(1 for f in fields if f)
        score += int((filled / len(fields)) * 30)

    # ── Section 2: Academic Qualifications (15 points) ────────
    if AcademicQualification.objects.filter(user=user).exists():
        score += 15

    # ── Section 3: Professional Qualifications (10 points) ────
    if ProfessionalQualification.objects.filter(user=user).exists():
        score += 10

    # ── Section 4: Work History (10 points) ───────────────────
    if WorkHistory.objects.filter(user=user).exists():
        score += 10

    # ── Section 5: Professional Body Memberships (10 points) ──
    if ProfessionalBodyMembership.objects.filter(user=user).exists():
        score += 10

        # ── Section 6: Referees (15 points) ───────────────────────
        referee_count = Referee.objects.filter(user=user).count()
        if referee_count >= 2:
            score += 15  # full 15 only when both are saved
        elif referee_count == 1:
            score += 8  # partial credit for one referee

    # ── Section 7: Additional Details (10 points) ─────────────
    detail = AdditionalDetail.objects.filter(user=user).first()
    if detail:
        if detail.cv:              score += 3
        if detail.cover_letter:    score += 2
        if detail.availability:    score += 2
        if detail.expected_salary: score += 2
        if detail.languages:       score += 1

    return min(int(score), 100)


def professional_qualifications_view(request):
    user_id = request.session.get('user_id')
    if not user_id:
        return redirect('index')

    user = JobseekerAccount.objects.filter(id=user_id).first()
    if not user:
        request.session.flush()
        return redirect('index')

    profile = JobSeekerProfile.objects.filter(user=user).first()
    completion = calculate_profile_completion(user)

    if request.method == 'POST':
        action = request.POST.get('action', 'save')

        # ── DELETE ───────────────────────────────────────────
        if action == 'delete':
            try:
                qual_id = request.POST.get('qual_id')
                qual = ProfessionalQualification.objects.filter(id=qual_id, user=user).first()
                if not qual:
                    return JsonResponse({'status': 'error', 'message': 'Qualification not found.'})
                qual.delete()
                return JsonResponse({'status': 'success', 'message': 'Qualification deleted successfully.'})
            except Exception as e:
                logger.exception("Error deleting professional qualification for user %s", user.id)
                return JsonResponse(
                    {
                        'status': 'error',
                        'message': 'An unexpected error occurred while deleting the qualification. Please try again later.',
                    }
                )

        # ── EDIT ─────────────────────────────────────────────
        if action == 'edit':
            try:
                qual_id = request.POST.get('qual_id')
                qual = ProfessionalQualification.objects.filter(id=qual_id, user=user).first()
                if not qual:
                    return JsonResponse({'status': 'error', 'message': 'Qualification not found.'})

                qualification = request.POST.get('qualification', '').strip()
                awarding_body = request.POST.get('awarding_body', '').strip()
                year_obtained = request.POST.get('year_obtained', '').strip()

                if not qualification:
                    return JsonResponse({'status': 'error', 'message': 'Qualification name is required.'})
                if not awarding_body:
                    return JsonResponse({'status': 'error', 'message': 'Awarding body is required.'})
                if not year_obtained:
                    return JsonResponse({'status': 'error', 'message': 'Year obtained is required.'})

                expiry_raw = request.POST.get('expiry_year', '').strip()

                qual.qualification = qualification
                qual.awarding_body = awarding_body
                qual.year_obtained = year_obtained
                qual.expiry_year = int(expiry_raw) if expiry_raw else None
                qual.grade = request.POST.get('grade', '').strip()
                qual.cert_number = request.POST.get('cert_number', '').strip()
                qual.country = request.POST.get('country', 'Kenya').strip() or 'Kenya'
                qual.save()

                files = request.FILES.getlist('edit_files')
                doc_types = request.POST.getlist('edit_doc_types')

                for i, file in enumerate(files):
                    doc_type_id = doc_types[i] if i < len(doc_types) else None
                    doc_type = DocumentType.objects.filter(id=doc_type_id).first()
                    if file and doc_type:
                        Document.objects.create(
                            user=user,
                            profile=profile,
                            document_type=doc_type,
                            file=file,
                            professional_qualification=qual,
                        )

                # Return ALL docs for this qual (existing + newly uploaded)
                all_docs = list(
                    qual.documents.select_related('document_type').order_by('-uploaded_at')
                )

                return JsonResponse({
                    'status': 'success',
                    'message': 'Qualification updated successfully.',
                    'qual': {
                        'id': qual.id,
                        'qualification': qual.qualification,
                        'awarding_body': qual.awarding_body,
                        'year_obtained': qual.year_obtained,
                        'expiry_year': qual.expiry_year or '',
                        'grade': qual.grade or '',
                        'cert_number': qual.cert_number or '',
                        'country': qual.country,
                        'doc_count': len(all_docs),
                        'docs': [_doc_to_dict(d) for d in all_docs],
                    }
                })

            except Exception as e:
                logger.exception("Error while editing professional qualification")
                return JsonResponse({
                    'status': 'error',
                    'message': 'An unexpected error occurred while updating the qualification. Please try again later.'
                })
                logger.exception("Error updating professional qualification for user %s", user.id)
                return JsonResponse(
                    {
                        'status': 'error',
                        'message': 'An unexpected error occurred while saving the qualification. Please try again later.',
                    }
                )

        # ── SAVE NEW ─────────────────────────────────────────
        try:
            qualifications = json.loads(request.POST.get('qualifications', '[]'))

            if not qualifications:
                return JsonResponse({'status': 'error', 'message': 'Please add at least one qualification.'})

            saved = []

            for idx, q in enumerate(qualifications):
                qualification = q.get('qualification', '').strip()
                awarding_body = q.get('awarding_body', '').strip()
                year_obtained = q.get('year_obtained', '')
                expiry_raw = q.get('expiry_year', '')

                if not qualification or not awarding_body or not year_obtained:
                    continue

                qual = ProfessionalQualification.objects.create(
                    user=user,
                    qualification=qualification,
                    awarding_body=awarding_body,
                    year_obtained=year_obtained,
                    expiry_year=int(expiry_raw) if expiry_raw else None,
                    grade=q.get('grade', '').strip(),
                    cert_number=q.get('cert_number', '').strip(),
                    country=q.get('country', 'Kenya').strip() or 'Kenya',
                )

                files = request.FILES.getlist(f'qual_files_{idx}')
                doc_types = request.POST.getlist(f'qual_doc_types_{idx}')
                doc_objs = []

                for i, file in enumerate(files):
                    doc_type_id = doc_types[i] if i < len(doc_types) else None
                    doc_type = DocumentType.objects.filter(id=doc_type_id).first()
                    if file and doc_type:
                        doc = Document.objects.create(
                            user=user,
                            profile=profile,
                            document_type=doc_type,
                            file=file,
                            professional_qualification=qual,
                        )
                        doc_objs.append(doc)

                saved.append({
                    'id': qual.id,
                    'qualification': qual.qualification,
                    'awarding_body': qual.awarding_body,
                    'year_obtained': qual.year_obtained,
                    'expiry_year': qual.expiry_year or '',
                    'grade': qual.grade or '',
                    'cert_number': qual.cert_number or '',
                    'country': qual.country,
                    'doc_count': len(doc_objs),
                    'docs': [_doc_to_dict(d) for d in doc_objs],
                })

            if not saved:
                return JsonResponse({
                    'status': 'error',
                    'message': 'No valid qualifications saved. Check all required fields.'
                })

            return JsonResponse({
                'status': 'success',
                'message': f'{len(saved)} qualification(s) saved successfully.',
                'saved': saved,
            })

        except Exception as e:
            logger.exception("Error saving professional qualifications for user %s", user.id)
            return JsonResponse(
                {
                    'status': 'error',
                    'message': 'An unexpected error occurred while saving the qualifications. Please try again later.',
                }
            )

    # ── GET ───────────────────────────────────────────────────
    existing = (
        ProfessionalQualification.objects
        .filter(user=user)
        .prefetch_related(
            Prefetch(
                'documents',
                queryset=Document.objects.select_related('document_type').order_by('-uploaded_at'),
            )
        )
        .order_by('-year_obtained')
    )

    context = {
        'profile': profile,
        'user': user,
        'page': 'Professional Qualifications',
        'document_types': DocumentType.objects.all(),
        'existing': existing,
        'completion': completion,
        'has_academic': user.academic_qualifications.exists()
        if hasattr(user, 'academic_qualifications') else False,
        'has_professional': existing.exists(),
        'has_work_history': user.work_history.exists()
        if hasattr(user, 'work_history') else False,
        'has_additional': hasattr(user, 'additional_detail'),
        'has_memberships': ProfessionalBodyMembership.objects.filter(user=user).exists(),
        'has_referees': Referee.objects.filter(user=user).count() >= 2,
    }
    return render(request, 'Jobseekers/professional.html', context)


# ── delete_document — standalone AJAX endpoint ────────────────────────────────
def delete_document(request, doc_id):
    user_id = request.session.get('user_id')
    if not user_id:
        return JsonResponse({'status': 'error', 'message': 'Not authenticated.'}, status=403)
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'POST required.'}, status=405)

    doc = Document.objects.filter(id=doc_id, user_id=user_id).first()
    if not doc:
        return JsonResponse({'status': 'error', 'message': 'Document not found.'}, status=404)

    try:
        doc.file.delete(save=False)
    except Exception:
        pass

    doc.delete()
    return JsonResponse({'status': 'success', 'message': 'Document deleted.'})


def work_history_view(request):
    user_id = request.session.get('user_id')
    if not user_id:
        return redirect('index')

    user = JobseekerAccount.objects.filter(id=user_id).first()
    if not user:
        request.session.flush()
        return redirect('index')

    profile = JobSeekerProfile.objects.filter(user=user).first()
    completion = calculate_profile_completion(user)

    if request.method == 'POST':
        action = request.POST.get('action', 'save')

        # ── DELETE ───────────────────────────────────────────
        if action == 'delete':
            try:
                job_id = request.POST.get('job_id')
                job = WorkHistory.objects.filter(id=job_id, user=user).first()
                if not job:
                    return JsonResponse({'status': 'error',
                                         'message': 'Record not found.'})
                job.delete()
                return JsonResponse({'status': 'success',
                                     'message': 'Work history deleted successfully.'})
            except Exception as e:
                logger.exception("Error deleting work history for user %s", user.id)
                return JsonResponse({
                    'status': 'error',
                    'message': 'An unexpected error occurred while deleting the work history record.'
                })

        # ── EDIT ─────────────────────────────────────────────
        if action == 'edit':
            try:
                job_id = request.POST.get('job_id')
                job = WorkHistory.objects.filter(id=job_id, user=user).first()
                if not job:
                    return JsonResponse({'status': 'error',
                                         'message': 'Record not found.'})

                job_title = request.POST.get('job_title', '').strip()
                company = request.POST.get('company', '').strip()
                start_month = request.POST.get('start_month', '').strip()
                start_year = request.POST.get('start_year', '').strip()

                if not job_title:
                    return JsonResponse({'status': 'error',
                                         'message': 'Job title is required.'})
                if not company:
                    return JsonResponse({'status': 'error',
                                         'message': 'Employer / company is required.'})
                if not start_month or not start_year:
                    return JsonResponse({'status': 'error',
                                         'message': 'Start month and year are required.'})

                is_current = request.POST.get('is_current') == 'true'

                # If marking as current, unset any other current job
                if is_current:
                    WorkHistory.objects.filter(
                        user=user, is_current=True
                    ).exclude(id=job_id).update(is_current=False)

                end_month_raw = request.POST.get('end_month', '').strip()
                end_year_raw = request.POST.get('end_year', '').strip()

                job.job_title = job_title
                job.company = company
                job.employment_type = request.POST.get('employment_type', '').strip()
                job.start_month = int(start_month)
                job.start_year = int(start_year)
                job.end_month = int(end_month_raw) if end_month_raw and not is_current else None
                job.end_year = int(end_year_raw) if end_year_raw and not is_current else None
                job.is_current = is_current
                job.duties = request.POST.get('duties', '').strip()
                job.exit_reason = '' if is_current else request.POST.get('exit_reason', '').strip()
                job.country = request.POST.get('country', 'Kenya').strip() or 'Kenya'
                job.save()

                return JsonResponse({
                    'status': 'success',
                    'message': 'Work history updated successfully.',
                    'job': _job_to_dict(job),
                })

            except Exception as e:
                logger.exception("Error while updating work history entry for user %s", user.id)
                return JsonResponse({
                    'status': 'error',
                    'message': 'An unexpected error occurred while updating work history. Please try again later.',
                })

        # ── SAVE NEW ─────────────────────────────────────────
        try:
            jobs_data = json.loads(request.POST.get('jobs', '[]'))

            if not jobs_data:
                return JsonResponse({'status': 'error',
                                     'message': 'Please add at least one work history entry.'})

            saved = []

            for j in jobs_data:
                job_title = j.get('job_title', '').strip()
                company = j.get('company', '').strip()
                start_month = j.get('start_month', '')
                start_year = j.get('start_year', '')

                if not job_title or not company or not start_month or not start_year:
                    continue

                is_current = j.get('is_current', False)
                end_month_raw = j.get('end_month', '')
                end_year_raw = j.get('end_year', '')

                if is_current:
                    WorkHistory.objects.filter(
                        user=user, is_current=True
                    ).update(is_current=False)

                job = WorkHistory.objects.create(
                    user=user,
                    job_title=job_title,
                    company=company,
                    employment_type=j.get('employment_type', '').strip(),
                    start_month=int(start_month),
                    start_year=int(start_year),
                    end_month=int(end_month_raw) if end_month_raw and not is_current else None,
                    end_year=int(end_year_raw) if end_year_raw and not is_current else None,
                    is_current=is_current,
                    duties=j.get('duties', '').strip(),
                    exit_reason='' if is_current else j.get('exit_reason', '').strip(),
                    country=j.get('country', 'Kenya').strip() or 'Kenya',
                )
                saved.append(_job_to_dict(job))

            if not saved:
                return JsonResponse({'status': 'error',
                                     'message': 'No valid entries saved. Check required fields.'})

            return JsonResponse({
                'status': 'success',
                'message': f'{len(saved)} work history record(s) saved successfully.',
                'saved': saved,
            })

        except Exception as e:
            logger.exception("Error saving work history for user %s", user.id)
            return JsonResponse({
                'status': 'error',
                'message': 'An unexpected error occurred while saving the work history records.'
            })

    # ── GET ───────────────────────────────────────────────────
    existing = WorkHistory.objects.filter(user=user)

    context = {
        'profile': profile,
        'user': user,
        'page': 'Work History',
        'existing': existing,
        'completion': completion,
        'has_academic': AcademicQualification.objects.filter(user=user).exists(),
        'has_professional': ProfessionalQualification.objects.filter(user=user).exists(),
        'has_work_history': existing.exists(),
        'has_memberships': ProfessionalBodyMembership.objects.filter(user=user).exists(),
        'has_referees': Referee.objects.filter(user=user).count() >= 2,
        'has_additional': hasattr(user, 'additional_detail'),
    }
    return render(request, 'Jobseekers/work_history.html', context)


def _job_to_dict(job):
    """Serialise a WorkHistory instance for JSON responses."""
    MONTHS = {
        1: 'Jan', 2: 'Feb', 3: 'Mar', 4: 'Apr',
        5: 'May', 6: 'Jun', 7: 'Jul', 8: 'Aug',
        9: 'Sep', 10: 'Oct', 11: 'Nov', 12: 'Dec',
    }
    start_display = f"{MONTHS.get(job.start_month, '')} {job.start_year}"
    if job.is_current:
        end_display = 'Present'
    elif job.end_month and job.end_year:
        end_display = f"{MONTHS.get(job.end_month, '')} {job.end_year}"
    else:
        end_display = '—'

    return {
        'id': job.id,
        'job_title': job.job_title,
        'company': job.company,
        'employment_type': job.employment_type or '',
        'start_month': job.start_month,
        'start_year': job.start_year,
        'end_month': job.end_month or '',
        'end_year': job.end_year or '',
        'is_current': job.is_current,
        'duties': job.duties or '',
        'exit_reason': job.exit_reason or '',
        'country': job.country,
        'start_display': start_display,
        'end_display': end_display,
    }


def memberships_view(request):
    user_id = request.session.get('user_id')
    if not user_id:
        return redirect('index')

    user = JobseekerAccount.objects.filter(id=user_id).first()
    if not user:
        request.session.flush()
        return redirect('index')

    profile = JobSeekerProfile.objects.filter(user=user).first()
    completion = calculate_profile_completion(user)

    if request.method == 'POST':
        action = request.POST.get('action', 'save')

        # ── DELETE ───────────────────────────────────────────
        if action == 'delete':
            try:
                mem_id = request.POST.get('mem_id')
                mem = ProfessionalBodyMembership.objects.filter(
                    id=mem_id, user=user).first()
                if not mem:
                    return JsonResponse({'status': 'error',
                                         'message': 'Record not found.'})
                mem.delete()
                return JsonResponse({'status': 'success',
                                     'message': 'Membership deleted successfully.'})
            except Exception as e:
                logger.exception("Error deleting ProfessionalBodyMembership for user %s", user.id)
                return JsonResponse({
                    'status': 'error',
                    'message': 'An unexpected error occurred. Please try again later.'
                })

        # ── EDIT ─────────────────────────────────────────────
        if action == 'edit':
            try:
                mem_id = request.POST.get('mem_id')
                mem = ProfessionalBodyMembership.objects.filter(
                    id=mem_id, user=user).first()
                if not mem:
                    return JsonResponse({'status': 'error',
                                         'message': 'Record not found.'})

                body_name = request.POST.get('body_name', '').strip()
                membership_no = request.POST.get('membership_no', '').strip()
                year_joined = request.POST.get('year_joined', '').strip()
                expiry_raw = request.POST.get('expiry_year', '').strip()

                if not body_name:
                    return JsonResponse({'status': 'error',
                                         'message': 'Body name is required.'})
                if not membership_no:
                    return JsonResponse({'status': 'error',
                                         'message': 'Membership number is required.'})
                if not year_joined:
                    return JsonResponse({'status': 'error',
                                         'message': 'Year joined is required.'})

                mem.body_name = body_name
                mem.membership_no = membership_no
                mem.year_joined = int(year_joined)
                mem.expiry_year = int(expiry_raw) if expiry_raw else None
                mem.save()

                return JsonResponse({
                    'status': 'success',
                    'message': 'Membership updated successfully.',
                    'mem': _mem_to_dict(mem),
                })

            except Exception as e:
                logger.exception("Error editing ProfessionalBodyMembership %s for user %s", mem_id, user.id)
                return JsonResponse({
                    'status': 'error',
                    'message': 'An unexpected error occurred. Please try again later.'
                })

        # ── SAVE NEW ─────────────────────────────────────────
        try:
            mems_data = json.loads(request.POST.get('memberships', '[]'))

            if not mems_data:
                return JsonResponse({'status': 'error',
                                     'message': 'Please add at least one membership.'})

            saved = []
            for m in mems_data:
                body_name = m.get('body_name', '').strip()
                membership_no = m.get('membership_no', '').strip()
                year_joined = m.get('year_joined', '')
                expiry_raw = m.get('expiry_year', '')

                if not body_name or not membership_no or not year_joined:
                    continue

                mem = ProfessionalBodyMembership.objects.create(
                    user=user,
                    body_name=body_name,
                    membership_no=membership_no,
                    year_joined=int(year_joined),
                    expiry_year=int(expiry_raw) if expiry_raw else None,
                )
                saved.append(_mem_to_dict(mem))

            if not saved:
                return JsonResponse({'status': 'error',
                                     'message': 'No valid entries saved. Check required fields.'})

            return JsonResponse({
                'status': 'success',
                'message': f'{len(saved)} membership(s) saved successfully.',
                'saved': saved,
            })

        except Exception as e:
            return JsonResponse({'status': 'error',
                                 'message': f'Something went wrong: {str(e)}'})

    # ── GET ───────────────────────────────────────────────────
    existing = ProfessionalBodyMembership.objects.filter(user=user)

    context = {
        'profile': profile,
        'user': user,
        'page': 'Memberships',
        'existing': existing,
        'completion': completion,
        'has_academic': AcademicQualification.objects.filter(user=user).exists(),
        'has_professional': ProfessionalQualification.objects.filter(user=user).exists(),
        'has_work_history': WorkHistory.objects.filter(user=user).exists(),
        'has_memberships': existing.exists(),
        'has_additional': AdditionalDetail.objects.filter(user=user).exists(),
        'has_referees': Referee.objects.filter(user=user).count() >= 2,
    }
    return render(request, 'Jobseekers/membership.html', context)


def _mem_to_dict(mem):
    """Serialise a ProfessionalBodyMembership for JSON responses."""
    return {
        'id': mem.id,
        'body_name': mem.body_name,
        'membership_no': mem.membership_no,
        'year_joined': mem.year_joined,
        'expiry_year': mem.expiry_year or '',
    }


def referee_view(request):
    user_id = request.session.get('user_id')
    if not user_id:
        return redirect('index')

    user = JobseekerAccount.objects.filter(id=user_id).first()
    if not user:
        request.session.flush()
        return redirect('index')

    profile = JobSeekerProfile.objects.filter(user=user).first()
    completion = calculate_profile_completion(user)

    if request.method == 'POST':
        try:
            # ── Collect both referees first ───────────────────────────
            refs_data = {}
            for no in [1, 2]:
                import re as _re
                raw_mobile = request.POST.get(f'ref{no}_mobile', '').strip()
                mobile     = _re.sub(r'[\s\-]', '', raw_mobile)
                refs_data[no] = {
                    'name':         request.POST.get(f'ref{no}_name', '').strip(),
                    'occupation':   request.POST.get(f'ref{no}_occupation', '').strip(),
                    'organization': request.POST.get(f'ref{no}_organization', '').strip(),
                    'mobile':       mobile,
                    'email':        request.POST.get(f'ref{no}_email', '').strip(),
                    'period_known': request.POST.get(f'ref{no}_period_known', '').strip(),
                }

            # ── Validate BOTH before saving EITHER ───────────────────
            for no in [1, 2]:
                d = refs_data[no]
                if not all([d['name'], d['occupation'], d['organization'],
                            d['mobile'], d['email'], d['period_known']]):
                    return JsonResponse({
                        'status': 'error',
                        'message': f'All fields for Referee {no} are required. '
                                   f'Both referees must be complete before saving.'
                    })
                if len(d['mobile']) < 10:
                    return JsonResponse({'status': 'error',
                        'message': f'Referee {no}: Mobile number is too short. Minimum 10 digits.'})
                if len(d['mobile']) > 13:
                    return JsonResponse({'status': 'error',
                        'message': f'Referee {no}: Mobile number is too long. Maximum 13 characters.'})

            # ── Both valid — now save ─────────────────────────────────
            saved = []
            for no in [1, 2]:
                d = refs_data[no]
                referee, _ = Referee.objects.update_or_create(
                    user=user,
                    referee_no=no,
                    defaults={
                        'name':         d['name'],
                        'occupation':   d['occupation'],
                        'organization': d['organization'],
                        'mobile':       d['mobile'],
                        'email':        d['email'],
                        'period_known': d['period_known'],
                    }
                )
                saved.append(_referee_to_dict(referee))

            return JsonResponse({
                'status':     'success',
                'message':    'Referee details saved successfully.',
                'completion': calculate_profile_completion(user),
                'saved':      saved,
            })

        except Exception as e:
            return JsonResponse({'status': 'error',
                                 'message': f'Something went wrong: {str(e)}'})

    # ── GET ───────────────────────────────────────────────────────────
    ref1 = Referee.objects.filter(user=user, referee_no=1).first()
    ref2 = Referee.objects.filter(user=user, referee_no=2).first()

    context = {
        'profile':          profile,
        'user':             user,
        'page':             'Referees',
        'ref1':             ref1,
        'ref2':             ref2,
        'period_choices':   Referee.PERIOD_CHOICES,
        'completion':       completion,
        'has_academic':     AcademicQualification.objects.filter(user=user).exists(),
        'has_professional': ProfessionalQualification.objects.filter(user=user).exists(),
        'has_work_history': WorkHistory.objects.filter(user=user).exists(),
        'has_memberships':  ProfessionalBodyMembership.objects.filter(user=user).exists(),
        'has_referees':     Referee.objects.filter(user=user).count() >= 2,
        'has_additional':   AdditionalDetail.objects.filter(user=user).exists(),
    }
    return render(request, 'Jobseekers/referee.html', context)


def _referee_to_dict(ref):
    return {
        'id':           ref.id,
        'referee_no':   ref.referee_no,
        'name':         ref.name,
        'occupation':   ref.occupation,
        'organization': ref.organization,
        'mobile':       ref.mobile,
        'email':        ref.email,
        'period_known': ref.period_known,
    }


# ── Additional Details ───────────────────────────────────────
def additional_details_view(request):
    user_id = request.session.get('user_id')
    if not user_id:
        return redirect('index')

    user = JobseekerAccount.objects.filter(id=user_id).first()
    if not user:
        request.session.flush()
        return redirect('index')

    profile = JobSeekerProfile.objects.filter(user=user).first()
    completion = calculate_profile_completion(user)
    detail = AdditionalDetail.objects.filter(user=user).first()

    if request.method == 'POST':
        action = request.POST.get('action', 'save')

        # ── DELETE CV ─────────────────────────────────────────────────
        if action == 'delete_cv':
            try:
                if detail and detail.cv:
                    if os.path.isfile(detail.cv.path):
                        os.remove(detail.cv.path)
                    detail.cv = None
                    detail.save()
                return JsonResponse({'status': 'success', 'message': 'CV removed successfully.'})
            except Exception as e:
                return JsonResponse({'status': 'error', 'message': str(e)})

        # ── DELETE COVER LETTER ───────────────────────────────────────
        if action == 'delete_cover_letter':
            try:
                if detail and detail.cover_letter:
                    if os.path.isfile(detail.cover_letter.path):
                        os.remove(detail.cover_letter.path)
                    detail.cover_letter = None
                    detail.save()
                return JsonResponse({'status': 'success', 'message': 'Cover letter removed successfully.'})
            except Exception as e:
                return JsonResponse({'status': 'error', 'message': str(e)})

        # ── SAVE / UPDATE ─────────────────────────────────────────────
        try:
            linkedin_url = request.POST.get('linkedin_url', '').strip()
            portfolio_url = request.POST.get('portfolio_url', '').strip()
            languages_raw = request.POST.get('languages', '').strip()
            availability = request.POST.get('availability', '').strip()
            salary_raw = request.POST.get('expected_salary', '').strip()
            cv_file = request.FILES.get('cv')
            cover_letter_file = request.FILES.get('cover_letter')

            # ── Server-side validation ────────────────────────────────
            if not availability:
                return JsonResponse({'status': 'error', 'message': 'Please select your availability.'})

            # Cover letter required if not already saved
            has_cover_letter = (detail and detail.cover_letter) or cover_letter_file
            if not has_cover_letter:
                return JsonResponse({'status': 'error', 'message': 'Please upload your cover letter (PDF).'})

            # Validate CV file
            if cv_file:
                if not cv_file.name.lower().endswith('.pdf'):
                    return JsonResponse({'status': 'error', 'message': 'CV must be a PDF file.'})
                if cv_file.size > 2 * 1024 * 1024:
                    return JsonResponse({'status': 'error', 'message': 'CV must be smaller than 2MB.'})

            # Validate cover letter file
            if cover_letter_file:
                if not cover_letter_file.name.lower().endswith('.pdf'):
                    return JsonResponse({'status': 'error', 'message': 'Cover letter must be a PDF file.'})
                if cover_letter_file.size > 2 * 1024 * 1024:
                    return JsonResponse({'status': 'error', 'message': 'Cover letter must be smaller than 2MB.'})

            # Clean languages
            languages = ', '.join(
                dict.fromkeys(
                    l.strip().title()
                    for l in languages_raw.split(',')
                    if l.strip()
                )
            )

            expected_salary = int(salary_raw) if salary_raw.isdigit() else None

            if detail:
                if cv_file:
                    if detail.cv and os.path.isfile(detail.cv.path):
                        os.remove(detail.cv.path)
                    detail.cv = cv_file

                if cover_letter_file:
                    if detail.cover_letter and os.path.isfile(detail.cover_letter.path):
                        os.remove(detail.cover_letter.path)
                    detail.cover_letter = cover_letter_file

                detail.linkedin_url = linkedin_url
                detail.portfolio_url = portfolio_url
                detail.languages = languages
                detail.availability = availability
                detail.expected_salary = expected_salary
                detail.save()
            else:
                detail = AdditionalDetail.objects.create(
                    user=user,
                    cv=cv_file,
                    cover_letter=cover_letter_file,
                    linkedin_url=linkedin_url,
                    portfolio_url=portfolio_url,
                    languages=languages,
                    availability=availability,
                    expected_salary=expected_salary,
                )

            new_completion = calculate_profile_completion(user)

            return JsonResponse({
                'status': 'success',
                'message': 'Additional details saved successfully.',
                'cv_filename': detail.cv.name.split('/')[-1] if detail.cv else None,
                'cv_url': detail.cv.url if detail.cv else None,
                'cover_letter_filename': detail.cover_letter.name.split('/')[-1] if detail.cover_letter else None,
                'cover_letter_url': detail.cover_letter.url if detail.cover_letter else None,
                'completion': new_completion,
            })

        except Exception as e:
            logger.exception("Error while saving additional details for user_id=%s", user.id if user else None)
            return JsonResponse({
                'status': 'error',
                'message': 'Something went wrong while saving your additional details. Please try again later.'
            })

    context = {
        'profile': profile,
        'user': user,
        'page': 'Additional Details',
        'detail': detail,
        'completion': completion,
        'has_academic': AcademicQualification.objects.filter(user=user).exists(),
        'has_professional': ProfessionalQualification.objects.filter(user=user).exists(),
        'has_work_history': WorkHistory.objects.filter(user=user).exists(),
        'has_memberships': ProfessionalBodyMembership.objects.filter(user=user).exists(),
        'has_referees': Referee.objects.filter(user=user).count() >= 2,
        'has_additional': detail is not None,
    }
    return render(request, 'Jobseekers/additional.html', context)


@login_required
def hr_dashboard(request):
    user = request.user
    user_roles = user.role.values_list('name', flat=True)

    vacancies = Vacancy.objects.exclude(status='draft').annotate(
        applications_count=Count('jobapplication')
    ).order_by('-created_at')

    # Build vacancies_ready with winner info for the appointments table
    ceo_approved_vacancies = Vacancy.objects.filter(status='ceo_approved')
    vacancies_ready = []
    for v in ceo_approved_vacancies:
        winner = JobApplication.objects.filter(
            vacancy=v, status__code='ceo_selected',
        ).select_related('user').first()
        vacancies_ready.append({'vacancy': v, 'winner': winner})

    context = {
        'user': user,
        'user_roles': user_roles,
        'vacancies': vacancies,
        'vacancies_ready': vacancies_ready,
        'open_vacancies_count': Vacancy.objects.filter(status='open').count(),
        'pending_ceo_count': Vacancy.objects.filter(status='ceo_review').count(),
        'pending_appointments_count': Vacancy.objects.filter(status='ceo_approved').count(),
        'appointed_count': Vacancy.objects.filter(status='appointed').count(),
        'page': 'HR Dashboard',
    }

    return render(request, 'recruitment/hr/dashboard.html', context)





@login_required
@role_required(['admin'])
def admin_dashboard(request):
    context = {
        "page": "Admin Dashboard"
    }

    return render(
        request,
        "recruitment/admin/dashboard.html",
        context
    )


@login_required
@role_required(['officer'])
def officer_dashboard(request):
    context = {
        'internal_vacancies_count': Vacancy.objects.filter(status='open').count(),
        'my_applications_count': request.user.application_set.count()
    }
    return render(request, 'officer/dashboard.html', context)





@login_required
@role_required(['panelist'])
def submit_score(request, application_id):
    application = get_object_or_404(Application, id=application_id)

    if request.method == 'POST':
        score = request.POST.get('score')
        remarks = request.POST.get('remarks')

        InterviewScore.objects.update_or_create(
            application=application,
            panelist=request.user,
            defaults={'score': score, 'remarks': remarks}
        )

        return redirect('panelist_dashboard')


@login_required
@role_required(['hod_hr'])
def generate_ranking(request, vacancy_id):
    vacancy = get_object_or_404(Vacancy, id=vacancy_id)

    applications = Application.objects.filter(
        vacancy=vacancy,
        status='interviewed'
    ).annotate(
        avg_score=Avg('scores__score')
    ).order_by('-avg_score')

    return render(request, 'recruitment/hr/top_three.html', {'applications': applications})


@login_required
@role_required(['hod_hr'])
def appoint_candidate(request, vacancy_id):
    vacancy = get_object_or_404(Vacancy, id=vacancy_id)

    ceo_decision = CEODecision.objects.get(vacancy=vacancy)

    Appointment.objects.create(
        vacancy=vacancy,
        application=ceo_decision.selected_application,
        appointed_by=request.user
    )

    ceo_decision.selected_application.status = 'selected'
    ceo_decision.selected_application.save()

    Application.objects.filter(
        vacancy=vacancy
    ).exclude(
        id=ceo_decision.selected_application.id
    ).update(status='not_selected')

    vacancy.status = 'appointed'
    vacancy.save()

    return redirect('hr_dashboard')


@login_required
@role_required(['hod_hr'])
# ── Create Vacancy ─────────────────────────────────────────────────────────
def create_vacancy(request):
    education_levels = EducationLevel.objects.all().order_by('rank')

    if request.method == 'POST':

        # ── Step 1: Position ───────────────────────────────
        title = request.POST.get('title', '').strip()
        reference_number = request.POST.get('reference_number', '').strip()
        description = request.POST.get('description', '').strip()
        vacancy_type = request.POST.get('vacancy_type', 'external').strip()
        grade_category = request.POST.get('grade_category', '4-1').strip()
        start_date = request.POST.get('start_date', '').strip()
        end_date = request.POST.get('end_date', '').strip()
        advert_pdf = request.FILES.get('advert_pdf')

        # ── Step 2: Screening criteria ─────────────────────
        screening_criteria = {
            'require_cv':
                bool(request.POST.get('sc_require_cv')),
            'require_cover_letter':
                bool(request.POST.get('sc_require_cover_letter')),
            'require_academic_cert':
                bool(request.POST.get('sc_require_academic_cert')),
            'require_professional_qualification':
                bool(request.POST.get('sc_require_professional_qualification')),
            'minimum_education_level':
                int(request.POST.get('sc_minimum_education_level') or 0),
            'minimum_experience_years':
                int(request.POST.get('sc_minimum_experience_years') or 0),
            'check_salary':
                bool(request.POST.get('sc_check_salary')),
            'salary_max':
                int(request.POST.get('sc_salary_max') or 0),
            'check_availability':
                bool(request.POST.get('sc_check_availability')),
            'maximum_notice_days':
                int(request.POST.get('sc_maximum_notice_days') or 30),
        }

        # ── Validation ─────────────────────────────────────
        errors = []

        if not all([title, reference_number, description, start_date, end_date]):
            errors.append("All required fields must be filled.")

        if vacancy_type not in ['external', 'internal']:
            errors.append("Invalid vacancy type.")

        if grade_category not in ['4-1', '10-5']:
            errors.append("Invalid grade category.")

        if advert_pdf:
            if not advert_pdf.name.lower().endswith('.pdf'):
                errors.append("Only PDF files are allowed for the advert.")
            elif advert_pdf.size > 5 * 1024 * 1024:
                errors.append("Advert PDF must be under 5MB.")

        parsed_start = parsed_end = None
        try:
            parsed_start = datetime.strptime(start_date, "%Y-%m-%d").date()
            parsed_end = datetime.strptime(end_date, "%Y-%m-%d").date()
        except ValueError:
            errors.append("Invalid date format.")

        if parsed_start and parsed_end:
            today = timezone.now().date()
            if parsed_start < today:
                errors.append("Start date cannot be in the past.")
            if parsed_end <= parsed_start:
                errors.append("End date must be after the start date.")

        if reference_number and Vacancy.objects.filter(
                reference_number=reference_number).exists():
            errors.append(
                f"Reference number '{reference_number}' already exists.")

        min_edu = screening_criteria['minimum_education_level']
        if min_edu > 0 and not EducationLevel.objects.filter(
                rank=min_edu).exists():
            errors.append("Invalid minimum education level selected.")

        if errors:
            for error in errors:
                messages.error(request, error)
            return render(request, 'recruitment/hr/create_vacancy.html', {
                'page': 'Create Vacancy',
                'posted': request.POST,
                'education_levels': education_levels,
            })

        Vacancy.objects.create(
            title=title,
            reference_number=reference_number,
            description=description,
            vacancy_type=vacancy_type,
            grade_category=grade_category,
            advert_pdf=advert_pdf,
            start_date=parsed_start,
            end_date=parsed_end,
            screening_criteria=screening_criteria,
            created_by=request.user,
            status='draft',
        )

        messages.success(request, f"Vacancy '{title}' created as Draft.")
        return redirect('hr_dashboard')

    return render(request, 'recruitment/hr/create_vacancy.html', {
        'page': 'Create Vacancy',
        'education_levels': education_levels,
    })


def download_vacancy_pdf(request, vacancy_id):
    try:
        vacancy = Vacancy.objects.get(id=vacancy_id)
        if not vacancy.advert_pdf:
            raise Http404("PDF not found")
        return FileResponse(vacancy.advert_pdf.open(), as_attachment=True)
    except Vacancy.DoesNotExist:
        raise Http404("Vacancy not found")


@login_required
@role_required(['hod_hr'])
# ── Update Vacancy ─────────────────────────────────────────────────────────
def update_vacancy(request, vacancy_id):
    vacancy = get_object_or_404(Vacancy, id=vacancy_id)

    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        reference_number = request.POST.get('reference_number', '').strip()
        description = request.POST.get('description', '').strip()
        vacancy_type = request.POST.get('vacancy_type', vacancy.vacancy_type).strip()
        grade_category = request.POST.get('grade_category', vacancy.grade_category).strip()
        start_date_str = request.POST.get('start_date', '').strip()
        end_date_str = request.POST.get('end_date', '').strip()
        advert_pdf = request.FILES.get('advert_pdf')

        errors = []

        if not all([title, reference_number, description, start_date_str, end_date_str]):
            errors.append("All required fields must be filled.")

        if vacancy_type not in ['external', 'internal']:
            errors.append("Invalid vacancy type.")

        if grade_category not in ['4-1', '10-5']:
            errors.append("Invalid grade category.")

        parsed_start = parsed_end = None
        try:
            parsed_start = datetime.strptime(start_date_str, "%Y-%m-%d").date()
            parsed_end = datetime.strptime(end_date_str, "%Y-%m-%d").date()
        except ValueError:
            errors.append("Invalid date format.")

        if parsed_start and parsed_end:
            if parsed_end <= parsed_start:
                errors.append("End date must be after start date.")

        # Check duplicate ref — exclude current vacancy
        if Vacancy.objects.filter(
                reference_number=reference_number
        ).exclude(id=vacancy.id).exists():
            errors.append(f"Reference number '{reference_number}' is already used by another vacancy.")

        if advert_pdf:
            if not advert_pdf.name.lower().endswith('.pdf'):
                errors.append("Only PDF files are allowed.")
            elif advert_pdf.size > 5 * 1024 * 1024:
                errors.append("Advert PDF must be under 5MB.")

        if errors:
            for error in errors:
                messages.error(request, error)
            return render(request, 'recruitment/hr/update_vacancy.html', {
                'page': 'Edit Vacancy',
                'vacancy': vacancy,
            })

        vacancy.title = title
        vacancy.reference_number = reference_number
        vacancy.description = description
        vacancy.vacancy_type = vacancy_type
        vacancy.grade_category = grade_category
        vacancy.start_date = parsed_start
        vacancy.end_date = parsed_end
        if advert_pdf:
            vacancy.advert_pdf = advert_pdf
        vacancy.save()

        messages.success(request, f"Vacancy '{title}' updated successfully.")
        return redirect('hr_dashboard')

    return render(request, 'recruitment/hr/update_vacancy.html', {
        'page': 'Edit Vacancy',
        'vacancy': vacancy,
    })


@login_required
@role_required(['hod_hr'])
# ── Delete Vacancy (AJAX POST from Swal confirm) ───────────────────────────
def delete_vacancy(request, vacancy_id):
    vacancy = get_object_or_404(Vacancy, id=vacancy_id)

    # Accept both AJAX (from Swal) and standard POST (from confirm_delete page)
    if request.method == 'POST':
        title = vacancy.title
        vacancy.delete()
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'status': 'ok', 'message': f"Vacancy '{title}' deleted."})
        messages.success(request, f"Vacancy '{title}' deleted successfully.")
        return redirect('hr_dashboard')

    # GET — fallback confirm page (keep for safety)
    return render(request, 'recruitment/hr/confirm_delete.html', {
        'page': 'Delete Vacancy',
        'vacancy': vacancy,
    })


@login_required
@role_required(['hod_hr'])
# ── Publish Vacancy (draft → open) ────────────────────────────────────────
def publish_vacancy(request, vacancy_id):
    vacancy = get_object_or_404(Vacancy, id=vacancy_id)

    if vacancy.status != 'draft':
        messages.error(request, "Only draft vacancies can be published.")
        return redirect('hr_dashboard')

    vacancy.status = 'open'
    vacancy.save()
    messages.success(request, f"Vacancy '{vacancy.title}' is now live and open for applications.")
    return redirect('hr_dashboard')


def vacancy_detail(request, vacancy_id):
    vacancy = get_object_or_404(
        Vacancy,
        id=vacancy_id,
        status='open'
    )

    return render(request, 'recruitment/hr/vacancy_detail.html', {
        'vacancy': vacancy
    })


def apply_for_vacancy(request, vacancy_id):
    vacancy = get_object_or_404(Vacancy, id=vacancy_id)

    user_id = request.session.get('user_id')
    if not user_id:
        return redirect('index')

    user = JobseekerAccount.objects.filter(pk=user_id).first()

    if request.method == 'POST':
        cv_file = request.FILES.get('cv')
        cover_letter = request.POST.get('cover_letter', '').strip()

        # Validate CV
        if not cv_file:
            messages.error(request, "Please upload your CV.")
        elif not cv_file.name.lower().endswith('.pdf'):
            messages.error(request, "CV must be a PDF.")
        elif not cover_letter:
            messages.error(request, "Cover letter cannot be empty.")
        else:
            snapshot = build_profile_snapshot(user)

            application = Application.objects.create(
                vacancy=vacancy,
                applicant=user,
                cv=cv_file,
                cover_letter=cover_letter,
                profile_snapshot=snapshot
            )
            application.save()
            messages.success(request, "Application submitted successfully.")
            return redirect('dashboard')

    return render(request, 'recruitment/applicant/apply.html', {'vacancy': vacancy})


@login_required
@role_required(['hod_hr'])
# ── Move to Longlisting (closed → longlisting) ────────────────────────────
def move_to_longlisting(request, vacancy_id):
    vacancy = get_object_or_404(Vacancy, id=vacancy_id)

    if vacancy.status != 'closed':
        messages.error(request, "Vacancy must be closed before moving to longlisting.")
        return redirect('hr_dashboard')

    vacancy.status = 'longlisting'
    vacancy.save()
    messages.success(request, f"'{vacancy.title}' moved to Longlisting stage.")
    return redirect('hr_dashboard')


@login_required
@role_required(['hod_hr', 'panelist', 'committee'])
def hr_view_applications(request, vacancy_id):
    vacancy = get_object_or_404(Vacancy, id=vacancy_id)

    # Only counts for KPI cards — no full queryset loaded into memory
    status_counts = (
        JobApplication.objects
        .filter(vacancy=vacancy)
        .values('status__name', 'status__code')
        .annotate(count=Count('id'))
        .order_by('status__order')
    )

    total = JobApplication.objects.filter(vacancy=vacancy).count()

    context = {
        'page': f'Applications — {vacancy.title}',
        'vacancy': vacancy,
        'total': total,
        'status_counts': status_counts,
    }
    return render(request, 'recruitment/hr/view_applications.html', context)


@login_required
@role_required(['hod_hr', 'panelist', 'committee'])
def hr_view_applications_json(request, vacancy_id):
    """
    Server-side DataTables JSON endpoint.
    Add to urls.py:
    path('hr/vacancy/<int:vacancy_id>/applications/json/', views.hr_view_applications_json, name='hr_applications_json'),
    """
    vacancy = get_object_or_404(Vacancy, id=vacancy_id)

    draw = int(request.GET.get('draw', 1))
    start = int(request.GET.get('start', 0))
    length = int(request.GET.get('length', 25))
    search = request.GET.get('search[value]', '').strip()

    # Column index → DB field for ordering
    col_map = {
        '1': 'application_number',
        '6': 'submitted_at',
        '7': 'status__order',
        '8': 'longlist_decision',  # ← added
    }
    order_col = request.GET.get('order[0][column]', '6')
    order_dir = request.GET.get('order[0][dir]', 'desc')
    order_field = col_map.get(order_col, 'submitted_at')
    if order_dir == 'desc':
        order_field = '-' + order_field

    qs = (
        JobApplication.objects
        .filter(vacancy=vacancy)
        .select_related('status', 'user')
    )

    total_records = qs.count()

    if search:
        qs = qs.filter(
            Q(application_number__icontains=search) |
            Q(user__email__icontains=search) |
            Q(snapshot_basic__id_no__icontains=search)
        )

    filtered_records = qs.count()
    qs = qs.order_by(order_field)[start: start + length]

    rows = []
    for i, app in enumerate(qs, start=start + 1):
        basic = app.snapshot_basic or {}
        # ↓ added: read docs from snapshot — zero extra DB queries
        academic = app.snapshot_academic or []
        professional = app.snapshot_professional or []
        additional = app.snapshot_additional or {}

        full_name = ' '.join(filter(None, [
            basic.get('first_name', ''),
            basic.get('second_name', ''),
            basic.get('surname', ''),
        ])) or app.user.email

        # ↓ added: flatten all attached docs from each qual's documents list
        academic_docs = [
            {'url': doc['file_url'], 'filename': doc.get('filename', ''), 'type': doc.get('document_type', '')}
            for qual in academic
            for doc in qual.get('documents', [])
            if doc.get('file_url')
        ]

        professional_docs = [
            {'url': doc['file_url'], 'filename': doc.get('filename', ''), 'type': doc.get('document_type', '')}
            for qual in professional
            for doc in qual.get('documents', [])
            if doc.get('file_url')
        ]

        rows.append({
            'row_num': i,
            'application_number': app.application_number or '—',
            'full_name': full_name,
            'id_no': basic.get('id_no', '—'),
            'email': app.user.email,
            'phone': basic.get('phone_number', '—'),
            'submitted_at': app.submitted_at.strftime('%d %b %Y'),
            'status_code': app.status.code,
            'status_name': app.status.name,
            'longlist_decision': app.longlist_decision or '',  # ← added
            'docs': {  # ← added
                'cv_url': additional.get('cv_url', ''),
                'cover_letter_url': additional.get('cover_letter_url', ''),
                'academic_docs': academic_docs,
                'professional_docs': professional_docs,
            },
            'detail_url': f'/recruitment/hr/application/{app.id}/',
        })

    return JsonResponse({
        'draw': draw,
        'recordsTotal': total_records,
        'recordsFiltered': filtered_records,
        'data': rows,
    })


@login_required
@role_required(['committee'])
def committee_view_applications(request, vacancy_id):
    vacancy = get_object_or_404(Vacancy, id=vacancy_id)

    applications = Application.objects.filter(vacancy=vacancy) \
        .select_related(
        "applicant",
        "applicant__profile",
        "applicant__additional_detail"
    ).prefetch_related(
        "applicant__academic_qualifications",
        "applicant__work_history",
        "applicant__professional_qualifications",
        "applicant__documents"
    )

    return render(request, 'recruitment/hr/committee_view_applications.html', {
        'vacancy': vacancy,
        'applications': applications
    })


# HR View to Move Vacancy to Longlisting

@login_required
# @role_required(['hod_hr'])
def start_longlisting(request, vacancy_id):
    vacancy = get_object_or_404(Vacancy, id=vacancy_id)

    if vacancy.status != 'closed':
        messages.error(request, "Vacancy must be closed before longlisting.")
        return redirect('hr_dashboard')

    vacancy.status = 'longlisting'
    vacancy.save()

    messages.success(request, "Longlisting stage started.")
    return redirect('hr_dashboard')


# @login_required
# @role_required(['hod_hr'])
# def committee_stage(request, vacancy_id):
#     vacancy = get_object_or_404(Vacancy, id=vacancy_id)

#     if vacancy.status != 'longlisting':
#         messages.error(request, "Not in longlisting stage.")
#         return redirect('hr_dashboard')

#     vacancy.status = 'committee_stage'
#     vacancy.save()

#     return redirect('hr_dashboard')

@login_required
@role_required(['committee'])
def shortlist_candidates(request, vacancy_id):
    vacancy = get_object_or_404(Vacancy, id=vacancy_id)

    if vacancy.status != 'shortlisting':
        messages.error(request, "Not in shortlisting stage.")
        return redirect('hr_dashboard')

    applications = Application.objects.filter(vacancy=vacancy)

    if request.method == 'POST':
        selected_ids = request.POST.getlist('selected_applications')

        if not selected_ids:
            messages.error(request, "You must select at least one candidate.")
            return redirect('shortlist_candidates', vacancy_id=vacancy.id)

        Application.objects.filter(vacancy=vacancy).update(status='submitted')

        Application.objects.filter(
            id__in=selected_ids,
            vacancy=vacancy
        ).update(status='shortlisted')

        vacancy.status = 'shortlisting'
        vacancy.save()
        return redirect('shortlisting_dashboard')

    return render(request, 'recruitment/hr/shortlist.html', {
        'vacancy': vacancy,
        'applications': applications
    })


from django.contrib.auth import get_user_model

User = get_user_model()




def evaluate_shortlisting(application):
    committee = application.vacancy.shortlisting_committee
    total_members = committee.members.count()

    votes = application.shortlisting_votes.all()

    if votes.count() < total_members:
        return  # not complete yet

    approvals = votes.filter(decision='approve').count()

    if approvals >= (total_members // 2 + 1):
        application.status = 'shortlisted'
    else:
        application.status = 'rejected'

    application.save()





from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied


@login_required
@role_required(['hod_hr'])
# ── Reopen Vacancy (closed → open) ────────────────────────────────────────
def open_vacancy(request, vacancy_id):
    vacancy = get_object_or_404(Vacancy, id=vacancy_id)

    if vacancy.status != 'closed':
        messages.warning(request, "Only closed vacancies can be reopened.")
        return redirect('hr_dashboard')

    vacancy.status = 'open'
    vacancy.save()
    messages.success(request, f"Vacancy '{vacancy.title}' has been reopened.")
    return redirect('vacancy_list')


@login_required
@role_required(['hod_hr'])
def close_vacancy(request, vacancy_id):
    vacancy = get_object_or_404(Vacancy, id=vacancy_id)

    if vacancy.status != 'open':
        messages.warning(request, "Only open vacancies can be closed.")
        return redirect('hr_dashboard')

    # Import the same function the context processor uses
    from accounts.context_processors import _close_and_screen
    from django.utils import timezone

    today = timezone.now().date()
    _close_and_screen(vacancy, today)

    messages.success(
        request,
        f"Vacancy '{vacancy.title}' closed and screening completed. "
        f"Applications have been Sysytem longlisted awaiting manual longlisting"
    )
    return redirect('vacancy_list')






from django.db.models import Q


@login_required
@role_required(['hod_hr'])
def hr_ranking_view(request, vacancy_id):
    vacancy = get_object_or_404(Vacancy, id=vacancy_id)

    if vacancy.status != 'interviews':
        messages.error(request, "Ranking available only during interview stage.")
        return redirect('hr_dashboard')

    applications = Application.objects.filter(
        vacancy=vacancy
    ).annotate(
        avg_score=Avg('scores__total_score'),
        score_count=Count('scores')
    ).filter(
        score_count__gt=0
    ).order_by('-avg_score')

    total_applications = applications.count()

    return render(request, 'recruitment/hr/ranking.html', {
        'vacancy': vacancy,
        'applications': applications,
        'total_applications': total_applications
    })


@login_required
@role_required(['hod_hr'])
def select_top_three(request, vacancy_id):
    vacancy = get_object_or_404(Vacancy, id=vacancy_id)

    if request.method == 'POST':
        selected_ids = request.POST.getlist('selected_candidates')

        # Total applications (or panelists assigned) for this vacancy
        total_applications = Application.objects.filter(vacancy=vacancy).count()

        # Only enforce exactly 3 selections if more than 3 exist
        if total_applications > 3 and len(selected_ids) != 3:
            messages.error(request, "You must select exactly three candidates.")
            return redirect('hr_ranking_view', vacancy_id=vacancy.id)

        # Optional safety: prevent selecting more than available
        if len(selected_ids) > total_applications:
            messages.error(request, "Invalid number of selections.")
            return redirect('hr_ranking_view', vacancy_id=vacancy.id)

        # Reset all to interviewed
        Application.objects.filter(
            vacancy=vacancy
        ).update(status='interviewed')

        # Update selected ones
        Application.objects.filter(
            id__in=selected_ids,
            vacancy=vacancy
        ).update(status='selected_top_three')

        # vacancy.status = 'top_three_selected'

        vacancy.status = 'ceo_review'
        vacancy.save()

        messages.success(request, "Selection completed successfully.")
        return redirect('hr_dashboard')





@login_required
@role_required(['ceo'])
def ceo_approve(request, vacancy_id):
    vacancy = get_object_or_404(Vacancy, id=vacancy_id)

    if request.method == 'POST':
        application_id = request.POST.get('application_id')
        reason = request.POST.get('reason', '')

        selected = get_object_or_404(Application, id=application_id)

        is_override = selected.status != 'selected_top_three'

        CEODecision.objects.create(
            vacancy=vacancy,
            selected_application=selected,
            approved_by=request.user,
            is_override=is_override,
            reason=reason if is_override else ''
        )

        vacancy.status = 'approved'
        vacancy.save()

        messages.success(request, "Vacancy approved successfully.")
        return redirect('ceo_dashboard')

    return redirect('ceo_dashboard')


from django.db.models import Avg, Count


@login_required
@role_required(['ceo'])
def ceo_review_view(request, vacancy_id):
    vacancy = get_object_or_404(Vacancy, id=vacancy_id)

    if vacancy.status != 'ceo_review':
        messages.error(request, "This vacancy is not in CEO review stage.")
        return redirect('ceo_dashboard')

    applications = Application.objects.filter(
        vacancy=vacancy
    ).annotate(
        avg_score=Avg('scores__total_score'),
        score_count=Count('scores')
    ).filter(
        score_count__gt=0
    ).order_by('-avg_score')

    return render(request, 'recruitment/ceo/review.html', {
        'vacancy': vacancy,
        'applications': applications
    })


@login_required
@role_required(['ceo'])
def ceo_select_candidate(request, vacancy_id, application_id):
    vacancy = get_object_or_404(Vacancy, id=vacancy_id)

    # Ensure only applications that are interview-locked are selectable
    application = get_object_or_404(
        Application,
        id=application_id,
        vacancy=vacancy,
        # interview_locked=True
    )

    if vacancy.status != 'ceo_review':
        messages.error(request, "Not in CEO review stage.")
        return redirect('ceo_dashboard')

    # Determine if this candidate is in Top 3
    is_override = application.status != 'selected_top_three'

    if request.method == 'POST':
        override_reason = request.POST.get('override_reason', '').strip()

        if is_override and not override_reason:
            messages.error(request, "Override requires a reason.")
            return redirect(
                'ceo_select_candidate',
                vacancy_id=vacancy.id,
                application_id=application.id
            )

        # Reset previous CEO selections
        Application.objects.filter(
            vacancy=vacancy
        ).update(ceo_selected=False)

        # Update selected application
        application.ceo_selected = True
        application.status = 'ceo_approved'

        if is_override:
            application.ceo_override = True
            application.ceo_override_reason = override_reason

        application.save()

        # Update vacancy status
        vacancy.status = 'ceo_approved'
        vacancy.save()

        messages.success(request, "Candidate approved by CEO.")
        return redirect('ceo_dashboard')

    return render(request, 'recruitment/ceo/select.html', {
        'vacancy': vacancy,
        'application': application,
        'is_override': is_override
    })


@login_required
@role_required(['hod_hr', 'committee', 'panelist'])
def application_detail(request, application_id):
    application = get_object_or_404(
        JobApplication.objects.select_related(
            "user",
            "user__additional_detail",  # needed for CV/cover letter file URLs
            "vacancy",
            "status",
        ),
        id=application_id
    )

    return render(request, "recruitment/hr/application_detail.html", {
        "application": application
    })


from django.contrib.auth.decorators import login_required
from core.decorators import role_required


# ----------------------
# Stage: Longlisting
# ----------------------
@login_required
@role_required(['hod_hr'])
def vacancy_longlisting(request):
    vacancies_qs = Vacancy.objects.filter(status='longlisting').order_by('-end_date')

    vacancy_data = []
    for v in vacancies_qs:
        apps = JobApplication.objects.filter(vacancy=v, status__code='longlisted')
        total = apps.count()
        accepted = apps.filter(longlist_decision='accepted').count()
        rejected = apps.filter(longlist_decision='rejected').count()
        reviewed = accepted + rejected
        unreviewed = total - reviewed
        pct = int((reviewed / total * 100) if total else 0)

        vacancy_data.append({
            'vacancy': v, 'total': total, 'accepted': accepted,
            'rejected': rejected, 'reviewed': reviewed,
            'unreviewed': unreviewed, 'pct': pct,
        })

    return render(request, 'recruitment/hr/longlisting/vacancy_picker.html', {
        'page': 'Longlisting',
        'vacancies': vacancy_data,
    })


# @login_required
# @role_required(['hod_hr'])
# def longlist_candidates(request, vacancy_id):
#     vacancy = get_object_or_404(Vacancy, id=vacancy_id)
#     vacancies = Vacancy.objects.filter(status='longlisting')

#     if vacancy.status not in ['longlisting']:
#         messages.error(request, "Vacancy is not in longlisting stage.")
#         return redirect('hr_dashboard')

#     applications = Application.objects.filter(
#         vacancy=vacancy,
#         status='submitted'
#     )

#     if request.method == 'POST':
#         selected_ids = request.POST.getlist('selected_applications')

#         for app in applications:
#             if str(app.id) in selected_ids:
#                 app.move_to('shortlisted')
#             else:
#                 app.move_to('not_selected')

#         vacancy.move_to('shortlisting')

#         messages.success(request, "Longlisting completed successfully.")
#         return redirect('hr_dashboard')

#     return render(request, 'recruitment/hr/longlisting.html', {
#         'vacancy': vacancy,
#         'applications': applications,
#         'vacancies': vacancies
#     })

# ----------------------
# Stage: Shortlisting
# ----------------------

# ── vacancy_shortlisting — updated to use CommitteeVote ──────────────────────

@login_required
@role_required(['hod_hr'])
def vacancy_shortlisting(request):
    """
    Shortlisting picker — shows vacancies in committee_stage.
    """
    vacancies_qs = Vacancy.objects.filter(
        status='committee_stage'
    ).order_by('end_date')

    vacancy_data = []
    for v in vacancies_qs:
        # Final longlisted applications
        app_count = JobApplication.objects.filter(
            vacancy=v,
            status__code='final_longlisted',
        ).count()

        # Active committee members
        committee = ShortlistingCommittee.objects.filter(vacancy=v, is_active=True)
        committee_count = committee.count()

        # How many members have submitted ALL their votes
        # (votes_submitted flag on ShortlistingCommittee)
        voted_count = committee.filter(votes_submitted=True).count()
        all_voted = (voted_count == committee_count and committee_count > 0)

        # Has the shortlist been generated yet?
        shortlist_generated = ShortlistResult.objects.filter(vacancy=v).exists()

        threshold = _threshold(committee_count)
        deadline = v.end_date + timedelta(days=21)
        days_remaining = (deadline - timezone.now().date()).days

        vacancy_data.append({
            'vacancy': v,
            'app_count': app_count,
            'committee_count': committee_count,
            'voted_count': voted_count,
            'all_voted': all_voted,
            'shortlist_generated': shortlist_generated,
            'threshold': threshold,
            'deadline': deadline,
            'days_remaining': days_remaining,
        })

    return render(request, 'recruitment/hr/shortlisting/vacancy_picker.html', {
        'page': 'Shortlisting',
        'vacancies': vacancy_data,
    })


# ----------------------
# Stage: Interviews
# ----------------------


# ----------------------
# Stage: Appointments (with panelists)
# ----------------------
@login_required
@role_required(['hod_hr'])
def vacancy_appointments(request):
    vacancies = Vacancy.objects.filter(status='appointed').prefetch_related('panelassignment_set__panelist')

    context = {
        'page': 'Human Resource Dashboard',
        'vacancies': vacancies
    }
    return render(request, 'recruitment/hr/vacancy_appointments.html', context)






@login_required
@role_required(['hod_hr'])
# ── Vacancy List (Published = all non-draft) ───────────────────────────────
def vacancy_list(request):
    vacancies = (
        Vacancy.objects
        .exclude(status='draft')
        .annotate(application_count=Count('jobapplication'))
        .order_by('-created_at')
    )
    context = {
        'page': 'Published Vacancies',
        'vacancies': vacancies,
    }
    return render(request, 'recruitment/hr/vacancy_list.html', context)


# ── Add to recruitment/views.py ────────────────────────────────
# Additional imports needed:
# from django.core.mail import send_mail
# from django.conf import settings
# from django.utils import timezone
# from .models import (..., Vacancy, JobApplication, JobApplicationStatus,
#                      JobApplicationStatusLog, JobApplicationNotification,
#                      VacancyApplicationCounter)

def _application_ready(user):
    issues = []
    profile = JobSeekerProfile.objects.filter(user=user).first()
    detail = AdditionalDetail.objects.filter(user=user).first()

    if not profile or not all([profile.first_name, profile.surname,
                               profile.date_of_birth, profile.phone_number,
                               profile.gender_id, profile.home_county_id]):
        issues.append({'label': 'Complete your basic details', 'url': 'profile', 'icon': 'fa-user'})

    if not AcademicQualification.objects.filter(user=user).exists():
        issues.append({'label': 'Add at least one academic qualification', 'url': 'academic_qualifications',
                       'icon': 'fa-graduation-cap'})

    if not WorkHistory.objects.filter(user=user).exists():
        issues.append({'label': 'Add your work history', 'url': 'work_history', 'icon': 'fa-briefcase'})

    if Referee.objects.filter(user=user).count() < 2:
        issues.append({'label': 'Add both referees', 'url': 'referees', 'icon': 'fa-user-tie'})

    if not detail or not detail.cv:
        issues.append({'label': 'Upload your CV', 'url': 'additional_details', 'icon': 'fa-file-pdf'})
    if not detail or not detail.cover_letter:
        issues.append({'label': 'Upload your cover letter', 'url': 'additional_details', 'icon': 'fa-file-alt'})
    if not detail or not detail.availability:
        issues.append({'label': 'Set your availability', 'url': 'additional_details', 'icon': 'fa-calendar-check'})


    return len(issues) == 0, issues


#     return render(request, 'recruitment/panelist/shortlist.html', {
#         'vacancy': vacancy,
#         'applications': applications
#     })


@login_required
@role_required(['hr', 'ceo'])  # CEO can view but not appoint
def hr_finalize_appointment(request, vacancy_id):
    vacancy = get_object_or_404(Vacancy, id=vacancy_id)

    if vacancy.status != 'ceo_approved':
        messages.error(request, "Vacancy not ready for appointment.")
        return redirect('hr_dashboard')

    selected_application = Application.objects.filter(
        vacancy=vacancy,
        ceo_selected=True
    ).first()

    if not selected_application:
        messages.error(request, "No CEO approved candidate found.")
        return redirect('hr_dashboard')

    if request.method == 'POST':

        # Appoint selected candidate
        selected_application.status = 'appointed'
        selected_application.save()

        # Send appointment notification
        _notify_appointment(selected_application.user, selected_application)

        # Reject all other applicants
        other_applications = Application.objects.filter(
            vacancy=vacancy
        ).exclude(
            id=selected_application.id
        )

        for application in other_applications:
            application.status = 'rejected'
            application.save()

        vacancy.status = 'appointed'
        vacancy.save()

        messages.success(request, "Candidate successfully appointed.")
        return redirect('hr_dashboard')

    return render(request, 'recruitment/hr/finalize_appointment.html', {
        'vacancy': vacancy,
        'selected_application': selected_application
    })


def _build_snapshots(user):
    profile = JobSeekerProfile.objects.filter(user=user).first()
    detail = AdditionalDetail.objects.filter(user=user).first()

    # ── Basic ──────────────────────────────────────────────────
    snap_basic = {}
    if profile:
        snap_basic = {
            'salutation': profile.salutation or '',
            'surname': profile.surname or '',
            'first_name': profile.first_name or '',
            'second_name': profile.second_name or '',
            'id_no': profile.id_no or '',
            'phone_number': profile.phone_number or '',
            'date_of_birth': str(profile.date_of_birth) if profile.date_of_birth else '',
            'gender': str(profile.gender) if profile.gender else '',
            'ethnic_group': str(profile.ethnic_group) if profile.ethnic_group else '',
            'home_county': str(profile.home_county) if profile.home_county else '',
            'constituency': str(profile.constituency) if profile.constituency else '',
            'sub_county': str(profile.sub_county) if profile.sub_county else '',
            'ward': str(profile.ward) if profile.ward else '',
            'disability_status': profile.disability_status or '',
            'disability_other': profile.disability_other or '',
            'disability_no': profile.disability_no or '',
            'employee_number': profile.employee_number or '',
        }

    # ── Academic ────────────────────────────────────────────────
    snap_academic = [
        {
            'education_level': str(q.education_level) if q.education_level else '',
            'institution': q.institution or '',
            'field_of_study': q.field_of_study or '',
            'country': q.country or '',
            'year_completed': q.year_completed,
            'grade': q.grade or '',
            'cert_number': q.cert_number or '',
            'documents': [
                {
                    'document_type': doc.document_type.name,
                    'unique_ref': doc.unique_ref,
                    'filename': doc.filename,  # uses your @property
                    'file_url': doc.file.url if doc.file else '',
                    'uploaded_at': str(doc.uploaded_at),
                }
                for doc in q.documents.all()
            ],
        }
        for q in AcademicQualification.objects.filter(user=user)
        .select_related('education_level')
        .prefetch_related('documents__document_type')  # ← avoids N+1
    ]

    # ── Professional ────────────────────────────────────────────
    snap_professional = [
        {
            'qualification': q.qualification or '',
            'awarding_body': q.awarding_body or '',
            'year_obtained': q.year_obtained,
            'expiry_year': q.expiry_year or '',
            'grade': q.grade or '',
            'cert_number': q.cert_number or '',
            'country': q.country or '',
            'documents': [
                {
                    'document_type': doc.document_type.name,
                    'unique_ref': doc.unique_ref,
                    'filename': doc.filename,
                    'file_url': doc.file.url if doc.file else '',
                    'uploaded_at': str(doc.uploaded_at),
                }
                for doc in q.documents.all()
            ],
        }
        for q in ProfessionalQualification.objects.filter(user=user)
        .prefetch_related('documents__document_type')  # ← avoids N+1
    ]

    # ── Work ────────────────────────────────────────────────────
    snap_work = [
        {
            'job_title': w.job_title or '',
            'company': w.company or '',
            'employment_type': w.employment_type or '',
            'start_display': w.start_display,
            'end_display': w.end_display if not w.is_current else 'Present',
            'is_current': w.is_current,
            'duties': w.duties or '',
            'exit_reason': w.exit_reason or '',
            'country': w.country or '',
        }
        for w in WorkHistory.objects.filter(user=user).order_by('-start_year', '-start_month')
    ]

    # ── Memberships ─────────────────────────────────────────────
    snap_memberships = [
        {
            'body_name': m.body_name or '',
            'membership_no': m.membership_no or '',
            'year_joined': m.year_joined,
            'expiry_year': m.expiry_year or '',
        }
        for m in ProfessionalBodyMembership.objects.filter(user=user)
    ]

    # ── Referees ────────────────────────────────────────────────
    snap_referees = [
        {
            'referee_no': r.referee_no,
            'name': r.name or '',
            'occupation': r.occupation or '',
            'mobile': r.mobile or '',
            'email': r.email or '',
            'organization':r.organization or '',
            'period_known': r.period_known or '',
        }
        for r in Referee.objects.filter(user=user).order_by('referee_no')
    ]

    # ── Supporting Documents ────────────────────────────────────
    # These are typed attachments (ID copy, cert scans, etc.) from
    # the Document model — stored separately from CV/cover letter.
    snap_documents = [
        {
            'document_type': doc.document_type.name,
            'unique_ref': doc.unique_ref,
            'file_url': doc.file.url if doc.file else '',
            'filename': doc.file.name.split('/')[-1] if doc.file else '',
            'uploaded_at': str(doc.uploaded_at),
        }
        for doc in Document.objects.filter(user=user).select_related('document_type')
    ]

    # ── Additional / Files ──────────────────────────────────────
    snap_additional = {}
    if detail:
        snap_additional = {
            'cv_filename': detail.cv.name.split('/')[-1] if detail.cv else '',
            'cv_url': detail.cv.url if detail.cv else '',  # ← store URL too
            'cover_letter_filename': detail.cover_letter.name.split('/')[-1] if detail.cover_letter else '',
            'cover_letter_url': detail.cover_letter.url if detail.cover_letter else '',  # ← store URL too
            'linkedin_url': detail.linkedin_url or '',
            'portfolio_url': detail.portfolio_url or '',
            'languages': detail.languages or '',
            'availability': detail.availability or '',
            'expected_salary': str(detail.expected_salary) if detail.expected_salary else '',
        }

    return {
        'basic': snap_basic,
        'academic': snap_academic,
        'professional': snap_professional,
        'work': snap_work,
        'memberships': snap_memberships,
        'referees': snap_referees,
        'documents': snap_documents,  # ← new
        'additional': snap_additional,
    }


def _send_html_email(subject, to_email, message_html):
    """Send a branded UFAA HTML email."""
    from django.template.loader import render_to_string
    from django.core.mail import EmailMultiAlternatives
    from datetime import date

    html_body = render_to_string('emails/email_base.html', {
        'subject': subject,
        'message_content': message_html,
        'logo_url': 'https://ufaa.go.ke//wp-content/uploads/2022/07/LOGO_RVSD-2-1.png',
        'year': date.today().year,
    })
    email = EmailMultiAlternatives(
        subject=subject,
        body='Please view this email in an HTML-capable email client.',
        from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@ufaa.go.ke'),
        to=[to_email],
    )
    email.attach_alternative(html_body, 'text/html')
    email.send(fail_silently=False)


def _notify_submission(user, application):
    vacancy = application.vacancy

    # 1. In-app notification
    msg = (
        f'Your application for {vacancy.title} has been received. '
        f'Application No: {application.application_number}. '
        f'We will be in touch regarding next steps.'
    )
    JobApplicationNotification.objects.create(
        user=user,
        title=f'Application Submitted — {application.application_number}',
        message=msg,
        notification_type='application_submitted',
        related_application=application,
    )

    # 2. HTML email
    try:
        profile = getattr(user, 'jobseekerprofile', None)
        first_name = profile.first_name if profile and profile.first_name else ''
        second_name = profile.second_name if profile and profile.second_name else ''
        surname = profile.surname if profile and profile.surname else ''
        full_name = ' '.join(filter(None, [first_name, second_name, surname])) or 'Applicant'
        site_url = getattr(settings, 'SITE_URL', 'http://127.0.0.1:8000')

        message_html = f"""
            <p>Dear <strong>{full_name}</strong>,</p>
            <p>Thank you for submitting your application for the position of
               <strong>{vacancy.title}</strong>
               (Vacancy Reference: <strong>{vacancy.reference_number}</strong>).</p>

            <table width="100%" cellpadding="0" cellspacing="0" role="presentation"
                   style="background:#f0f4ff; border:1px solid #c7d2fe;
                          border-radius:8px; margin:16px 0;">
                <tr>
                    <td style="padding:16px 20px;">
                        <p style="margin:0 0 4px; font-size:11px; color:#6b7280;
                                  text-transform:uppercase; letter-spacing:0.05em;">
                            Your Application Number
                        </p>
                        <p style="margin:0; font-size:22px; font-weight:700;
                                  color:#1D255B; letter-spacing:0.5px;">
                            {application.application_number}
                        </p>
                        <p style="margin:6px 0 0; font-size:12px; color:#6b7280;">
                            Please quote this number in all correspondence with UFAA HR.
                        </p>
                    </td>
                </tr>
            </table>

            <p>Your application has been received and is currently under review by the
               UFAA Human Resources team. You will be notified of any updates through
               the portal and via email.</p>
            <p>You can track your application status anytime by logging into the
               <a href='{site_url}/recruitment/job-status/'
                  style='color:#1D255B;font-weight:bold;'>UFAA Job Portal</a>.</p>
            <br>
            <p style='margin:0;'>Regards,</p>
            <p style='margin:0;'><strong>UFAA Human Resources</strong></p>
            <p style='margin:0;color:#67748e;font-size:13px;'>Unclaimed Financial Assets Authority</p>
        """

        _send_html_email(
            subject=f'Application Received — {application.application_number} | {vacancy.title}',
            to_email=user.email,
            message_html=message_html,
        )
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f'Email send failed for {user.email}: {e}')


def _notify_appointment(user, application):
    vacancy = application.vacancy

    # 1. In-app notification
    msg = (
        f'Congratulations! You have been appointed for the position of {vacancy.title}. '
        f'Application No: {application.application_number}. '
        f'Please log into the portal for further instructions.'
    )

    JobApplicationNotification.objects.create(
        user=user,
        title=f'Appointment Notification — {vacancy.title}',
        message=msg,
        notification_type='appointment',
        related_application=application,
    )

    # 2. HTML Email
    try:
        profile = getattr(user, 'jobseekerprofile', None)

        first_name = profile.first_name if profile and profile.first_name else ''
        second_name = profile.second_name if profile and profile.second_name else ''
        surname = profile.surname if profile and profile.surname else ''

        full_name = ' '.join(filter(None, [first_name, second_name, surname])) or 'Applicant'

        site_url = getattr(settings, 'SITE_URL', 'http://127.0.0.1:8000')

        message_html = f"""
            <p>Dear <strong>{full_name}</strong>,</p>

            <p>We are pleased to inform you that following the completion of the
            recruitment process for the position of
            <strong>{vacancy.title}</strong>
            (Vacancy Reference: <strong>{vacancy.reference_number}</strong>),
            you have been <strong>successfully selected for appointment</strong>.</p>

            <table width="100%" cellpadding="0" cellspacing="0" role="presentation"
                   style="background:#f0f4ff; border:1px solid #c7d2fe;
                          border-radius:8px; margin:16px 0;">
                <tr>
                    <td style="padding:16px 20px;">
                        <p style="margin:0 0 4px; font-size:11px; color:#6b7280;
                                  text-transform:uppercase; letter-spacing:0.05em;">
                            Application Number
                        </p>
                        <p style="margin:0; font-size:22px; font-weight:700;
                                  color:#1D255B; letter-spacing:0.5px;">
                            {application.application_number}
                        </p>
                    </td>
                </tr>
            </table>

            <p>The UFAA Human Resources Department will contact you shortly with
            further instructions regarding your appointment and onboarding process.</p>

            <p>You may also log into the
            <a href='{site_url}/recruitment/job-status/'
               style='color:#1D255B;font-weight:bold;'>UFAA Job Portal</a>
            to view your application status.</p>

            <br>

            <p style='margin:0;'>Congratulations and welcome.</p>
            <p style='margin:0;'><strong>UFAA Human Resources</strong></p>
            <p style='margin:0;color:#67748e;font-size:13px;'>Unclaimed Financial Assets Authority</p>
        """

        _send_html_email(
            subject=f'Appointment Notification — {vacancy.title}',
            to_email=user.email,
            message_html=message_html,
        )

    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f'Appointment email failed for {user.email}: {e}')


def apply_jobs_view(request):
    user_id = request.session.get('user_id')
    if not user_id:
        return redirect('index')
    user = JobseekerAccount.objects.filter(pk=user_id).first()
    if not user:
        request.session.flush()
        return redirect('index')

    profile = JobSeekerProfile.objects.filter(user=user).first()
    completion = calculate_profile_completion(user)
    is_ready, readiness_issues = _application_ready(user)

    if request.method == 'POST':
        vacancy_id = request.POST.get('vacancy_id', '').strip()
        try:
            ready, issues = _application_ready(user)
            if not ready:
                return JsonResponse({'status': 'error',
                                     'message': 'Your profile is incomplete. Please address all required sections before applying.'})

            vacancy = Vacancy.objects.filter(id=vacancy_id).first()
            if not vacancy:
                return JsonResponse({'status': 'error', 'message': 'Vacancy not found.'})
            if not vacancy.is_open():
                return JsonResponse({'status': 'error', 'message': 'This vacancy is no longer open for applications.'})
            if vacancy.vacancy_type == 'internal' and not user.is_employee:
                return JsonResponse({'status': 'error', 'message': 'This vacancy is only open to UFAA employees.'})
            if JobApplication.objects.filter(user=user, vacancy=vacancy).exists():
                return JsonResponse({'status': 'error', 'message': 'You have already applied for this position.'})

            submitted_status = JobApplicationStatus.objects.filter(code='submitted').first()
            if not submitted_status:
                return JsonResponse(
                    {'status': 'error', 'message': 'System configuration error. Please contact support.'})

            snaps = _build_snapshots(user)

            # ── Generate atomic application number ──────────────────
            from django.db import transaction
            with transaction.atomic():
                counter, _ = VacancyApplicationCounter.objects.select_for_update().get_or_create(
                    vacancy=vacancy
                )
                counter.last_number += 1
                counter.save()
                seq = str(counter.last_number).zfill(3)
                application_number = f"{vacancy.reference_number}/{seq}"

                application = JobApplication.objects.create(
                    user=user,
                    vacancy=vacancy,
                    status=submitted_status,
                    application_number=application_number,
                    snapshot_basic=snaps['basic'],
                    snapshot_academic=snaps['academic'],
                    snapshot_professional=snaps['professional'],
                    snapshot_work=snaps['work'],
                    snapshot_memberships=snaps['memberships'],
                    snapshot_referees=snaps['referees'],
                    snapshot_additional=snaps['additional'],
                )

            JobApplicationStatusLog.objects.create(
                application=application,
                from_status=None,
                to_status=submitted_status,
                notes='Application submitted by applicant.',
            )
            _notify_submission(user, application)

            return JsonResponse({'status': 'success',
                                 'message': f'Your application for {vacancy.title} has been submitted successfully.',
                                 'application_number': application_number})

        except Exception as e:
            logger.exception("Error while submitting application")
            return JsonResponse({
                'status': 'error',
                'message': 'An unexpected error occurred while submitting your application. Please try again later.'
            })

    def _parse_vacancy_fields(description):
        """Parse vacancy description into structured fields for card display."""
        if not description:
            return [], ''

        # 1. Produce clean snippet (strip all markdown)
        clean = re.sub(r'\*+', '', description)
        clean = re.sub(r'#{1,6}\s*', '', clean)
        clean = re.sub(r'---+', '', clean)
        clean = re.sub(r'\s+', ' ', clean).strip()
        snippet = (clean[:120] + '\u2026') if len(clean) > 120 else clean

        # 2. For field parsing, only use the header block (before ---, ###, or blank lines)
        # Split on section dividers to isolate the key-value header block
        header_block = re.split(r'(---|#{1,6}|\n\s*\n)', description)[0]
        header_clean = re.sub(r'\*+', '', header_block)
        header_clean = re.sub(r'\s+', ' ', header_clean).strip()

        field_map = [
            ('JOB TITLE', 'Position', 'fa-briefcase'),
            ('LOCATION', 'Location', 'fa-map-marker-alt'),
            ('EMPLOYMENT TYPE', 'Employment Type', 'fa-clock'),
            ('DEPARTMENT', 'Department', 'fa-building'),
            ('SALARY SCALE', 'Salary Scale', 'fa-money-bill-wave'),
            ('REPORTS TO', 'Reports To', 'fa-sitemap'),
            ('DIVISION', 'Division', 'fa-layer-group'),
        ]

        # Match ALL-CAPS KEY: value, stopping at next ALL-CAPS KEY: or end
        kv_pattern = re.compile(
            r'([A-Z][A-Z ]{2,25}?)\s*:\s*(.+?)(?=\s+[A-Z][A-Z ]{2,25}?\s*:|\Z)',
            re.DOTALL
        )
        found = {}
        for m in kv_pattern.finditer(header_clean):
            key = m.group(1).strip()
            val = re.sub(r'\s+', ' ', m.group(2)).strip()
            if key and val and len(key) <= 28:
                found[key] = val

        result = []
        for fkey, label, icon in field_map:
            val = found.get(fkey)
            if not val:
                for k, v in found.items():
                    if fkey in k or k in fkey:
                        val = v
                        break
            if val:
                if len(val) > 45:
                    val = val[:43] + '\u2026'
                result.append((label, icon, val))

        return result, snippet

    today = timezone.now().date()
    vacancies_qs = Vacancy.objects.filter(
        status='open',
        start_date__lte=today,
        end_date__gte=today,
    ).order_by('end_date')
    if not user.is_employee:
        vacancies_qs = vacancies_qs.filter(vacancy_type='external')

    vacancies = list(vacancies_qs)
    for v in vacancies:
        v.parsed_fields, v.plain_snippet = _parse_vacancy_fields(v.description)
        print(f"[DEBUG] {v.title} | parsed_fields={v.parsed_fields} | snippet={v.plain_snippet[:60]!r}")

    applied_ids = set(JobApplication.objects.filter(user=user).values_list('vacancy_id', flat=True))
    snaps = _build_snapshots(user)
    detail = AdditionalDetail.objects.filter(user=user).first()
    ref1 = Referee.objects.filter(user=user, referee_no=1).first()
    ref2 = Referee.objects.filter(user=user, referee_no=2).first()

    context = {
        'user': user, 'profile': profile, 'completion': completion,
        'vacancies': vacancies, 'applied_ids': applied_ids,
        'is_ready': is_ready, 'readiness_issues': readiness_issues,
        'snap_academic_count': len(snaps['academic']),
        'snap_professional_count': len(snaps['professional']),
        'snap_work_count': len(snaps['work']),
        'snap_memberships_count': len(snaps['memberships']),
        'ref1': ref1, 'ref2': ref2, 'detail': detail,
        'has_academic': AcademicQualification.objects.filter(user=user).exists(),
        'has_professional': ProfessionalQualification.objects.filter(user=user).exists(),
        'has_work_history': WorkHistory.objects.filter(user=user).exists(),
        'has_memberships': ProfessionalBodyMembership.objects.filter(user=user).exists(),
        'has_referees': Referee.objects.filter(user=user).count() >= 2,
        'has_additional': detail is not None,
        'page': 'Apply for Jobs',
    }
    return render(request, 'Jobseekers/apply_jobs.html', context)


def job_status_view(request):
    user_id = request.session.get('user_id')
    if not user_id:
        return redirect('index')
    user = JobseekerAccount.objects.filter(pk=user_id).first()
    if not user:
        request.session.flush()
        return redirect('index')

    profile = JobSeekerProfile.objects.filter(user=user).first()
    completion = calculate_profile_completion(user)
    detail = AdditionalDetail.objects.filter(user=user).first()

    applications = (
        JobApplication.objects
        .filter(user=user)
        .select_related('vacancy', 'status')
        .prefetch_related('status_logs__to_status', 'status_logs__from_status')
        .order_by('-submitted_at')
    )

    JobApplicationNotification.objects.filter(user=user, is_read=False).update(is_read=True)

    context = {
        'user': user, 'profile': profile, 'detail': detail,
        'completion': completion, 'applications': applications,
        'has_academic': AcademicQualification.objects.filter(user=user).exists(),
        'has_professional': ProfessionalQualification.objects.filter(user=user).exists(),
        'has_work_history': WorkHistory.objects.filter(user=user).exists(),
        'has_memberships': ProfessionalBodyMembership.objects.filter(user=user).exists(),
        'has_referees': Referee.objects.filter(user=user).count() >= 2,
        'has_additional': detail is not None,
        'page': 'Job Status',
    }
    return render(request, 'Jobseekers/job_status.html', context)


def mark_notification_read_view(request):
    """AJAX: mark one or all notifications as read, return new unread count."""
    user_id = request.session.get('user_id')
    if not user_id or request.method != 'POST':
        return JsonResponse({'status': 'error'}, status=400)

    notif_id = request.POST.get('notif_id')  # blank = mark ALL read

    if notif_id:
        JobApplicationNotification.objects.filter(
            id=notif_id, user_id=user_id
        ).update(is_read=True)
    else:
        JobApplicationNotification.objects.filter(
            user_id=user_id, is_read=False
        ).update(is_read=True)

    unread = JobApplicationNotification.objects.filter(
        user_id=user_id, is_read=False
    ).count()

    return JsonResponse({'status': 'ok', 'unread_count': unread})


def notification_poll_view(request):
    """Lightweight polling endpoint — returns unread count + latest unseen notifs."""
    user_id = request.session.get('user_id')
    if not user_id:
        return JsonResponse({'unread_count': 0, 'notifications': []})

    unread = JobApplicationNotification.objects.filter(
        user_id=user_id, is_read=False
    ).count()

    # Return latest 10 for dropdown refresh
    notifs = list(
        JobApplicationNotification.objects
        .filter(user_id=user_id)
        .order_by('-created_at')[:10]
        .values('id', 'title', 'message', 'notification_type', 'is_read', 'created_at')
    )

    # Make created_at JSON serializable
    for n in notifs:
        n['created_at'] = n['created_at'].strftime('%d %b %Y, %H:%M')

    return JsonResponse({'unread_count': unread, 'notifications': notifs})


"""
recruitment/views_longlisting.py

Manual longlisting views for UFAA recruitment portal.

URL patterns to add to recruitment/urls.py:
    path('hr/vacancy/<int:vacancy_id>/longlist/',
         views.hr_longlist_dashboard, name='hr_longlist_dashboard'),
    path('hr/vacancy/<int:vacancy_id>/longlist/<int:app_id>/',
         views.hr_longlist_dossier, name='hr_longlist_dossier'),
    path('hr/vacancy/<int:vacancy_id>/longlist/<int:app_id>/decision/',
         views.hr_longlist_decision, name='hr_longlist_decision'),
    path('hr/vacancy/<int:vacancy_id>/longlist/bulk/',
         views.hr_longlist_bulk, name='hr_longlist_bulk'),
    path('hr/vacancy/<int:vacancy_id>/longlist/<int:app_id>/recall/',
         views.hr_longlist_recall, name='hr_longlist_recall'),
    path('hr/vacancy/<int:vacancy_id>/longlist/finalise/',
         views.hr_longlist_finalise, name='hr_longlist_finalise'),

Decisions:
    accepted  — HR accepts into final longlist
    rejected  — HR rejects (immediate regret email + not_selected status)

Finalise:
    Accepted  → final_longlisted (presented to shortlisting committee)
    Remaining rejected → not_selected (already done immediately)
    Vacancy   → committee_stage
"""

from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import (
    JobApplication,
    JobApplicationStatus,
    JobApplicationStatusLog,
    LonglistReviewLog,
    Vacancy,
)


# ── Helpers ────────────────────────────────────────────────────────────────

def _status(code):
    return JobApplicationStatus.objects.filter(code=code).first()


def _get_filter_queryset(vacancy, params):
    """Return filtered queryset for the given tab and filter params."""
    tab = params.get('tab', 'active')

    if tab == 'rejected':
        # System-rejected — for recall
        qs = JobApplication.objects.filter(
            vacancy=vacancy,
            status=_status('not_selected'),
        )
    else:
        qs = JobApplication.objects.filter(
            vacancy=vacancy,
            status=_status('longlisted'),
        )

    gender = params.get('gender', '')
    if gender:
        qs = qs.filter(snapshot_basic__gender__iexact=gender)

    disability = params.get('disability', '')
    if disability == 'yes':
        # disability_status stored as string e.g. "Yes", "None", "No"
        qs = qs.exclude(
            snapshot_basic__disability_status__in=['None', 'No', 'no', '', None]
        )
    elif disability == 'no':
        qs = qs.filter(
            snapshot_basic__disability_status__in=['None', 'No', 'no', '', None]
        )

    county = params.get('county', '')
    if county:
        qs = qs.filter(snapshot_basic__home_county__icontains=county)

    screening = params.get('screening', '')
    if screening == 'passed':
        qs = qs.filter(screening_passed=True)
    elif screening == 'flagged':
        qs = qs.filter(screening_passed=True).exclude(screening_flags=[])

    decision = params.get('decision', '')
    if decision == 'unreviewed':
        qs = qs.filter(longlist_decision__isnull=True)
    elif decision in ['accepted', 'rejected']:
        qs = qs.filter(longlist_decision=decision)

    return qs.select_related('user', 'status').order_by('application_number')


def _build_filter_params(params):
    keys = ['tab', 'gender', 'disability', 'county', 'screening', 'decision']
    return {k: params.get(k, '') for k in keys if params.get(k, '')}


def _extract_basic(app):
    b = app.snapshot_basic or {}
    return {
        'full_name': ' '.join(filter(None, [
            b.get('first_name', ''),
            b.get('second_name', ''),
            b.get('surname', ''),
        ])) or app.user.email,
        'id_no': b.get('id_no', '—'),
        'dob': b.get('date_of_birth', '—'),
        'gender': b.get('gender', '—'),
        'phone': b.get('phone_number', '—'),
        'county': b.get('home_county', '—'),
        'subcounty': b.get('sub_county', '—'),
        'constituency': b.get('constituency', '—'),
        'ward': b.get('ward', '—'),
        'disability': b.get('disability_status') not in (None, '', 'None', 'No', 'no', False),
        'ethnicity': b.get('ethnic_group', '—'),
    }


def _parse_date(s):
    from datetime import datetime
    if not s:
        return None
    for fmt in ('%Y-%m-%d', '%Y-%m', '%B %Y', '%b %Y', '%Y'):
        try:
            return datetime.strptime(str(s).strip(), fmt).date()
        except ValueError:
            continue
    return None


def _calculate_experience(work_list):
    if not work_list:
        return 0, 0
    today = date.today()
    total = 0
    for job in work_list:
        try:
            start_str = job.get('start_display') or job.get('start_date') or ''
            end_str = job.get('end_display') or job.get('end_date') or ''
            if not start_str:
                continue
            start = _parse_date(start_str)
            if not start:
                continue
            end = today if (not end_str or end_str.lower() in ('present', '—')) \
                else (_parse_date(end_str) or today)
            if end >= start:
                total += max((end.year - start.year) * 12 + (end.month - start.month), 0)
        except (ValueError, TypeError):
            continue
    return total // 12, total % 12


def _highest_edu(academic):
    """Return highest education_level string from snapshot_academic list."""
    if not academic:
        return '—'
    # Education level rank map — same as screening engine
    RANKS = {
        'kenya certificate of primary education (kcpe)': 1, 'kcpe': 1,
        'kenya certificate of secondary education (kcse)': 2, 'kcse': 2,
        'o-levels': 2, 'o levels': 2, 'igcse': 2, 'ged': 2,
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
    best_rank = -1
    best_label = '—'
    for entry in academic:
        label = entry.get('education_level', '')
        rank = RANKS.get(label.strip().lower(), 0)
        if rank > best_rank:
            best_rank = rank
            best_label = label
    return best_label or '—'


def _send_regret_email(app, vacancy):
    """Send regret email for HR manual rejection."""
    try:
        from django.template.loader import render_to_string
        from django.core.mail import EmailMultiAlternatives
        from django.conf import settings

        b = app.snapshot_basic or {}
        name = ' '.join(filter(None, [b.get('first_name', ''), b.get('surname', '')])) \
               or app.user.email

        subject = (f"Application Outcome — {vacancy.title} "
                   f"({vacancy.reference_number})")

        message_html = f"""
        <p>Dear <strong>{name}</strong>,</p>

        <p>Thank you for your interest in the position of
        <strong>{vacancy.title}</strong>
        (Ref: <span style="font-family:monospace;">{vacancy.reference_number}</span>)
        at the Unclaimed Financial Assets Authority (UFAA).</p>

        <p>Following a careful review of all applications received, we regret to
        inform you that your application has <strong>not been successful</strong>
        at this stage of the recruitment process.</p>

        <p>We appreciate the time and effort you invested in your application and
        encourage you to apply for future opportunities that match your
        qualifications and experience.</p>

        <p style="margin-top:24px; color:#6b7280; font-size:13px;">
            Yours sincerely,<br>
            <strong style="color:#1D255B;">Human Resources &amp; Administration</strong><br>
            Unclaimed Financial Assets Authority (UFAA)
        </p>
        """

        html_body = render_to_string('emails/email_base.html', {
            'subject': subject,
            'message_content': message_html,
            'year': date.today().year,
        })

        msg = EmailMultiAlternatives(
            subject=subject,
            body='Please view this email in an HTML-capable client.',
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@ufaa.go.ke'),
            to=[app.user.email],
        )
        msg.attach_alternative(html_body, 'text/html')
        msg.send(fail_silently=True)
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(
            f"Regret email failed for app {app.id}: {e}", exc_info=True)


def _send_recall_email(app, vacancy):
    """Send reconsideration email when system-rejected app is recalled."""
    try:
        from django.template.loader import render_to_string
        from django.core.mail import EmailMultiAlternatives
        from django.conf import settings

        b = app.snapshot_basic or {}
        name = ' '.join(filter(None, [b.get('first_name', ''), b.get('surname', '')])) \
               or app.user.email

        subject = (f"Application Update — {vacancy.title} "
                   f"({vacancy.reference_number})")

        message_html = f"""
        <p>Dear <strong>{name}</strong>,</p>

        <p>We are writing to inform you that your application for the position of
        <strong>{vacancy.title}</strong>
        (Ref: <span style="font-family:monospace;">{vacancy.reference_number}</span>)
        has been <strong style="color:#1a7a45;">reconsidered</strong>.</p>

        <p>Your application is now back under active consideration. You will
        receive further communication regarding the next steps in the
        recruitment process.</p>

        <p style="margin-top:24px; color:#6b7280; font-size:13px;">
            Yours sincerely,<br>
            <strong style="color:#1D255B;">Human Resources &amp; Administration</strong><br>
            Unclaimed Financial Assets Authority (UFAA)
        </p>
        """

        html_body = render_to_string('emails/email_base.html', {
            'subject': subject,
            'message_content': message_html,
            'logo_url': 'https://ufaa.go.ke/wp-content/uploads/2022/07/LOGO_RVSD-2-1.png',
            'year': date.today().year,
        })

        msg = EmailMultiAlternatives(
            subject=subject,
            body='Please view this email in an HTML-capable client.',
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@ufaa.go.ke'),
            to=[app.user.email],
        )
        msg.attach_alternative(html_body, 'text/html')
        msg.send(fail_silently=True)
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(
            f"Recall email failed for app {app.id}: {e}", exc_info=True)


# ── View 1: Dashboard ──────────────────────────────────────────────────────

@login_required
@role_required(['hod_hr', 'panelist'])
def hr_longlist_dashboard(request, vacancy_id):
    vacancy = get_object_or_404(Vacancy, id=vacancy_id, status='longlisting')

    longlisted_st = _status('longlisted')
    not_selected_st = _status('not_selected')

    total_longlisted = JobApplication.objects.filter(
        vacancy=vacancy, status=longlisted_st).count()
    total_accepted = JobApplication.objects.filter(
        vacancy=vacancy, status=longlisted_st,
        longlist_decision='accepted').count()
    total_rejected = JobApplication.objects.filter(
        vacancy=vacancy, status=longlisted_st,
        longlist_decision='rejected').count()
    total_unreviewed = JobApplication.objects.filter(
        vacancy=vacancy, status=longlisted_st,
        longlist_decision__isnull=True).count()
    total_sys_rejected = JobApplication.objects.filter(
        vacancy=vacancy, status=not_selected_st).count()

    qs = _get_filter_queryset(vacancy, request.GET)

    applications = []
    for app in qs:
        yrs, mo = _calculate_experience(app.snapshot_work or [])
        applications.append({
            'app': app,
            'basic': _extract_basic(app),
            'exp_years': yrs,
            'exp_months': mo,
            'highest_edu': _highest_edu(app.snapshot_academic or []),
        })

    filter_params = _build_filter_params(request.GET)
    filter_query = '&'.join(f"{k}={v}" for k, v in filter_params.items())

    context = {
        'vacancy': vacancy,
        'applications': applications,
        'filter_query': filter_query,
        'filter_params': filter_params,
        'active_tab': request.GET.get('tab', 'active'),
        'total_longlisted': total_longlisted,
        'total_accepted': total_accepted,
        'total_rejected': total_rejected,
        'total_unreviewed': total_unreviewed,
        'total_sys_rejected': total_sys_rejected,
        'gender_choices': [('Male', 'Male'), ('Female', 'Female'), ('Other', 'Other')],
        'decision_choices': [('unreviewed', 'Unreviewed'),
                             ('accepted', 'Accepted'),
                             ('rejected', 'Rejected')],
    }
    return render(request, 'recruitment/hr/longlisting/dashboard.html', context)


# ── View 2: Dossier ────────────────────────────────────────────────────────

@login_required
@role_required(['hod_hr', 'panelist'])
def hr_longlist_dossier(request, vacancy_id, app_id):
    vacancy = get_object_or_404(Vacancy, id=vacancy_id, status='longlisting')
    app = get_object_or_404(JobApplication, id=app_id, vacancy=vacancy)

    qs = _get_filter_queryset(vacancy, request.GET)
    app_ids = list(qs.values_list('id', flat=True))
    filter_params = _build_filter_params(request.GET)
    filter_query = '&'.join(f"{k}={v}" for k, v in filter_params.items())

    try:
        current_idx = app_ids.index(app_id)
    except ValueError:
        current_idx = None

    prev_id = app_ids[current_idx - 1] if current_idx not in (None, 0) else None
    next_id = app_ids[current_idx + 1] if (
            current_idx is not None and current_idx < len(app_ids) - 1) else None
    position = (current_idx + 1) if current_idx is not None else None

    LonglistReviewLog.objects.create(
        vacancy=vacancy, application=app,
        officer=request.user, action='viewed',
        metadata={'filter_params': filter_params},
    )

    yrs, mo = _calculate_experience(app.snapshot_work or [])

    context = {
        'vacancy': vacancy,
        'app': app,
        'basic': _extract_basic(app),
        'academic': app.snapshot_academic or [],
        'professional': app.snapshot_professional or [],
        'work': app.snapshot_work or [],
        'referees': app.snapshot_referees or [],
        'additional': app.snapshot_additional or {},
        'memberships': app.snapshot_memberships or [],
        'exp_years': yrs,
        'exp_months': mo,
        'prev_id': prev_id,
        'next_id': next_id,
        'position': position,
        'total': len(app_ids),
        'filter_query': filter_query,
        'filter_params': filter_params,
        'active_tab': request.GET.get('tab', 'active'),
        'gender_choices': [('Male', 'Male'), ('Female', 'Female'), ('Other', 'Other')],
        'decision_choices': [('unreviewed', 'Unreviewed'),
                             ('accepted', 'Accepted'),
                             ('rejected', 'Rejected')],
    }
    return render(request, 'recruitment/hr/longlisting/dossier.html', context)


# ── View 3: Decision ───────────────────────────────────────────────────────

@login_required
@role_required(['hod_hr', 'panelist'])
@require_POST
def hr_longlist_decision(request, vacancy_id, app_id):
    vacancy = get_object_or_404(Vacancy, id=vacancy_id, status='longlisting')
    app = get_object_or_404(JobApplication, id=app_id, vacancy=vacancy)

    decision = request.POST.get('decision', '').strip()
    notes = request.POST.get('notes', '').strip()
    filter_query = request.POST.get('filter_query', '')

    if decision not in ['accepted', 'rejected']:
        return JsonResponse({'error': 'Invalid decision.'}, status=400)

    if decision == 'rejected' and not notes:
        return JsonResponse(
            {'error': 'A reason is required when rejecting.'}, status=400)

    previous_decision = app.longlist_decision
    action = 'decision_changed' if previous_decision else decision

    with transaction.atomic():
        app.longlist_decision = decision
        app.longlist_decision_by = request.user
        app.longlist_decision_at = timezone.now()
        app.longlist_notes = notes

        if decision == 'rejected':
            # Immediately move to not_selected
            not_selected_st = _status('not_selected')
            previous_status = app.status
            app.status = not_selected_st
            app.save(update_fields=[
                'longlist_decision', 'longlist_decision_by',
                'longlist_decision_at', 'longlist_notes', 'status',
            ])
            JobApplicationStatusLog.objects.create(
                application=app,
                from_status=previous_status,
                to_status=not_selected_st,
                changed_by=request.user,
                notes=f"Rejected during manual longlisting. Reason: {notes}",
            )
        else:
            app.save(update_fields=[
                'longlist_decision', 'longlist_decision_by',
                'longlist_decision_at', 'longlist_notes',
            ])

        LonglistReviewLog.objects.create(
            vacancy=vacancy, application=app,
            officer=request.user, action=action, notes=notes,
            metadata={
                'decision': decision,
                'previous_decision': previous_decision,
                'screening_passed': app.screening_passed,
            },
        )

    # Send regret email immediately on rejection (outside transaction)
    if decision == 'rejected':
        _send_regret_email(app, vacancy)

    return JsonResponse({'success': True, 'decision': decision, 'app_id': app_id})


# ── View 4: Bulk Action ────────────────────────────────────────────────────

@login_required
@role_required(['hod_hr', 'panelist'])
@require_POST
def hr_longlist_bulk(request, vacancy_id):
    vacancy = get_object_or_404(Vacancy, id=vacancy_id, status='longlisting')

    action = request.POST.get('action', '').strip()
    app_ids = request.POST.getlist('app_ids')
    notes = request.POST.get('notes', '').strip()

    if action not in ['accepted', 'rejected']:
        return JsonResponse({'error': 'Invalid action.'}, status=400)
    if not app_ids:
        return JsonResponse({'error': 'No applications selected.'}, status=400)
    if action == 'rejected' and not notes:
        return JsonResponse(
            {'error': 'A reason is required for bulk rejection.'}, status=400)

    apps = JobApplication.objects.filter(id__in=app_ids, vacancy=vacancy)
    updated_ids = list(apps.values_list('id', flat=True))
    count = len(updated_ids)

    with transaction.atomic():
        if action == 'rejected':
            not_selected_st = _status('not_selected')
            for app in apps:
                previous_status = app.status
                app.longlist_decision = 'rejected'
                app.longlist_decision_by = request.user
                app.longlist_decision_at = timezone.now()
                app.longlist_notes = notes
                app.status = not_selected_st
                app.save(update_fields=[
                    'longlist_decision', 'longlist_decision_by',
                    'longlist_decision_at', 'longlist_notes', 'status',
                ])
                JobApplicationStatusLog.objects.create(
                    application=app, from_status=previous_status,
                    to_status=not_selected_st, changed_by=request.user,
                    notes=f"Bulk rejected during manual longlisting. Reason: {notes}",
                )
        else:
            apps.update(
                longlist_decision='accepted',
                longlist_decision_by=request.user,
                longlist_decision_at=timezone.now(),
                longlist_notes=notes,
            )

        LonglistReviewLog.objects.create(
            vacancy=vacancy, application=None,
            officer=request.user, action=f'bulk_{action}', notes=notes,
            metadata={'count': count, 'application_ids': updated_ids, 'decision': action},
        )

    # Send regret emails after transaction
    if action == 'rejected':
        for app in JobApplication.objects.filter(id__in=updated_ids):
            _send_regret_email(app, vacancy)

    return JsonResponse({'success': True, 'count': count, 'action': action})


# ── View 5: Recall ─────────────────────────────────────────────────────────

@login_required
@role_required(['hod_hr', 'panelist'])
@require_POST
def hr_longlist_recall(request, vacancy_id, app_id):
    vacancy = get_object_or_404(Vacancy, id=vacancy_id, status='longlisting')
    app = get_object_or_404(JobApplication, id=app_id, vacancy=vacancy)

    notes = request.POST.get('notes', '').strip()
    if not notes:
        return JsonResponse(
            {'error': 'A reason for reconsideration is required.'}, status=400)

    longlisted_st = _status('longlisted')
    previous_status = app.status

    with transaction.atomic():
        app.status = longlisted_st
        app.longlist_decision = None
        app.longlist_decision_by = None
        app.longlist_decision_at = None
        app.longlist_notes = ''
        app.save(update_fields=[
            'status', 'longlist_decision', 'longlist_decision_by',
            'longlist_decision_at', 'longlist_notes',
        ])
        JobApplicationStatusLog.objects.create(
            application=app, from_status=previous_status,
            to_status=longlisted_st, changed_by=request.user,
            notes=f"Recalled for reconsideration by HR. Reason: {notes}",
        )
        LonglistReviewLog.objects.create(
            vacancy=vacancy, application=app,
            officer=request.user, action='override', notes=notes,
            metadata={
                'previous_status': previous_status.code if previous_status else None,
                'original_screening': app.screening_reasons,
            },
        )

    _send_recall_email(app, vacancy)
    return JsonResponse({'success': True, 'app_id': app_id})


# ── View 6: Finalise Longlist ──────────────────────────────────────────────

@login_required
@role_required(['hod_hr', 'panelist'])
@require_POST
def hr_longlist_finalise(request, vacancy_id):
    vacancy = get_object_or_404(Vacancy, id=vacancy_id, status='longlisting')

    longlisted_st = _status('longlisted')
    final_longlisted_st = _status('final_longlisted')
    not_selected_st = _status('not_selected')

    if not final_longlisted_st:
        return JsonResponse(
            {'error': 'final_longlisted status not found. Run migrations.'}, status=500)

    # Guard: block if any applications are still unreviewed
    unreviewed_count = JobApplication.objects.filter(
        vacancy=vacancy,
        status=longlisted_st,
        longlist_decision__isnull=True,
    ).count()

    if unreviewed_count > 0:
        return JsonResponse({
            'error': (f'{unreviewed_count} application(s) still unreviewed. '
                      f'Please accept or reject all applications before finalising.'),
            'unreviewed_count': unreviewed_count,
        }, status=400)

    accepted_apps = JobApplication.objects.filter(
        vacancy=vacancy,
        status=longlisted_st,
        longlist_decision='accepted',
    )
    accepted_count = accepted_apps.count()

    if accepted_count == 0:
        return JsonResponse({
            'error': 'No applications have been accepted into the final longlist.',
        }, status=400)

    with transaction.atomic():
        # Move accepted → final_longlisted
        for app in accepted_apps:
            previous_status = app.status
            app.status = final_longlisted_st
            app.save(update_fields=['status'])
            JobApplicationStatusLog.objects.create(
                application=app, from_status=previous_status,
                to_status=final_longlisted_st, changed_by=request.user,
                notes="Accepted into final longlist by HR. Proceeding to shortlisting committee.",
            )

        # Move vacancy to committee_stage
        vacancy.status = 'committee_stage'
        vacancy.save(update_fields=['status'])

        LonglistReviewLog.objects.create(
            vacancy=vacancy, application=None,
            officer=request.user, action='finalised',
            notes=f"Longlist finalised. {accepted_count} application(s) accepted.",
            metadata={
                'accepted_count': accepted_count,
                'finalised_by': request.user.full_name or request.user.email,
                'finalised_at': timezone.now().isoformat(),
            },
        )

    return JsonResponse({
        'success': True,
        'accepted_count': accepted_count,
        'redirect_url': '/recruitment/hr/vacancy/list/',
    })


# ── Helpers ────────────────────────────────────────────────────────────────

def _threshold(member_count):
    """Minimum approvals required: floor(n/2) + 1."""
    return (member_count // 2) + 1 if member_count > 0 else 0


def _display_name(user):
    """Best available display name for a user.
    Works with custom AbstractBaseUser that has first_name / last_name fields
    but does NOT inherit AbstractUser's get_full_name() method.
    """
    full = f"{getattr(user, 'first_name', '') or ''} {getattr(user, 'last_name', '') or ''}".strip()
    return full or getattr(user, 'full_name', None) or user.email


def _active_count(vacancy):
    """Non-recused active committee members — used for threshold and completion checks."""
    return ShortlistingCommittee.objects.filter(
        vacancy=vacancy,
        is_active=True,
        has_conflict=False,
    ).count()


def _recused_member_ids(vacancy):
    return list(
        ShortlistingCommittee.objects.filter(
            vacancy=vacancy,
            is_active=True,
            has_conflict=True,
        ).values_list('member_id', flat=True)
    )


def _send_appointment_email(member, vacancy, request):
    """
    Email a committee member their appointment notice.
    Tells them to log in, review the longlist, and submit
    their approve/disapprove decision on each applicant.
    """
    try:
        name = _display_name(member)
        deadline = vacancy.end_date + timedelta(days=21)
        portal_url = request.build_absolute_uri('/hr/dashboard/')

        message_html = f"""
        <p>Dear <strong>{name}</strong>,</p>
        <p>
            You have been appointed to the <strong>Shortlisting Committee</strong>
            for the following vacancy:
        </p>
        <table style="border-collapse:collapse;width:100%;margin:1rem 0;">
            <tr>
                <td style="padding:0.5rem 1rem;background:#f8f9ff;font-weight:600;
                           border:1px solid #e0e4ef;width:35%;">Position</td>
                <td style="padding:0.5rem 1rem;border:1px solid #e0e4ef;">
                    {vacancy.title}
                </td>
            </tr>
            <tr>
                <td style="padding:0.5rem 1rem;background:#f8f9ff;font-weight:600;
                           border:1px solid #e0e4ef;">Reference</td>
                <td style="padding:0.5rem 1rem;border:1px solid #e0e4ef;
                           font-family:monospace;">
                    {vacancy.reference_number}
                </td>
            </tr>
            <tr>
                <td style="padding:0.5rem 1rem;background:#f8f9ff;font-weight:600;
                           border:1px solid #e0e4ef;">Deadline</td>
                <td style="padding:0.5rem 1rem;border:1px solid #e0e4ef;">
                    {deadline.strftime('%d %B %Y')}
                </td>
            </tr>
        </table>
        <p>
            Your task is to <strong>review each longlisted applicant's dossier</strong>
            and formally record your decision — <strong>Approve</strong> or
            <strong>Disapprove</strong> — with a mandatory written comment for
            each applicant. All decisions must be submitted by the deadline above.
        </p>
        <p>
            The shortlist will be automatically generated once every committee
            member has submitted their decisions. Applicants who receive
            approval from 50%+1 of the committee will proceed to the shortlist.
        </p>
        <p>
            Please log in to the portal, acknowledge your appointment, and
            begin reviewing the longlist at your earliest convenience.
        </p>
        <p style="margin-top:1.5rem;">
            <a href="{portal_url}"
               style="background:#1D255B;color:#F9E6A1;padding:0.65rem 1.5rem;
                      border-radius:0.4rem;text-decoration:none;font-weight:600;">
                Go to Portal
            </a>
        </p>
        <p style="margin-top:1.5rem;color:#67748e;font-size:0.85rem;">
            Detailed vote breakdowns and audit records are available in the
            portal. Email notifications will be sent to applicants only after
            all decisions have been submitted and the shortlist is generated.
        </p>
        <p style="color:#67748e;font-size:0.85rem;">
            If you believe this appointment was made in error, please contact
            the HR office immediately.
        </p>
        """

        html_body = render_to_string('emails/email_base.html', {
            'subject': f'Shortlisting Committee Appointment — {vacancy.title}',
            'message_content': message_html,
            'logo_url': 'https://ufaa.go.ke/wp-content/uploads/2022/07/LOGO_RVSD-2-1.png',
            'year': timezone.now().year,
        })
        msg = EmailMultiAlternatives(
            subject=f'Shortlisting Committee Appointment — {vacancy.title} ({vacancy.reference_number})',
            body=(
                f'You have been appointed to the shortlisting committee for {vacancy.title}. '
                f'Please log in to the portal to review the longlist and submit your decisions.'
            ),
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@ufaa.go.ke'),
            to=[member.email],
        )
        msg.attach_alternative(html_body, 'text/html')
        msg.send(fail_silently=False)
        return True

    except Exception as e:
        logger.error(f"Appointment email failed to {member.email}: {e}", exc_info=True)
        return False


# ── View 1: Appoint Committee Dashboard ───────────────────────────────────

@login_required
@role_required(['hod_hr'])
def hr_appoint_committee(request, vacancy_id):
    vacancy = get_object_or_404(Vacancy, id=vacancy_id, status='committee_stage')

    app_count = JobApplication.objects.filter(
        vacancy=vacancy,
        status__code='final_longlisted',
    ).count()

    committee_qs = ShortlistingCommittee.objects.filter(
        vacancy=vacancy,
        is_active=True,
    ).select_related('member', 'appointed_by').order_by('appointed_at')

    committee_data = []
    for entry in committee_qs:
        # Count submitted (non-draft) votes for this member
        votes_done = CommitteeVote.objects.filter(
            vacancy=vacancy,
            member=entry.member,
            is_draft=False,
        ).count()
        # Can only remove if they haven't submitted any votes yet
        can_remove = (votes_done == 0 and not entry.votes_submitted)
        committee_data.append({
            'entry': entry,
            'name': _display_name(entry.member),
            'email': entry.member.email,
            'votes_done': votes_done,
            'can_remove': can_remove,
        })

    committee_count = len(committee_data)
    threshold = _threshold(committee_count)
    deadline = vacancy.end_date + timedelta(days=21)
    days_remaining = (deadline - timezone.now().date()).days

    on_committee_ids = set(
        str(mid) for mid in ShortlistingCommittee.objects.filter(
            vacancy=vacancy, is_active=True
        ).values_list('member_id', flat=True)
    )
    all_staff = []
    for u in User.objects.filter(user_type=2, is_active=True).order_by('first_name', 'last_name', 'email'):
        uid = str(u.pk)
        all_staff.append({
            'id': uid,
            'name': _display_name(u),
            'email': u.email,
            'on_committee': uid in on_committee_ids,
        })

    return render(request, 'recruitment/hr/shortlisting/appoint_committee.html', {
        'page': 'Shortlisting',
        'vacancy': vacancy,
        'app_count': app_count,
        'committee': committee_data,
        'committee_count': committee_count,
        'threshold': threshold,
        'deadline': deadline,
        'all_staff': all_staff,
        'days_remaining': days_remaining,
        'deadline_amber': 0 < days_remaining <= 5,
        'deadline_red': days_remaining <= 0,
    })


# hr_committee_add  — sits between hr_appoint_committee and hr_committee_remove
# hr_shortlist_review — placeholder, full build comes in Step 5
# ─────────────────────────────────────────────────────────────────────────────


@login_required
@role_required(['hod_hr'])
@require_POST
def hr_committee_add(request, vacancy_id):
    vacancy = get_object_or_404(Vacancy, id=vacancy_id, status='committee_stage')
    member_id = request.POST.get('member_id', '').strip()
    send_email = request.POST.get('send_email', '1') == '1'

    if not member_id:
        return JsonResponse({'error': 'No member selected.'}, status=400)

    try:
        member = User.objects.get(pk=member_id)
    except User.DoesNotExist:
        return JsonResponse({'error': 'User not found.'}, status=404)

    try:
        with transaction.atomic():
            entry, created = ShortlistingCommittee.objects.get_or_create(
                vacancy=vacancy,
                member=member,
                defaults={
                    'appointed_by': request.user,
                    'is_active': True,
                    'coi_declared': False,  # ← add this
                    'has_conflict': False,  # ← add this too while you're here
                },
            )
            if not created:
                if entry.is_active:
                    return JsonResponse({
                        'error': f'{_display_name(member)} is already on the committee.'
                    }, status=400)
                entry.is_active = True
                entry.appointed_by = request.user
                entry.appointed_at = timezone.now()
                entry.save(update_fields=['is_active', 'appointed_by', 'appointed_at'])

            ShortlistLog.objects.create(
                vacancy=vacancy,
                application=None,
                performed_by=request.user,
                action='member_appointed',
                notes=f'Appointed {_display_name(member)} to committee.',
                metadata={'member_id': str(member.pk), 'member_email': member.email},
                performed_by_label=_display_name(request.user),
            )
    except Exception as e:
        logger.error(f"Committee add error: {e}", exc_info=True)
        return JsonResponse({'error': 'Database error. Please try again.'}, status=500)

    email_sent = False
    if send_email:
        email_sent = _send_appointment_email(member, vacancy, request)

    new_count = ShortlistingCommittee.objects.filter(vacancy=vacancy, is_active=True).count()
    new_threshold = _threshold(new_count)

    return JsonResponse({
        'success': True,
        'created': created,
        'email_sent': email_sent,
        'member': {
            'id': str(member.pk),
            'name': _display_name(member),
            'email': member.email,
            'appointed_at': entry.appointed_at.strftime('%d %b %Y %H:%M'),
        },
        'committee_count': new_count,
        'new_threshold': new_threshold,
    })


@login_required
@role_required(['hod_hr'])
def hr_shortlist_review(request, vacancy_id):
    """
    HR shortlist review screen.
    Shown after all committee votes are in and _generate_shortlist() has run.
    HR can:
      - View full vote breakdown per applicant
      - Override a result (with mandatory justification, immutably logged)
      - Confirm and finalise the shortlist (advances vacancy to next stage)
    """
    vacancy = get_object_or_404(Vacancy, id=vacancy_id)

    # ── Stats ──────────────────────────────────────────────────────
    committee_members = ShortlistingCommittee.objects.filter(
        vacancy=vacancy, is_active=True
    ).select_related('member')
    committee_count = committee_members.count()
    threshold = _threshold(committee_count)

    all_voted = not committee_members.filter(votes_submitted=False).exists()

    # ── Shortlist results ──────────────────────────────────────────
    results = ShortlistResult.objects.filter(
        vacancy=vacancy
    ).select_related('application', 'application__user', 'application__status')

    results_by_app = {r.application_id: r for r in results}

    # ── All submitted votes ────────────────────────────────────────
    all_votes = CommitteeVote.objects.filter(
        vacancy=vacancy, is_draft=False,
    ).select_related('member').order_by('voted_at')

    votes_by_app = {}
    for v in all_votes:
        votes_by_app.setdefault(v.application_id, []).append(v)

    # ── Applications ───────────────────────────────────────────────
    applications = JobApplication.objects.filter(
        vacancy=vacancy,
        status__code__in=['final_longlisted', 'shortlisted', 'not_selected'],
    ).select_related('user', 'status').order_by('application_number')

    shortlisted_count = 0
    not_selected_count = 0
    app_rows = []

    for app in applications:
        result = results_by_app.get(app.id)
        votes = votes_by_app.get(app.id, [])
        approvals = sum(1 for v in votes if v.approve)
        rejections = len(votes) - approvals

        if result:
            if result.shortlisted:
                shortlisted_count += 1
            else:
                not_selected_count += 1

        app_rows.append({
            'app': app,
            'result': result,
            'votes': votes,
            'approvals': approvals,
            'rejections': rejections,
            'pct': int(approvals / committee_count * 100) if committee_count else 0,
        })

    # Sort: shortlisted first, then by approvals desc
    app_rows.sort(key=lambda r: (
        0 if r['result'] and r['result'].shortlisted else 1,
        -r['approvals']
    ))

    # ── Logs ───────────────────────────────────────────────────────
    override_logs = ShortlistLog.objects.filter(
        vacancy=vacancy,
        action__in=['override_requested', 'override_approved'],
    ).order_by('-timestamp')

    # ── Shortlist already finalised? ───────────────────────────────
    shortlist_finalised = vacancy.status in ('interview_scheduled', 'shortlisted_final')

    return render(request, 'recruitment/hr/shortlisting/shortlist_review.html', {
        'page': 'Shortlist Review',
        'vacancy': vacancy,
        'committee_count': committee_count,
        'threshold': threshold,
        'all_voted': all_voted,
        'app_rows': app_rows,
        'shortlisted_count': shortlisted_count,
        'not_selected_count': not_selected_count,
        'total_count': len(app_rows),
        'override_logs': override_logs,
        'shortlist_finalised': shortlist_finalised,
    })


@login_required
@role_required(['hod_hr'])
@require_POST
def hr_shortlist_override(request, vacancy_id):
    """
    HR overrides a single shortlist result.
    Mandatory justification — immutably logged.
    """
    vacancy = get_object_or_404(Vacancy, id=vacancy_id)
    application_id = request.POST.get('application_id', '').strip()
    new_decision = request.POST.get('decision', '').strip()  # 'shortlist' or 'reject'
    justification = request.POST.get('justification', '').strip()

    if not application_id or new_decision not in ('shortlist', 'reject'):
        return JsonResponse({'error': 'Invalid request.'}, status=400)
    if not justification:
        return JsonResponse({'error': 'A written justification is mandatory for overrides.'}, status=400)

    try:
        application = JobApplication.objects.get(pk=application_id, vacancy=vacancy)
        result = ShortlistResult.objects.get(application=application, vacancy=vacancy)
    except (JobApplication.DoesNotExist, ShortlistResult.DoesNotExist):
        return JsonResponse({'error': 'Record not found.'}, status=404)

    new_shortlisted = (new_decision == 'shortlist')
    old_decision = 'shortlisted' if result.shortlisted else 'not_selected'
    new_label = 'shortlisted' if new_shortlisted else 'not_selected'

    with transaction.atomic():
        result.shortlisted = new_shortlisted
        result.save(update_fields=['shortlisted'])

        # Update application status
        new_status = JobApplicationStatus.objects.get(
            code='shortlisted' if new_shortlisted else 'not_selected'
        )
        application.status = new_status
        application.save(update_fields=['status'])

        ShortlistLog.objects.create(
            vacancy=vacancy,
            application=application,
            performed_by=request.user,
            action='override_approved',
            notes=(
                f'HR override: {old_decision} → {new_label}. '
                f'Justification: {justification}'
            ),
            metadata={
                'old_decision': old_decision,
                'new_decision': new_label,
                'justification': justification,
            },
            performed_by_label=_display_name(request.user),
        )

    return JsonResponse({
        'success': True,
        'new_decision': new_label,
        'shortlisted': new_shortlisted,
    })


def _notify_shortlisted_applicants(vacancy, request):
    """
    Sends a congratulations email to every shortlisted applicant.
    Returns number of emails successfully sent.
    """
    applications = JobApplication.objects.filter(
        vacancy=vacancy,
        status__code='shortlisted',
    ).select_related('user')

    sent_count = 0
    for app in applications:
        applicant = app.user
        try:
            subject = f"Congratulations — You Have Been Shortlisted | {vacancy.title}"

            message_html = f"""
            <p style="font-size:1rem;font-weight:600;color:#262561;margin:0 0 1rem;">
                Dear {applicant.name},
            </p>

            <p style="font-size:0.88rem;color:#344767;line-height:1.65;margin:0 0 1rem;">
                We are pleased to inform you that following a thorough review by our
                shortlisting committee, your application has been successful at the
                shortlisting stage.
            </p>

            <div style="background:#f8f9ff;border-left:4px solid #262561;
                        border-radius:0 0.5rem 0.5rem 0;padding:1rem 1.25rem;margin:1.25rem 0;">
                <div style="font-size:0.68rem;font-weight:700;color:#8392ab;
                            text-transform:uppercase;letter-spacing:.06em;margin-bottom:0.3rem;">
                    Position Applied For
                </div>
                <div style="font-size:0.9rem;font-weight:700;color:#262561;">
                    {vacancy.title}
                </div>
                <div style="font-size:0.76rem;color:#8392ab;margin-top:0.15rem;">
                    Ref: {vacancy.reference_number}
                </div>
            </div>

            <div style="background:#f8f9ff;border-left:4px solid #262561;
                        border-radius:0 0.5rem 0.5rem 0;padding:1rem 1.25rem;margin:1.25rem 0;">
                <div style="font-size:0.68rem;font-weight:700;color:#8392ab;
                            text-transform:uppercase;letter-spacing:.06em;margin-bottom:0.3rem;">
                    Application Reference
                </div>
                <div style="font-size:0.9rem;font-weight:700;color:#262561;">
                    {app.application_number}
                </div>
            </div>

            <div style="background:#fff8e1;border:1px solid #ffe082;border-radius:0.5rem;
                        padding:1rem 1.25rem;margin:1.25rem 0;">
                <div style="font-size:0.78rem;font-weight:700;color:#6d4c00;
                            text-transform:uppercase;letter-spacing:.04em;margin-bottom:0.6rem;">
                    📋 What Happens Next
                </div>
                <div style="font-size:0.82rem;color:#344767;margin-bottom:0.4rem;">
                    <span style="background:#C39545;color:#fff;width:18px;height:18px;
                                 border-radius:50%;font-size:0.65rem;font-weight:700;
                                 display:inline-flex;align-items:center;justify-content:center;
                                 margin-right:0.5rem;">1</span>
                    Our HR team will contact you shortly with interview scheduling details.
                </div>
                <div style="font-size:0.82rem;color:#344767;margin-bottom:0.4rem;">
                    <span style="background:#C39545;color:#fff;width:18px;height:18px;
                                 border-radius:50%;font-size:0.65rem;font-weight:700;
                                 display:inline-flex;align-items:center;justify-content:center;
                                 margin-right:0.5rem;">2</span>
                    Ensure your contact details and documents on the portal are up to date.
                </div>
                <div style="font-size:0.82rem;color:#344767;">
                    <span style="background:#C39545;color:#fff;width:18px;height:18px;
                                 border-radius:50%;font-size:0.65rem;font-weight:700;
                                 display:inline-flex;align-items:center;justify-content:center;
                                 margin-right:0.5rem;">3</span>
                    Monitor your email inbox for further communication from us.
                </div>
            </div>

            <p style="font-size:0.88rem;color:#344767;line-height:1.65;margin:1rem 0;">
                We look forward to meeting you at the interview stage.
                Congratulations once again on this achievement. We will communicate further on the interview date
            </p>
            """

            _send_html_email(subject, applicant.email, message_html)

            ShortlistLog.objects.create(
                vacancy=vacancy,
                application=app,
                performed_by=None,
                action='applicant_notified',
                notes=f'Shortlisted notification sent to {applicant.email}',
                metadata={'email': applicant.email, 'outcome': 'shortlisted'},
                performed_by_label='System',
            )
            sent_count += 1

        except Exception as e:
            logger.error(
                f"Failed to send shortlist email to {applicant.email} "
                f"for vacancy {vacancy.id}: {e}",
                exc_info=True,
            )

    return sent_count


def _notify_rejected_applicants(vacancy, request):
    """
    Sends a regret email to every not-selected applicant.
    Returns number of emails successfully sent.
    """
    applications = JobApplication.objects.filter(
        vacancy=vacancy,
        status__code='not_selected',
    ).select_related('user')

    sent_count = 0
    for app in applications:
        applicant = app.user
        try:
            subject = f"Application Outcome — {vacancy.title} | {vacancy.reference_number}"

            message_html = f"""
            <p style="font-size:1rem;font-weight:600;color:#262561;margin:0 0 1rem;">
                Dear {applicant.name},
            </p>

            <p style="font-size:0.88rem;color:#344767;line-height:1.65;margin:0 0 1rem;">
                Thank you for taking the time to apply for the position below and for
                the interest you have shown in joining our organisation. We sincerely
                appreciate the effort you put into your application.
            </p>

            <div style="background:#f8f9ff;border-left:4px solid #8392ab;
                        border-radius:0 0.5rem 0.5rem 0;padding:1rem 1.25rem;margin:1.25rem 0;">
                <div style="font-size:0.68rem;font-weight:700;color:#8392ab;
                            text-transform:uppercase;letter-spacing:.06em;margin-bottom:0.3rem;">
                    Position Applied For
                </div>
                <div style="font-size:0.9rem;font-weight:700;color:#262561;">
                    {vacancy.title}
                </div>
                <div style="font-size:0.76rem;color:#8392ab;margin-top:0.15rem;">
                    Ref: {vacancy.reference_number}
                </div>
            </div>

            <div style="background:#f8f9ff;border-left:4px solid #8392ab;
                        border-radius:0 0.5rem 0.5rem 0;padding:1rem 1.25rem;margin:1.25rem 0;">
                <div style="font-size:0.68rem;font-weight:700;color:#8392ab;
                            text-transform:uppercase;letter-spacing:.06em;margin-bottom:0.3rem;">
                    Application Reference
                </div>
                <div style="font-size:0.9rem;font-weight:700;color:#262561;">
                    {app.application_number}
                </div>
            </div>

            <p style="font-size:0.88rem;color:#344767;line-height:1.65;margin:0 0 1rem;">
                After careful consideration of all applications received, we regret to
                inform you that on this occasion your application has not been successful
                at the shortlisting stage. This decision was made following a thorough
                review of all candidates against the requirements of the role.
            </p>

            <p style="font-size:0.88rem;color:#344767;line-height:1.65;margin:0 0 1rem;">
                We recognise this is disappointing news. The quality of applications
                we received was high, and this outcome is not a reflection of your
                overall abilities or qualifications.
            </p>

            <div style="background:#f0f2f8;border-radius:0.5rem;
                        padding:1rem 1.25rem;margin:1.25rem 0;">
                <div style="font-size:0.78rem;font-weight:700;color:#262561;
                            text-transform:uppercase;letter-spacing:.04em;margin-bottom:0.5rem;">
                    Keep an Eye on Future Opportunities
                </div>
                <p style="font-size:0.82rem;color:#344767;line-height:1.6;margin:0;">
                    We regularly advertise new vacancies. We encourage you to visit our
                    recruitment portal to view other open positions that may suit your
                    experience and career aspirations. Your profile remains active for
                    future opportunities.
                </p>
            </div>
            """

            _send_html_email(subject, applicant.email, message_html)

            ShortlistLog.objects.create(
                vacancy=vacancy,
                application=app,
                performed_by=None,
                action='applicant_notified',
                notes=f'Not-selected notification sent to {applicant.email}',
                metadata={'email': applicant.email, 'outcome': 'not_selected'},
                performed_by_label='System',
            )
            sent_count += 1

        except Exception as e:
            logger.error(
                f"Failed to send rejection email to {applicant.email} "
                f"for vacancy {vacancy.id}: {e}",
                exc_info=True,
            )

    return sent_count


# ─────────────────────────────────────────────────────────────────────────────
# Updated hr_shortlist_finalise
# ─────────────────────────────────────────────────────────────────────────────

@login_required
@role_required(['hod_hr'])
@require_POST
def hr_shortlist_finalise(request, vacancy_id):
    vacancy = get_object_or_404(Vacancy, id=vacancy_id)

    shortlisted_apps = JobApplication.objects.filter(
        vacancy=vacancy,
        status__code='shortlisted',
    )
    if not shortlisted_apps.exists():
        return JsonResponse({
            'error': 'No shortlisted applicants found. Cannot finalise an empty shortlist.'
        }, status=400)

    with transaction.atomic():
        vacancy.status = 'interview_scheduling'  # ← verify against your pipeline
        vacancy.save(update_fields=['status'])

        ShortlistLog.objects.create(
            vacancy=vacancy,
            application=None,
            performed_by=request.user,
            action='emails_sent',
            notes=(
                f'Shortlist finalised by {_display_name(request.user)}. '
                f'{shortlisted_apps.count()} applicant(s) shortlisted.'
            ),
            metadata={'shortlisted_count': shortlisted_apps.count()},
            performed_by_label=_display_name(request.user),
        )

    # Outside transaction — a failed email won't roll back the status change
    sent_shortlisted = _notify_shortlisted_applicants(vacancy, request)
    sent_rejected = _notify_rejected_applicants(vacancy, request)

    return JsonResponse({
        'success': True,
        'shortlisted_count': shortlisted_apps.count(),
        'emails_sent': sent_shortlisted + sent_rejected,
        'redirect_url': '/recruitment/vacancies/shortlisting/',
    })


# ── View 3: Remove Member (POST / AJAX) ───────────────────────────────────────
# Changes: scores_submitted → votes_submitted, CommitteeScore → CommitteeVote

@login_required
@role_required(['hod_hr'])
@require_POST
def hr_committee_remove(request, vacancy_id):
    vacancy = get_object_or_404(Vacancy, id=vacancy_id, status='committee_stage')
    member_id = request.POST.get('member_id', '').strip()
    reason = request.POST.get('reason', '').strip()

    if not member_id:
        return JsonResponse({'error': 'No member specified.'}, status=400)
    if not reason:
        return JsonResponse({'error': 'A reason for removal is required.'}, status=400)

    entry = get_object_or_404(
        ShortlistingCommittee, vacancy=vacancy, member_id=member_id, is_active=True)

    # Cannot remove once they have submitted any votes
    if entry.votes_submitted:
        return JsonResponse({
            'error': 'Cannot remove a member who has already submitted their votes.'
        }, status=400)

    votes_count = CommitteeVote.objects.filter(
        vacancy=vacancy, member_id=member_id, is_draft=False).count()
    if votes_count > 0:
        return JsonResponse({
            'error': f'Cannot remove — member has submitted {votes_count} vote(s).'
        }, status=400)

    with transaction.atomic():
        entry.is_active = False
        entry.save(update_fields=['is_active'])
        ShortlistLog.objects.create(
            vacancy=vacancy,
            application=None,
            performed_by=request.user,
            action='member_removed',
            notes=reason,
            metadata={'member_id': str(member_id)},
            performed_by_label=_display_name(request.user),
        )

    new_count = ShortlistingCommittee.objects.filter(vacancy=vacancy, is_active=True).count()
    new_threshold = _threshold(new_count)

    return JsonResponse({
        'success': True,
        'committee_count': new_count,
        'new_threshold': new_threshold,
    })


# ── View 4: Notify All Members (POST / AJAX) ──────────────────────────────

@login_required
@role_required(['hod_hr'])
@require_POST
def hr_committee_notify(request, vacancy_id):
    """Re-send appointment emails to all active committee members."""
    vacancy = get_object_or_404(Vacancy, id=vacancy_id, status='committee_stage')

    members = ShortlistingCommittee.objects.filter(
        vacancy=vacancy, is_active=True
    ).select_related('member')

    if not members.exists():
        return JsonResponse({'error': 'No committee members to notify.'}, status=400)

    sent_count = 0
    failed_count = 0
    for entry in members:
        ok = _send_appointment_email(entry.member, vacancy, request)
        if ok:
            sent_count += 1
        else:
            failed_count += 1

    ShortlistLog.objects.create(
        vacancy=vacancy,
        application=None,
        performed_by=request.user,
        action='emails_sent',
        notes=f'Bulk notification sent to {sent_count} committee member(s).',
        metadata={'sent': sent_count, 'failed': failed_count},
        performed_by_label=_display_name(request.user),
    )

    return JsonResponse({
        'success': True,
        'sent_count': sent_count,
        'failed_count': failed_count,
    })


# ── View 5: Staff Search (GET / AJAX) ─────────────────────────────────────

@login_required
@role_required(['hod_hr'])
def hr_committee_staff_search(request, vacancy_id):
    """
    Typeahead search for staff users.
    Returns JSON list: [{id, name, email, already_on_committee}].
    Excludes applicants for this vacancy.
    """
    vacancy = get_object_or_404(Vacancy, id=vacancy_id, status='committee_stage')
    q = request.GET.get('q', '').strip()

    if len(q) < 2:
        return JsonResponse({'results': []})

    # Internal staff only (user_type=2)
    from django.db.models import Q
    qs = User.objects.filter(
        user_type=2,
        is_active=True,
    ).filter(
        Q(email__icontains=q) |
        Q(first_name__icontains=q) |
        Q(last_name__icontains=q) |
        Q(full_name__icontains=q)
    ).exclude(
        # Exclude applicants for this vacancy
        # (no applicant exclusion needed — internal User != JobseekerAccount)
    )[:20]

    # Which are already on the committee? (str because PK is UUID)
    on_committee = set(
        str(mid) for mid in ShortlistingCommittee.objects.filter(
            vacancy=vacancy, is_active=True
        ).values_list('member_id', flat=True)
    )

    results = []
    for u in qs:
        name = _display_name(u)
        results.append({
            'id': str(u.pk),  # UUID -> string for JSON
            'name': name,
            'email': u.email,
            'already_on_committee': str(u.pk) in on_committee,
        })

    return JsonResponse({'results': results})


# ─────────────────────────────────────────────────────────────────────────────
# Add these imports at the top of views.py if not already present
# from .models import CommitteeVote, ShortlistResult, ShortlistLog
# ─────────────────────────────────────────────────────────────────────────────


def _generate_shortlist(vacancy, triggered_by):
    """
    Compute ShortlistResult for every final_longlisted application.
    Excludes votes from recused members.
    Called once all active non-recused members have submitted all votes.
    """
    from django.db import transaction

    recused_ids = _recused_member_ids(vacancy)
    active_count = _active_count(vacancy)
    threshold = _threshold(active_count)

    applications = JobApplication.objects.filter(
        vacancy=vacancy,
        status__code='final_longlisted',
    ).select_related('status')

    shortlisted_count = 0
    not_shortlisted_count = 0

    shortlisted_status = JobApplicationStatus.objects.get(code='shortlisted')
    not_selected_status = JobApplicationStatus.objects.get(code='not_selected')

    with transaction.atomic():
        for app in applications:
            votes = CommitteeVote.objects.filter(
                vacancy=vacancy,
                application=app,
                is_draft=False,
            ).exclude(member_id__in=recused_ids)

            approve_count = votes.filter(approve=True).count()
            reject_count = votes.filter(approve=False).count()
            total_votes = approve_count + reject_count
            shortlisted = approve_count >= threshold

            ShortlistResult.objects.update_or_create(
                vacancy=vacancy,
                application=app,
                defaults={
                    'total_votes': total_votes,
                    'approve_count': approve_count,
                    'reject_count': reject_count,
                    'threshold': threshold,
                    'shortlisted': shortlisted,
                    'computed_at': timezone.now(),
                },
            )

            old_status = app.status
            new_status = shortlisted_status if shortlisted else not_selected_status
            app.status = new_status
            app.save(update_fields=['status'])

            JobApplicationStatusLog.objects.create(
                application=app,
                from_status=old_status,
                to_status=new_status,
                changed_by=triggered_by,
                notes=(
                        f'{"Shortlisted" if shortlisted else "Not shortlisted"} by committee vote. '
                        f'Approve: {approve_count}, Reject: {reject_count}, '
                        f'Threshold: {threshold}/{active_count}.'
                        + (f' ({len(recused_ids)} member(s) recused due to COI.)' if recused_ids else '')
                ),
            )

            if shortlisted:
                shortlisted_count += 1
            else:
                not_shortlisted_count += 1

        ShortlistLog.objects.create(
            vacancy=vacancy,
            performed_by=triggered_by,
            action='all_votes_in',
            notes=(
                    f'Shortlist generated. {shortlisted_count} shortlisted, '
                    f'{not_shortlisted_count} not shortlisted. '
                    f'Threshold: {threshold}/{active_count}.'
                    + (f' {len(recused_ids)} member(s) recused (COI).' if recused_ids else '')
            ),
            metadata={
                'shortlisted': shortlisted_count,
                'not_shortlisted': not_shortlisted_count,
                'threshold': threshold,
                'active_count': active_count,
                'recused_count': len(recused_ids),
            },
            performed_by_label=_display_name(triggered_by) if triggered_by else 'System',
        )

    return shortlisted_count, not_shortlisted_count


# ── View: HR Committee Progress ───────────────────────────────────────────────

@login_required
@role_required(['hod_hr'])
def hr_committee_progress(request, vacancy_id):
    """
    HR monitoring screen for a vacancy's committee voting progress.

    Shows:
    - Each committee member and how many votes they've submitted
    - Each longlisted applicant and vote tally (masked until all voted)
    - Shortlist results once generated
    - Button to trigger shortlist generation once all votes are in
    """
    vacancy = get_object_or_404(Vacancy, id=vacancy_id, status='committee_stage')

    # Applications to be reviewed
    applications = list(
        JobApplication.objects.filter(
            vacancy=vacancy,
            status__code__in=['final_longlisted', 'shortlisted', 'not_selected'],
        ).select_related('user', 'status').order_by('application_number')
    )
    app_count = len(applications)

    # Active committee members
    committee = list(
        ShortlistingCommittee.objects.filter(
            vacancy=vacancy, is_active=True
        ).select_related('member').order_by('appointed_at')
    )
    committee_count = len(committee)
    threshold = _threshold(committee_count)

    # Per-member vote counts
    member_progress = []
    for entry in committee:
        submitted_votes = CommitteeVote.objects.filter(
            vacancy=vacancy,
            member=entry.member,
            is_draft=False,
        ).count()
        draft_votes = CommitteeVote.objects.filter(
            vacancy=vacancy,
            member=entry.member,
            is_draft=True,
        ).count()
        member_progress.append({
            'entry': entry,
            'name': _display_name(entry.member),
            'email': entry.member.email,
            'acknowledged': entry.acknowledged,
            'votes_submitted': entry.votes_submitted,
            'submitted_count': submitted_votes,
            'draft_count': draft_votes,
            'remaining': app_count - submitted_votes,
            'percent': int((submitted_votes / app_count * 100)) if app_count else 0,
        })

    # Overall completion
    members_done = sum(1 for m in member_progress if m['votes_submitted'])
    all_voted = (members_done == committee_count and committee_count > 0)

    # Shortlist already generated?
    shortlist_generated = ShortlistResult.objects.filter(vacancy=vacancy).exists()

    # Auto-generate if all voted and not yet generated
    if all_voted and not shortlist_generated and committee_count > 0:
        _generate_shortlist(vacancy, request.user)
        shortlist_generated = True

    # Per-applicant vote data
    # HR always sees the full picture (no blind rule for HR monitor view)
    app_rows = []
    all_votes_qs = CommitteeVote.objects.filter(
        vacancy=vacancy, is_draft=False
    ).select_related('member')

    # Build a dict: application_id → list of votes
    votes_by_app = {}
    for v in all_votes_qs:
        votes_by_app.setdefault(v.application_id, []).append(v)

    # Shortlist results dict
    results_by_app = {
        r.application_id: r
        for r in ShortlistResult.objects.filter(vacancy=vacancy)
    }

    for app in applications:
        votes = votes_by_app.get(app.id, [])
        approvals = sum(1 for v in votes if v.approve)
        rejections = sum(1 for v in votes if not v.approve)
        voted_ids = {v.member_id for v in votes}
        pending = [m for m in committee if m.member_id not in voted_ids]
        result = results_by_app.get(app.id)

        app_rows.append({
            'app': app,
            'votes': votes,
            'approvals': approvals,
            'rejections': rejections,
            'pending': pending,
            'voted_count': len(votes),
            'result': result,
        })

    # Deadline
    deadline = vacancy.end_date + timedelta(days=21)
    days_remaining = (deadline - timezone.now().date()).days

    return render(request, 'recruitment/hr/shortlisting/committee_progress.html', {
        'page': 'Shortlisting',
        'vacancy': vacancy,
        'app_count': app_count,
        'committee': member_progress,
        'committee_count': committee_count,
        'threshold': threshold,
        'members_done': members_done,
        'all_voted': all_voted,
        'shortlist_generated': shortlist_generated,
        'app_rows': app_rows,
        'deadline': deadline,
        'days_remaining': days_remaining,
        'deadline_amber': 0 < days_remaining <= 5,
        'deadline_red': days_remaining <= 0,
    })


def _committee_member_check(request, vacancy_id):
    """Return the active ShortlistingCommittee entry for this user/vacancy, or None."""
    return ShortlistingCommittee.objects.filter(
        member=request.user,
        vacancy_id=vacancy_id,
        is_active=True,
    ).select_related('vacancy').first()


# ── View 1: Committee Member Dashboard ───────────────────────────────────────

@login_required
@role_required(['committee'])
def committee_dashboard(request):
    assignments = ShortlistingCommittee.objects.filter(
        member=request.user,
        is_active=True,
    ).select_related('vacancy').order_by('appointed_at')

    if not assignments.exists():
        return render(request, 'recruitment/committee/committee_dashboard.html', {
            'page': 'My Committee Assignments',
            'assignments': [],
        })

    rows = []
    for entry in assignments:
        vacancy = entry.vacancy
        app_count = JobApplication.objects.filter(
            vacancy=vacancy,
            status__code='final_longlisted',
        ).count()

        submitted_votes = CommitteeVote.objects.filter(
            vacancy=vacancy, member=request.user, is_draft=False,
        ).count()
        draft_votes = CommitteeVote.objects.filter(
            vacancy=vacancy, member=request.user, is_draft=True,
        ).count()

        deadline = vacancy.end_date + timedelta(days=21)
        days_remaining = (deadline - timezone.now().date()).days

        # Determine what action the member needs to take next
        if not entry.acknowledged:
            next_action = 'acknowledge'
        elif not entry.coi_declared:
            next_action = 'declare_coi'
        elif entry.has_conflict:
            next_action = 'recused'
        elif entry.votes_submitted:
            next_action = 'done'
        else:
            next_action = 'vote'

        rows.append({
            'entry': entry,
            'vacancy': vacancy,
            'app_count': app_count,
            'submitted_votes': submitted_votes,
            'draft_votes': draft_votes,
            'remaining': app_count - submitted_votes,
            'percent': int(submitted_votes / app_count * 100) if app_count else 0,
            'all_done': entry.votes_submitted,
            'acknowledged': entry.acknowledged,
            'coi_declared': entry.coi_declared,
            'has_conflict': entry.has_conflict,
            'next_action': next_action,
            'deadline': deadline,
            'days_remaining': days_remaining,
            'deadline_amber': 0 < days_remaining <= 5,
            'deadline_red': days_remaining <= 0,
        })

    return render(request, 'recruitment/committee/committee_dashboard.html', {
        'page': 'My Committee Assignments',
        'assignments': rows,
    })


# ── View 2: Acknowledge Appointment (POST/AJAX) ───────────────────────────────

@login_required
@require_POST
def committee_acknowledge(request, vacancy_id):
    entry = _committee_member_check(request, vacancy_id)
    if not entry:
        return JsonResponse({'error': 'You are not on this committee.'}, status=403)

    if entry.acknowledged:
        return JsonResponse({'already': True, 'redirect_url': f'/committee/vacancy/{vacancy_id}/coi/'})

    entry.acknowledged = True
    entry.acknowledged_at = timezone.now()
    entry.save(update_fields=['acknowledged', 'acknowledged_at'])

    ShortlistLog.objects.create(
        vacancy=entry.vacancy,
        application=None,
        performed_by=request.user,
        action='member_acknowledged',
        notes=f'{_display_name(request.user)} acknowledged their appointment.',
        metadata={'member_id': str(request.user.pk)},
        performed_by_label=_display_name(request.user),
    )

    return JsonResponse({
        'success': True,
        'redirect_url': f'/committee/vacancy/{vacancy_id}/coi/',
    })


# ── View 3: COI Declaration (GET + POST) ──────────────────────────────────────

@login_required
def committee_declare_coi(request, vacancy_id):
    entry = _committee_member_check(request, vacancy_id)
    if not entry:
        return render(request, 'recruitment/committee/not_assigned.html', {
            'page': 'Conflict of Interest Declaration',
        })

    # Must acknowledge before declaring COI
    if not entry.acknowledged:
        return redirect('committee_dashboard')

    # Already declared — skip to appropriate destination
    if entry.coi_declared:
        if entry.has_conflict:
            return render(request, 'recruitment/committee/committee_coi.html', {
                'page': 'Conflict of Interest Declaration',
                'entry': entry,
                'vacancy': entry.vacancy,
                'already_declared': True,
            })
        return redirect('committee_review', vacancy_id=vacancy_id)

    if request.method == 'POST':
        decision = request.POST.get('decision', '').strip()  # 'no_conflict' or 'has_conflict'
        reason = request.POST.get('conflict_reason', '').strip()

        if decision not in ('no_conflict', 'has_conflict'):
            return render(request, 'recruitment/committee/committee_coi.html', {
                'page': 'Conflict of Interest Declaration',
                'entry': entry,
                'vacancy': entry.vacancy,
                'error': 'Please select one of the options below.',
            })

        if decision == 'has_conflict' and not reason:
            return render(request, 'recruitment/committee/committee_coi.html', {
                'page': 'Conflict of Interest Declaration',
                'entry': entry,
                'vacancy': entry.vacancy,
                'error': 'You must provide a reason when declaring a conflict of interest.',
                'decision_pre': 'has_conflict',
            })

        has_conflict = (decision == 'has_conflict')

        entry.coi_declared = True
        entry.has_conflict = has_conflict
        entry.conflict_reason = reason if has_conflict else ''
        entry.conflict_declared_at = timezone.now()
        entry.save(update_fields=[
            'coi_declared', 'has_conflict',
            'conflict_reason', 'conflict_declared_at',
        ])

        ShortlistLog.objects.create(
            vacancy=entry.vacancy,
            application=None,
            performed_by=request.user,
            action='coi_declared',
            notes=(
                    f'{_display_name(request.user)} declared '
                    + ('a conflict of interest. Reason: ' + reason if has_conflict
                       else 'no conflict of interest.')
            ),
            metadata={
                'member_id': str(request.user.pk),
                'has_conflict': has_conflict,
                'reason': reason,
            },
            performed_by_label=_display_name(request.user),
        )

        if has_conflict:
            # Notify HR by email
            _notify_hr_coi(entry, reason)
            return render(request, 'recruitment/committee/committee_coi.html', {
                'page': 'Conflict of Interest Declaration',
                'entry': entry,
                'vacancy': entry.vacancy,
                'just_recused': True,
            })

        # No conflict — go straight to voting
        return redirect('committee_review', vacancy_id=vacancy_id)

    applications = list(
        JobApplication.objects.filter(
            vacancy=entry.vacancy,
            status__code='final_longlisted',
        ).select_related('user', 'status').order_by('application_number')
    )
    app_count = len(applications)

    # GET
    return render(request, 'recruitment/committee/committee_coi.html', {
        'page': 'Conflict of Interest Declaration',
        'entry': entry,
        'vacancy': entry.vacancy,
        'applications': applications,
    })


def _notify_hr_coi(entry, reason):
    """Send email to HR when a member declares COI."""
    from django.core.mail import EmailMultiAlternatives
    from django.conf import settings
    from django.template.loader import render_to_string
    from datetime import date

    subject = (
        f'COI Declaration — {_display_name(entry.member)} | '
        f'{entry.vacancy.title} [{entry.vacancy.reference_number}]'
    )
    message_html = f"""
        <p>Dear HR,</p>
        <p><strong>{_display_name(entry.member)}</strong> has declared a
        <strong>conflict of interest</strong> for the shortlisting committee of
        <strong>{entry.vacancy.title}</strong> ({entry.vacancy.reference_number}).</p>
        <p><strong>Reason provided:</strong><br>{reason}</p>
        <p>This member has been recused and will not participate in voting.
        Please log in to the portal to review committee composition and
        appoint a replacement if necessary.</p>
        <p style="margin-top:1.5rem;color:#8392ab;font-size:0.85rem;">
            Declared at: {entry.conflict_declared_at.strftime('%d %b %Y, %H:%M')}
        </p>
    """
    try:
        html_body = render_to_string('emails/email_base.html', {
            'subject': subject,
            'message_content': message_html,
            'logo_url': 'https://ufaa.go.ke/wp-content/uploads/2022/07/LOGO_RVSD-2-1.png',
            'year': date.today().year,
        })
        hr_email = getattr(settings, 'HR_NOTIFICATION_EMAIL', settings.DEFAULT_FROM_EMAIL)
        msg = EmailMultiAlternatives(
            subject=subject,
            body='A committee member has declared a conflict of interest. Please view this email in HTML.',
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@ufaa.go.ke'),
            to=[hr_email],
        )
        msg.attach_alternative(html_body, 'text/html')
        msg.send(fail_silently=True)
    except Exception:
        pass  # Don't crash the request if email fails


# ── View 4: Review & Vote Screen ─────────────────────────────────────────────

@login_required
def committee_review(request, vacancy_id):
    entry = _committee_member_check(request, vacancy_id)
    if not entry:
        return render(request, 'recruitment/committee/not_assigned.html', {
            'page': 'Committee Review',
        })

    vacancy = entry.vacancy

    # Gate 1: must acknowledge first
    if not entry.acknowledged:
        return render(request, 'recruitment/committee/committee_acknowledge.html', {
            'page': 'Committee Review',
            'entry': entry,
            'vacancy': vacancy,
        })

    # Gate 2: must complete COI declaration
    if not entry.coi_declared:
        return redirect('committee_declare_coi', vacancy_id=vacancy_id)

    # Gate 3: recused members cannot vote
    if entry.has_conflict:
        return render(request, 'recruitment/committee/committee_coi.html', {
            'page': 'Committee Review',
            'entry': entry,
            'vacancy': vacancy,
            'already_declared': True,
        })

    if entry.votes_submitted:
        return redirect('committee_results', vacancy_id=vacancy_id)

    applications = list(
        JobApplication.objects.filter(
            vacancy=vacancy,
            status__code='final_longlisted',
        ).select_related('user', 'status').order_by('application_number')
    )
    app_count = len(applications)

    my_votes = {
        v.application_id: v
        for v in CommitteeVote.objects.filter(
            vacancy=vacancy, member=request.user,
        )
    }

    my_submitted_ids = {app_id for app_id, v in my_votes.items() if not v.is_draft}

    other_votes_by_app = {}
    if my_submitted_ids:
        for ov in CommitteeVote.objects.filter(
                vacancy=vacancy,
                application_id__in=my_submitted_ids,
                is_draft=False,
        ).exclude(member=request.user).select_related('member'):
            other_votes_by_app.setdefault(ov.application_id, []).append(ov)

    app_rows = []
    submitted_count = 0
    for app in applications:
        my_vote = my_votes.get(app.id)
        is_submitted = bool(my_vote and not my_vote.is_draft)
        if is_submitted:
            submitted_count += 1
        app_rows.append({
            'app': app,
            'my_vote': my_vote,
            'is_submitted': is_submitted,
            'other_votes': other_votes_by_app.get(app.id, []) if is_submitted else [],
            'can_vote': not is_submitted,
        })

    active_count = _active_count(vacancy)
    threshold = _threshold(active_count)
    deadline = vacancy.end_date + timedelta(days=21)

    return render(request, 'recruitment/committee/committee_review.html', {
        'page': 'Committee Review',
        'entry': entry,
        'vacancy': vacancy,
        'app_rows': app_rows,
        'app_count': app_count,
        'submitted_count': submitted_count,
        'remaining': app_count - submitted_count,
        'all_submitted': submitted_count == app_count,
        'committee_count': active_count,
        'threshold': threshold,
        'deadline': deadline,
        'applications': applications,
        'days_remaining': (deadline - timezone.now().date()).days,
    })


# ── View 4: Save / Submit Single Vote (POST/AJAX) ────────────────────────────

@login_required
@require_POST
def committee_vote_save(request, vacancy_id):
    entry = _committee_member_check(request, vacancy_id)
    if not entry:
        return JsonResponse({'error': 'Not authorised.'}, status=403)

    if not entry.coi_declared or entry.has_conflict:
        return JsonResponse({'error': 'You cannot vote — COI declaration incomplete or recused.'}, status=403)

    if entry.votes_submitted:
        return JsonResponse({'error': 'You have already submitted all votes.'}, status=400)

    app_id = request.POST.get('application_id', '').strip()
    approve = request.POST.get('approve', '').strip().lower()
    comment = request.POST.get('comment', '').strip()
    action = request.POST.get('action', 'draft')

    if not app_id:
        return JsonResponse({'error': 'No application specified.'}, status=400)
    if approve not in ('true', 'false'):
        return JsonResponse({'error': 'Invalid decision value.'}, status=400)
    if action == 'submit' and not comment:
        return JsonResponse({'error': 'A comment is required before submitting.'}, status=400)

    try:
        application = JobApplication.objects.get(
            pk=app_id,
            vacancy_id=vacancy_id,
            status__code='final_longlisted',
        )
    except JobApplication.DoesNotExist:
        return JsonResponse({'error': 'Application not found.'}, status=404)

    approve_bool = (approve == 'true')
    is_draft = (action == 'draft')
    now = timezone.now()

    vote, created = CommitteeVote.objects.update_or_create(
        vacancy=entry.vacancy,
        application=application,
        member=request.user,
        defaults={
            'approve': approve_bool,
            'comment': comment,
            'is_draft': is_draft,
            'voted_at': now,
            'submitted_at': None if is_draft else now,
        },
    )

    if not is_draft:
        ShortlistLog.objects.create(
            vacancy=entry.vacancy,
            application=application,
            performed_by=request.user,
            action='vote_submitted',
            notes=f'{"Approved" if approve_bool else "Disapproved"}: {comment[:120]}',
            metadata={
                'member_id': str(request.user.pk),
                'approve': approve_bool,
                'app_id': str(application.pk),
            },
            performed_by_label=_display_name(request.user),
        )

    revealed_votes = []
    if not is_draft:
        for ov in CommitteeVote.objects.filter(
                vacancy=entry.vacancy,
                application=application,
                is_draft=False,
        ).exclude(member=request.user).select_related('member'):
            revealed_votes.append({
                'name': _display_name(ov.member),
                'approve': ov.approve,
                'comment': ov.comment,
            })

    return JsonResponse({
        'success': True,
        'is_draft': is_draft,
        'approve': approve_bool,
        'revealed_votes': revealed_votes,
    })


# ── View 5: Submit All Votes ──────────────────────────────────────────────────

@login_required
@require_POST
def committee_submit_all(request, vacancy_id):
    entry = _committee_member_check(request, vacancy_id)
    if not entry:
        return JsonResponse({'error': 'Not authorised.'}, status=403)

    if not entry.coi_declared or entry.has_conflict:
        return JsonResponse({'error': 'Cannot submit — recused or COI not declared.'}, status=403)

    if entry.votes_submitted:
        return JsonResponse({'error': 'Already submitted.'}, status=400)

    vacancy = entry.vacancy

    app_ids = set(
        JobApplication.objects.filter(
            vacancy=vacancy,
            status__code='final_longlisted',
        ).values_list('pk', flat=True)
    )

    submitted_vote_app_ids = set(
        CommitteeVote.objects.filter(
            vacancy=vacancy,
            member=request.user,
            is_draft=False,
        ).values_list('application_id', flat=True)
    )

    missing = app_ids - submitted_vote_app_ids
    if missing:
        return JsonResponse({
            'error': (
                f'You still have {len(missing)} applicant(s) without a submitted vote. '
                f'Please vote on all applicants before submitting.'
            )
        }, status=400)

    entry.votes_submitted = True
    entry.votes_submitted_at = timezone.now()
    entry.save(update_fields=['votes_submitted', 'votes_submitted_at'])

    # "All done" = every non-recused, active member has submitted
    total_active = ShortlistingCommittee.objects.filter(
        vacancy=vacancy, is_active=True, has_conflict=False,
    ).count()
    done_active = ShortlistingCommittee.objects.filter(
        vacancy=vacancy, is_active=True, has_conflict=False, votes_submitted=True,
    ).count()

    shortlist_generated = False
    if done_active == total_active and total_active > 0:
        _generate_shortlist(vacancy, request.user)
        shortlist_generated = True

    return JsonResponse({
        'success': True,
        'shortlist_generated': shortlist_generated,
        'redirect_url': f'/recruitment/committee/vacancy/{vacancy_id}/results/',
    })


# ── View 6: Results Screen ────────────────────────────────────────────────────

@login_required
def committee_results(request, vacancy_id):
    entry = _committee_member_check(request, vacancy_id)
    if not entry:
        return render(request, 'recruitment/committee/not_assigned.html', {
            'page': 'Committee Results',
        })

    vacancy = entry.vacancy

    applications = list(
        JobApplication.objects.filter(
            vacancy=vacancy,
            status__code__in=['final_longlisted', 'shortlisted', 'not_selected'],
        ).select_related('user', 'status').order_by('application_number')
    )

    all_votes = CommitteeVote.objects.filter(
        vacancy=vacancy, is_draft=False,
    ).select_related('member')

    votes_by_app = {}
    for v in all_votes:
        votes_by_app.setdefault(v.application_id, []).append(v)

    results_by_app = {
        r.application_id: r
        for r in ShortlistResult.objects.filter(vacancy=vacancy)
    }

    active_count = _active_count(vacancy)
    all_done = (
            ShortlistingCommittee.objects.filter(
                vacancy=vacancy, is_active=True, has_conflict=False, votes_submitted=True
            ).count() == active_count and active_count > 0
    )

    app_rows = []
    for app in applications:
        votes = votes_by_app.get(app.id, [])
        my_vote = next((v for v in votes if v.member == request.user), None)
        result = results_by_app.get(app.id)
        approvals = sum(1 for v in votes if v.approve)

        app_rows.append({
            'app': app,
            'votes': votes,
            'my_vote': my_vote,
            'approvals': approvals,
            'rejections': len(votes) - approvals,
            'result': result,
        })

    return render(request, 'recruitment/committee/committee_results.html', {
        'page': 'My Votes — Results',
        'entry': entry,
        'vacancy': vacancy,
        'app_rows': app_rows,
        'committee_count': active_count,
        'all_done': all_done,
        'threshold': _threshold(active_count),
    })


# ── HR Progress view (updated to show COI status) ─────────────────────────────

@login_required
def hr_committee_progress(request, vacancy_id):
    vacancy = get_object_or_404(Vacancy, id=vacancy_id, status='committee_stage')

    applications = list(
        JobApplication.objects.filter(
            vacancy=vacancy,
            status__code__in=['final_longlisted', 'shortlisted', 'not_selected'],
        ).select_related('user', 'status').order_by('application_number')
    )
    app_count = len(applications)

    all_committee = list(
        ShortlistingCommittee.objects.filter(
            vacancy=vacancy, is_active=True,
        ).select_related('member').order_by('appointed_at')
    )

    active_count = sum(1 for e in all_committee if not e.has_conflict)
    threshold = _threshold(active_count)
    recused_ids_set = {e.member_id for e in all_committee if e.has_conflict}

    member_progress = []
    for entry in all_committee:
        if entry.has_conflict:
            member_progress.append({
                'entry': entry,
                'name': _display_name(entry.member),
                'email': entry.member.email,
                'acknowledged': entry.acknowledged,
                'coi_declared': entry.coi_declared,
                'has_conflict': True,
                'conflict_reason': entry.conflict_reason,
                'votes_submitted': False,
                'submitted_count': 0,
                'draft_count': 0,
                'remaining': 0,
                'percent': 0,
                'is_recused': True,
            })
            continue

        submitted_votes = CommitteeVote.objects.filter(
            vacancy=vacancy, member=entry.member, is_draft=False,
        ).count()
        draft_votes = CommitteeVote.objects.filter(
            vacancy=vacancy, member=entry.member, is_draft=True,
        ).count()

        member_progress.append({
            'entry': entry,
            'name': _display_name(entry.member),
            'email': entry.member.email,
            'acknowledged': entry.acknowledged,
            'coi_declared': entry.coi_declared,
            'has_conflict': False,
            'conflict_reason': '',
            'votes_submitted': entry.votes_submitted,
            'submitted_count': submitted_votes,
            'draft_count': draft_votes,
            'remaining': app_count - submitted_votes,
            'percent': int(submitted_votes / app_count * 100) if app_count else 0,
            'is_recused': False,
        })

    members_done = sum(1 for m in member_progress if not m['is_recused'] and m['votes_submitted'])
    all_voted = (members_done == active_count and active_count > 0)
    recused_count = len(recused_ids_set)

    shortlist_generated = ShortlistResult.objects.filter(vacancy=vacancy).exists()

    if all_voted and not shortlist_generated and active_count > 0:
        _generate_shortlist(vacancy, request.user)
        shortlist_generated = True

    all_votes_qs = CommitteeVote.objects.filter(
        vacancy=vacancy, is_draft=False,
    ).exclude(member_id__in=recused_ids_set).select_related('member')

    votes_by_app = {}
    for v in all_votes_qs:
        votes_by_app.setdefault(v.application_id, []).append(v)

    results_by_app = {
        r.application_id: r
        for r in ShortlistResult.objects.filter(vacancy=vacancy)
    }

    app_rows = []
    for app in applications:
        votes = votes_by_app.get(app.id, [])
        approvals = sum(1 for v in votes if v.approve)
        rejections = sum(1 for v in votes if not v.approve)
        result = results_by_app.get(app.id)
        app_rows.append({
            'app': app,
            'votes': votes,
            'approvals': approvals,
            'rejections': rejections,
            'voted_count': len(votes),
            'result': result,
        })

    deadline = vacancy.end_date + timedelta(days=21)
    days_remaining = (deadline - timezone.now().date()).days

    return render(request, 'recruitment/hr/shortlisting/committee_progress.html', {
        'page': 'Shortlisting',
        'vacancy': vacancy,
        'app_count': app_count,
        'committee': member_progress,
        'committee_count': active_count,
        'total_committee': len(all_committee),
        'recused_count': recused_count,
        'threshold': threshold,
        'members_done': members_done,
        'all_voted': all_voted,
        'shortlist_generated': shortlist_generated,
        'app_rows': app_rows,
        'deadline': deadline,
        'days_remaining': days_remaining,
        'deadline_amber': 0 < days_remaining <= 5,
        'deadline_red': days_remaining <= 0,
    })


# ═════════════════════════════════════════════════════════════════════════════
# SHARED HELPERS
# ═════════════════════════════════════════════════════════════════════════════

def _active_panel_count(vacancy):
    """Non-recused active panel members."""
    return InterviewPanel.objects.filter(
        vacancy=vacancy, is_active=True, has_conflict=False,
    ).count()

def _get_job_status(code: str):
    """Safe fetch of a JobApplicationStatus row."""
    try:
        return JobApplicationStatus.objects.get(code=code)
    except JobApplicationStatus.DoesNotExist:
        logger.error(f"JobApplicationStatus code='{code}' not found. Run the data migration.")
        return None


def _compute_interview_results(vacancy):
    """
    Called once all active, non-recused panel members have submitted all scores.

    Steps
    -----
    1. Aggregate scores per candidate (excluding recused panel members).
    2. Create / update InterviewResult rows with total, percentage, rank.
    3. Bulk-update every scored application to 'interviewed' status.
    4. If vacancy is still in 'interview_scheduling', advance it to 'interviews'
       so HR knows scoring is complete and they can submit to CEO.
    5. Write one InterviewLog audit record.

    Returns list of InterviewResult objects ordered by rank.
    """
    criteria = list(InterviewCriterion.objects.filter(vacancy=vacancy))
    max_per_member = sum(c.max_score for c in criteria)

    active_members = list(
        InterviewPanel.objects.filter(
            vacancy=vacancy, is_active=True, has_conflict=False,
        )
    )
    panel_count = len(active_members)
    max_possible = Decimal(max_per_member * panel_count)

    recused_ids = list(
        InterviewPanel.objects.filter(
            vacancy=vacancy, is_active=True, has_conflict=True,
        ).values_list('member_id', flat=True)
    )

    applications = list(
        JobApplication.objects.filter(
            vacancy=vacancy, status__code='shortlisted',
        ).select_related('status')
    )

    # Status objects — fetched once
    interviewed_status = _get_job_status('interviewed')

    results = []

    with transaction.atomic():
        for app in applications:
            submitted_scores = InterviewScore.objects.filter(
                vacancy=vacancy,
                application=app,
                is_draft=False,
            ).exclude(panel_member_id__in=recused_ids)

            total = sum(s.score for s in submitted_scores) or Decimal('0')
            pct = (total / max_possible * 100) if max_possible else Decimal('0')

            result, _ = InterviewResult.objects.update_or_create(
                vacancy=vacancy,
                application=app,
                defaults={
                    'total_score': total,
                    'max_possible': max_possible,
                    'percentage': round(pct, 2),
                    'computed_at': timezone.now(),
                },
            )
            results.append(result)

        # ── Rank ────────────────────────────────────────────────────────────
        results.sort(key=lambda r: r.total_score, reverse=True)
        for i, result in enumerate(results, start=1):
            result.rank = i
            result.save(update_fields=['rank'])

        # ── Update statuses → 'interviewed' ─────────────────────────────────
        if interviewed_status:
            for app in applications:
                old_status = app.status
                if old_status.code == 'interviewed':
                    continue  # already done (idempotent)
                app.status = interviewed_status
                app.save(update_fields=['status'])
                JobApplicationStatusLog.objects.create(
                    application=app,
                    from_status=old_status,
                    to_status=interviewed_status,
                    changed_by=None,
                    notes=(
                        f'Interview scoring complete — all {panel_count} active panel '
                        f'member(s) submitted scores. Candidate ranked #{next(r.rank for r in results if r.application_id == app.id)}.'
                    ),
                )
        else:
            logger.warning(
                "_compute_interview_results: 'interviewed' status missing — "
                "application statuses NOT updated. Run the data migration."
            )

        # ── Advance vacancy: interview_scheduling → interviews ───────────────
        if vacancy.status == 'interview_scheduling':
            vacancy.status = 'interviews'
            vacancy.save(update_fields=['status'])

        # ── Audit log ────────────────────────────────────────────────────────
        InterviewLog.objects.create(
            vacancy=vacancy,
            action='all_scores_in',
            notes=(
                f'Interview results computed. {len(results)} candidates ranked. '
                f'Max possible: {max_possible}. '
                f'All candidates updated to "interviewed" status. '
                f'Vacancy advanced to "interviews" stage.'
            ),
            metadata={
                'candidate_count': len(results),
                'max_possible': str(max_possible),
                'panel_count': panel_count,
                'recused_count': len(recused_ids),
            },
            performed_by_label='System',
        )

    return results


def _notify_candidate(slot, vacancy):
    """Email a shortlisted candidate their interview slot details."""
    applicant = slot.application.user
    venue_label = 'Online Meeting Link' if slot.schedule.venue_type == 'online' else 'Venue'
    subject = f'Interview Invitation — {vacancy.title} [{vacancy.reference_number}]'
    message_html = f"""
        <p>Dear {applicant.name},</p>
        <p>We are pleased to invite you for an interview for the position of
        <strong>{vacancy.title}</strong> ({vacancy.reference_number}).</p>

        <table style="border-collapse:collapse;width:100%;margin:1rem 0;">
            <tr>
                <td style="padding:0.5rem 1rem;background:#f8f9ff;font-weight:600;
                           border:1px solid #e0e4ef;width:35%;">Date</td>
                <td style="padding:0.5rem 1rem;border:1px solid #e0e4ef;">
                    {slot.interview_date.strftime('%A, %d %B %Y')}
                </td>
            </tr>
            <tr>
                <td style="padding:0.5rem 1rem;background:#f8f9ff;font-weight:600;
                           border:1px solid #e0e4ef;">Time</td>
                <td style="padding:0.5rem 1rem;border:1px solid #e0e4ef;">
                    {slot.interview_time.strftime('%I:%M %p')}
                </td>
            </tr>
            <tr>
                <td style="padding:0.5rem 1rem;background:#f8f9ff;font-weight:600;
                           border:1px solid #e0e4ef;">{venue_label}</td>
                <td style="padding:0.5rem 1rem;border:1px solid #e0e4ef;">
                    {slot.effective_venue()}
                </td>
            </tr>
        </table>

        {'<p><strong>Preparatory Instructions:</strong><br>' + slot.schedule.instructions + '</p>' if slot.schedule.instructions else ''}

        <p>Please ensure you arrive on time with a valid form of identification
        and copies of your academic and professional certificates.</p>
        <p>We look forward to meeting you.</p>
        <p style="margin-top:1.5rem;">Regards,<br>
        <strong>UFAA Human Resources Department</strong></p>
    """
    _send_html_email(subject, applicant.email, message_html)


def _notify_panel_member(entry, schedule, vacancy):
    """Email a panel member their assignment details."""
    from django.conf import settings as django_settings
    member = entry.member
    subject = f'Interview Panel Assignment — {vacancy.title} [{vacancy.reference_number}]'

    slots = InterviewSlot.objects.filter(vacancy=vacancy).select_related('application__user')
    candidate_rows = ''.join(
        f'<tr>'
        f'<td style="padding:0.4rem 0.75rem;border:1px solid #e0e4ef;">{s.application.user.name}</td>'
        f'<td style="padding:0.4rem 0.75rem;border:1px solid #e0e4ef;">{s.interview_date.strftime("%d %b %Y")}</td>'
        f'<td style="padding:0.4rem 0.75rem;border:1px solid #e0e4ef;">{s.interview_time.strftime("%I:%M %p")}</td>'
        f'</tr>'
        for s in slots
    )

    portal_url = getattr(django_settings, 'SITE_URL', 'https://ufaa.go.ke') + '/recruitment/panel/dashboard/'

    message_html = f"""
        <p>Dear {_display_name(member)},</p>
        <p>You have been appointed to the interview panel for
        <strong>{vacancy.title}</strong> ({vacancy.reference_number}).</p>

        <table style="border-collapse:collapse;width:100%;margin:1rem 0;">
            <tr>
                <td style="padding:0.5rem 1rem;background:#f8f9ff;font-weight:600;
                           border:1px solid #e0e4ef;width:35%;">Venue Type</td>
                <td style="padding:0.5rem 1rem;border:1px solid #e0e4ef;">
                    {schedule.get_venue_type_display()}
                </td>
            </tr>
            <tr>
                <td style="padding:0.5rem 1rem;background:#f8f9ff;font-weight:600;
                           border:1px solid #e0e4ef;">
                    {'Location' if schedule.venue_type == 'physical' else 'Meeting Link'}
                </td>
                <td style="padding:0.5rem 1rem;border:1px solid #e0e4ef;">{schedule.venue}</td>
            </tr>
        </table>

        <p><strong>Candidates you will interview:</strong></p>
        <table style="border-collapse:collapse;width:100%;margin:0.5rem 0 1rem;">
            <thead>
                <tr style="background:#f8f9ff;">
                    <th style="padding:0.5rem 0.75rem;border:1px solid #e0e4ef;text-align:left;">Candidate</th>
                    <th style="padding:0.5rem 0.75rem;border:1px solid #e0e4ef;text-align:left;">Date</th>
                    <th style="padding:0.5rem 0.75rem;border:1px solid #e0e4ef;text-align:left;">Time</th>
                </tr>
            </thead>
            <tbody>{candidate_rows}</tbody>
        </table>

        <p>Please log in to the portal to acknowledge your appointment,
        complete the conflict of interest declaration, and submit your scores
        after each interview.</p>
        <p><a href="{portal_url}" style="background:#262561;color:#F9E6A1;
           padding:0.5rem 1.25rem;border-radius:0.4rem;text-decoration:none;
           font-weight:600;">Go to Panel Portal</a></p>

        <p style="margin-top:1.5rem;">Regards,<br>
        <strong>UFAA Human Resources Department</strong></p>
    """
    _send_html_email(subject, member.email, message_html)


def _notify_hr_panel_coi(entry, reason):
    from django.conf import settings as django_settings
    subject = (
        f'Panel COI Declaration — {_display_name(entry.member)} | '
        f'{entry.vacancy.title} [{entry.vacancy.reference_number}]'
    )
    message_html = f"""
        <p>Dear HR,</p>
        <p><strong>{_display_name(entry.member)}</strong> has declared a conflict of interest
        on the interview panel for <strong>{entry.vacancy.title}</strong>
        ({entry.vacancy.reference_number}).</p>
        <p><strong>Reason:</strong><br>{reason}</p>
        <p>This member has been recused and will not score candidates.
        Please review the panel composition and appoint a replacement if necessary.</p>
        <p style="margin-top:1.5rem;color:#8392ab;font-size:0.85rem;">
            Declared at: {entry.conflict_declared_at.strftime('%d %b %Y, %H:%M')}
        </p>
    """
    try:
        hr_email = getattr(django_settings, 'HR_NOTIFICATION_EMAIL', django_settings.DEFAULT_FROM_EMAIL)
        _send_html_email(subject, hr_email, message_html)
    except Exception:
        pass


# ═════════════════════════════════════════════════════════════════════════════
# HR VIEWS
# ═════════════════════════════════════════════════════════════════════════════
@login_required
@role_required(['hod_hr'])
def vacancy_interviews(request):
    """
    HR pipeline list — shows vacancies in both interview sub-stages:
      interview_scheduling  = panel/slots/scoring in progress
      interviews            = all scoring done, ready to submit to CEO
    """
    vacancies = Vacancy.objects.filter(
        status__in=['interview_scheduling', 'interviews']
    ).order_by('-created_at')

    vacancy_data = []
    for v in vacancies:
        panel_count    = InterviewPanel.objects.filter(vacancy=v, is_active=True).count()
        panel_active   = InterviewPanel.objects.filter(vacancy=v, is_active=True, has_conflict=False).count()
        panel_done     = InterviewPanel.objects.filter(vacancy=v, is_active=True, has_conflict=False, scores_submitted=True).count()
        slot_count     = InterviewSlot.objects.filter(vacancy=v).count()
        notified_count = InterviewSlot.objects.filter(vacancy=v, notified=True).count()
        results_exist  = InterviewResult.objects.filter(vacancy=v).exists()
        scoring_complete = panel_active > 0 and panel_done == panel_active

        vacancy_data.append({
            'vacancy':          v,
            'panel_count':      panel_count,
            'panel_active':     panel_active,
            'panel_done':       panel_done,
            'slot_count':       slot_count,
            'notified_count':   notified_count,
            'scoring_complete': scoring_complete,
            'results_exist':    results_exist,
            'stage':            v.status,
        })

    context = {
        'page':         'Interviews',
        'vacancy_data': vacancy_data,
        'total':        len(vacancy_data),
    }
    return render(request, 'recruitment/hr/interview/vacancy_interviews.html', context)

@login_required
def hr_interview_setup(request, vacancy_id):
    vacancy = get_object_or_404(Vacancy, id=vacancy_id)

    panel = list(
        InterviewPanel.objects.filter(vacancy=vacancy, is_active=True)
        .select_related('member').order_by('appointed_at')
    )
    criteria = list(InterviewCriterion.objects.filter(vacancy=vacancy))
    schedule = InterviewSchedule.objects.filter(vacancy=vacancy).first()

    slots = []
    if schedule:
        slots = list(
            InterviewSlot.objects.filter(vacancy=vacancy)
            .select_related('application__user', 'schedule')
            .order_by('interview_date', 'interview_time')
        )

    slotted_app_ids = {s.application_id for s in slots}
    unslotted = list(
        JobApplication.objects.filter(
            vacancy=vacancy, status__code='shortlisted',
        ).select_related('user').exclude(id__in=slotted_app_ids)
        .order_by('application_number')
    )

    total_shortlisted = JobApplication.objects.filter(
        vacancy=vacancy, status__code='shortlisted',
    ).count()

    max_possible = sum(c.max_score for c in criteria)
    # ── Build all_staff for the panel picker ──────────────────────────────
    from django.contrib.auth import get_user_model
    User = get_user_model()

    # Exclude anyone who has applied for this vacancy
    applicant_ids = set(
        JobApplication.objects.filter(vacancy=vacancy)
        .values_list('user_id', flat=True)
    )
    panel_ids = {entry.member_id for entry in panel}

    all_staff = []
    for u in User.objects.exclude(id__in=applicant_ids).order_by('first_name', 'last_name', 'email'):
        full_name = (getattr(u, 'name', None) or '').strip() or u.email
        dept = getattr(u, 'department', None)
        if hasattr(dept, 'name'):
            dept = dept.name
        elif not isinstance(dept, str):
            dept = ''
        all_staff.append({
            'id': u.pk,
            'name': full_name,
            'email': u.email,
            'department': dept,
            'already_on_panel': u.pk in panel_ids,
        })

    return render(request, 'recruitment/hr/interview/interview_setup.html', {
        'page': 'Interview Scheduling',
        'vacancy': vacancy,
        'panel': panel,
        'panel_count': len(panel),
        'criteria': criteria,
        'max_possible': max_possible,
        'schedule': schedule,
        'slots': slots,
        'unslotted': unslotted,
        'total_shortlisted': total_shortlisted,
        'all_slotted': len(unslotted) == 0 and total_shortlisted > 0,
        'can_notify_candidates': (
                schedule is not None and
                len(unslotted) == 0 and
                total_shortlisted > 0 and
                not (schedule.candidates_notified if schedule else False)
        ),
        'can_notify_panel': (
                len(panel) > 0 and
                schedule is not None and
                not (schedule.panel_notified if schedule else False)
        ),
        'all_staff': all_staff,
    })


def _notify_panel_appointment(member, vacancy):
    """
    Immediate 'You have been appointed' email sent when HR adds a panel member.
    Does NOT require a schedule or slots to exist yet.
    """
    try:
        from django.conf import settings as django_settings
        name = _display_name(member)
        portal_url = getattr(django_settings, 'SITE_URL', '') + '/recruitment/panel/dashboard/'

        message_html = f"""
            <p>Dear <strong>{name}</strong>,</p>
            <p>You have been appointed as a member of the
            <strong>Interview Panel</strong> for the following vacancy:</p>
            <table style="border-collapse:collapse;width:100%;margin:1rem 0;">
                <tr>
                    <td style="padding:.5rem 1rem;background:#f8f9ff;font-weight:600;
                               border:1px solid #e0e4ef;width:35%;">Position</td>
                    <td style="padding:.5rem 1rem;border:1px solid #e0e4ef;">
                        {vacancy.title}
                    </td>
                </tr>
                <tr>
                    <td style="padding:.5rem 1rem;background:#f8f9ff;font-weight:600;
                               border:1px solid #e0e4ef;">Reference</td>
                    <td style="padding:.5rem 1rem;border:1px solid #e0e4ef;
                               font-family:monospace;">
                        {vacancy.reference_number}
                    </td>
                </tr>
            </table>
            <p>Your role is to <strong>score each shortlisted candidate</strong>
            against the defined assessment criteria and complete a conflict of
            interest declaration before scoring begins.</p>
            <p>Interview schedule details will be sent to you separately once confirmed.</p>
            <p style="margin-top:1.5rem;">
                <a href="{portal_url}"
                   style="background:#262561;color:#F9E6A1;padding:.65rem 1.5rem;
                          border-radius:.4rem;text-decoration:none;font-weight:600;">
                    Go to Panel Portal
                </a>
            </p>
            <p style="margin-top:1.5rem;color:#67748e;font-size:.85rem;">
                If you believe this appointment was made in error please contact
                the HR office immediately.
            </p>
            <p>Regards,<br><strong>UFAA Human Resources Department</strong></p>
        """
        _send_html_email(
            subject=f'Interview Panel Appointment — {vacancy.title} [{vacancy.reference_number}]',
            to_email=member.email,
            message_html=message_html,
        )
        return True
    except Exception as e:
        logger.error(f'Panel appointment email failed to {member.email}: {e}', exc_info=True)
        return False


def hr_panel_add(request, vacancy_id):
    vacancy = get_object_or_404(Vacancy, id=vacancy_id)
    user_id = request.POST.get('user_id', '').strip()
    if not user_id:
        return JsonResponse({'error': 'No user selected.'}, status=400)

    from django.contrib.auth import get_user_model
    User = get_user_model()
    try:
        member = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        return JsonResponse({'error': 'User not found.'}, status=404)

    entry, created = InterviewPanel.objects.get_or_create(
        vacancy=vacancy, member=member,
        defaults={
            'appointed_by': request.user,
            'is_active': True,
            'coi_declared': False,
            'has_conflict': False,
        },
    )

    if not created:
        if entry.is_active:
            return JsonResponse({'error': f'{_display_name(member)} is already on the panel.'}, status=400)
        entry.is_active = True
        entry.appointed_by = request.user
        entry.appointed_at = timezone.now()
        entry.save(update_fields=['is_active', 'appointed_by', 'appointed_at'])

    InterviewLog.objects.create(
        vacancy=vacancy, performed_by=request.user,
        action='panel_appointed',
        notes=f'{_display_name(member)} added to interview panel.',
        metadata={'member_id': str(member.pk)},
        performed_by_label=_display_name(request.user),
    )

    email_sent = _notify_panel_appointment(member, vacancy)

    return JsonResponse({
        'success': True,
        'email_sent': email_sent,
        'member': {'id': str(member.pk), 'name': _display_name(member), 'email': member.email},
    })


@login_required
@require_POST
def hr_panel_remove(request, vacancy_id):
    vacancy = get_object_or_404(Vacancy, id=vacancy_id)
    user_id = request.POST.get('user_id', '').strip()
    entry = InterviewPanel.objects.filter(vacancy=vacancy, member_id=user_id, is_active=True).first()
    if not entry:
        return JsonResponse({'error': 'Panel member not found.'}, status=404)

    entry.is_active = False
    entry.save(update_fields=['is_active'])

    InterviewLog.objects.create(
        vacancy=vacancy, performed_by=request.user,
        action='panel_removed',
        notes=f'{_display_name(entry.member)} removed from interview panel.',
        metadata={'member_id': str(entry.member.pk)},
        performed_by_label=_display_name(request.user),
    )
    return JsonResponse({'success': True})


@login_required
@require_POST
def hr_panel_notify(request, vacancy_id):
    vacancy = get_object_or_404(Vacancy, id=vacancy_id)
    schedule = get_object_or_404(InterviewSchedule, vacancy=vacancy)

    panel = InterviewPanel.objects.filter(vacancy=vacancy, is_active=True, notified=False).select_related('member')
    sent = 0
    errors = []
    for entry in panel:
        try:
            _notify_panel_member(entry, schedule, vacancy)
            entry.notified = True
            entry.notified_at = timezone.now()
            entry.save(update_fields=['notified', 'notified_at'])
            InterviewLog.objects.create(
                vacancy=vacancy, performed_by=request.user,
                action='panel_notified',
                notes=f'{_display_name(entry.member)} notified of panel assignment.',
                metadata={'member_id': str(entry.member.pk)},
                performed_by_label=_display_name(request.user),
            )
            sent += 1
        except Exception as e:
            errors.append(f'{_display_name(entry.member)}: {e}')

    schedule.panel_notified = True
    schedule.panel_notified_at = timezone.now()
    schedule.save(update_fields=['panel_notified', 'panel_notified_at'])

    return JsonResponse({'success': True, 'sent': sent, 'errors': errors})


@login_required
def hr_panel_staff_search(request, vacancy_id):
    from django.contrib.auth import get_user_model
    from django.db.models import Q
    User = get_user_model()
    vacancy = get_object_or_404(Vacancy, id=vacancy_id)
    q = request.GET.get('q', '').strip()

    if len(q) < 2:
        return JsonResponse({'results': []})

    existing_ids = InterviewPanel.objects.filter(
        vacancy=vacancy, is_active=True,
    ).values_list('member_id', flat=True)

    users = User.objects.filter(is_active=True).exclude(id__in=existing_ids).filter(
        Q(first_name__icontains=q) | Q(last_name__icontains=q) | Q(email__icontains=q)
    )[:10]

    return JsonResponse({
        'results': [{'id': str(u.pk), 'name': _display_name(u), 'email': u.email} for u in users]
    })


@login_required
@require_POST
def hr_criteria_save(request, vacancy_id):
    vacancy = get_object_or_404(Vacancy, id=vacancy_id)
    try:
        payload = json.loads(request.body)
        criteria = payload.get('criteria', [])
    except (json.JSONDecodeError, AttributeError):
        return JsonResponse({'error': 'Invalid JSON.'}, status=400)

    if not criteria:
        return JsonResponse({'error': 'At least one criterion is required.'}, status=400)

    for c in criteria:
        name = str(c.get('name', '')).strip()
        max_score = c.get('max_score')
        if not name:
            return JsonResponse({'error': 'Each criterion must have a name.'}, status=400)
        try:
            if int(max_score) < 1:
                raise ValueError
        except (TypeError, ValueError):
            return JsonResponse({'error': f'Invalid max_score for "{name}".'}, status=400)

    InterviewCriterion.objects.filter(vacancy=vacancy).delete()
    saved = []
    for i, c in enumerate(criteria):
        obj = InterviewCriterion.objects.create(
            vacancy=vacancy,
            name=str(c['name']).strip(),
            max_score=int(c['max_score']),
            order=i,
        )
        saved.append({'id': obj.id, 'name': obj.name, 'max_score': obj.max_score})

    return JsonResponse({'success': True, 'criteria': saved})


@login_required
@require_POST
def hr_slots_save(request, vacancy_id):
    vacancy = get_object_or_404(Vacancy, id=vacancy_id)
    try:
        payload = json.loads(request.body)
    except (json.JSONDecodeError, AttributeError):
        return JsonResponse({'error': 'Invalid JSON.'}, status=400)

    venue_type = payload.get('venue_type', 'physical')
    venue = payload.get('venue', '').strip()
    instructions = payload.get('instructions', '').strip()
    slots_data = payload.get('slots', [])

    if not venue:
        return JsonResponse({'error': 'Venue / meeting link is required.'}, status=400)
    if not slots_data:
        return JsonResponse({'error': 'At least one slot is required.'}, status=400)

    for s in slots_data:
        if not s.get('application_id') or not s.get('date') or not s.get('time'):
            return JsonResponse({'error': 'Each slot needs application_id, date and time.'}, status=400)

    schedule, created = InterviewSchedule.objects.update_or_create(
        vacancy=vacancy,
        defaults={
            'venue_type': venue_type, 'venue': venue,
            'instructions': instructions, 'created_by': request.user,
        },
    )

    InterviewLog.objects.create(
        vacancy=vacancy, performed_by=request.user,
        action='schedule_created' if created else 'schedule_updated',
        notes=f'Interview schedule {"created" if created else "updated"}.',
        metadata={'venue_type': venue_type},
        performed_by_label=_display_name(request.user),
    )

    saved_count = 0
    errors = []
    for s in slots_data:
        try:
            app = JobApplication.objects.get(
                pk=s['application_id'], vacancy=vacancy, status__code='shortlisted',
            )
            slot, slot_created = InterviewSlot.objects.update_or_create(
                vacancy=vacancy, application=app,
                defaults={
                    'schedule': schedule,
                    'interview_date': s['date'],
                    'interview_time': s['time'],
                    'venue_override': s.get('venue_override', '').strip(),
                    'notified': False,
                },
            )
            if not slot_created:
                slot.notified = False
                slot.notified_at = None
                slot.save(update_fields=['notified', 'notified_at'])
                # Reset schedule-level flag so "Email All" button reappears
                if schedule.candidates_notified:
                    schedule.candidates_notified = False
                    schedule.candidates_notified_at = None
                    schedule.save(update_fields=['candidates_notified', 'candidates_notified_at'])

            InterviewLog.objects.create(
                vacancy=vacancy, application=app, performed_by=request.user,
                action='slot_assigned',
                notes=f'Slot assigned: {s["date"]} {s["time"]}',
                metadata={'date': s['date'], 'time': s['time'], 'app_id': str(app.pk)},
                performed_by_label=_display_name(request.user),
            )
            saved_count += 1
        except JobApplication.DoesNotExist:
            errors.append(f'Application {s["application_id"]} not found or not shortlisted.')
        except Exception as e:
            errors.append(str(e))

    return JsonResponse({'success': True, 'saved': saved_count, 'errors': errors})


@login_required
@require_POST
def hr_interview_notify(request, vacancy_id):
    vacancy = get_object_or_404(Vacancy, id=vacancy_id)
    schedule = get_object_or_404(InterviewSchedule, vacancy=vacancy)

    slots = InterviewSlot.objects.filter(vacancy=vacancy, notified=False).select_related('application__user',
                                                                                         'schedule')
    sent = 0
    errors = []
    for slot in slots:
        try:
            _notify_candidate(slot, vacancy)
            slot.notified = True
            slot.notified_at = timezone.now()
            slot.save(update_fields=['notified', 'notified_at'])
            InterviewLog.objects.create(
                vacancy=vacancy, application=slot.application, performed_by=request.user,
                action='candidate_notified',
                notes=f'Interview notification sent to {slot.application.user.email}.',
                metadata={'app_id': str(slot.application.pk), 'date': str(slot.interview_date),
                          'time': str(slot.interview_time)},
                performed_by_label=_display_name(request.user),
            )
            sent += 1
        except Exception:
            logger.exception(
                "Failed to send interview notification for vacancy %s to %s",
                vacancy.id,
                slot.application.user.email,
            )
            errors.append(f'{slot.application.user.email}: notification failed')

    schedule.candidates_notified = True
    schedule.candidates_notified_at = timezone.now()
    schedule.save(update_fields=['candidates_notified', 'candidates_notified_at'])

    return JsonResponse({'success': True, 'sent': sent, 'errors': errors})


@login_required
def hr_interview_progress(request, vacancy_id):
    vacancy = get_object_or_404(Vacancy, id=vacancy_id)

    panel = list(
        InterviewPanel.objects.filter(vacancy=vacancy, is_active=True)
        .select_related('member').order_by('appointed_at')
    )
    applications = list(
        JobApplication.objects.filter(vacancy=vacancy, status__code='shortlisted')
        .select_related('user').order_by('application_number')
    )
    app_count = len(applications)
    criteria = list(InterviewCriterion.objects.filter(vacancy=vacancy))
    recused_ids = {e.member_id for e in panel if e.has_conflict}
    active_count = len([e for e in panel if not e.has_conflict])

    member_progress = []
    for entry in panel:
        if entry.has_conflict:
            member_progress.append({
                'entry': entry, 'name': _display_name(entry.member),
                'email': entry.member.email, 'is_recused': True,
                'has_conflict': True, 'conflict_reason': entry.conflict_reason,
                'acknowledged': entry.acknowledged, 'coi_declared': entry.coi_declared,
                'scores_submitted': False, 'submitted_count': 0, 'percent': 0,
            })
            continue

        submitted_apps = set()
        for app in applications:
            done = InterviewScore.objects.filter(
                vacancy=vacancy, application=app,
                panel_member=entry.member, is_draft=False,
            ).count()
            if done == len(criteria):
                submitted_apps.add(app.id)

        pct = int(len(submitted_apps) / app_count * 100) if app_count else 0
        member_progress.append({
            'entry': entry, 'name': _display_name(entry.member),
            'email': entry.member.email, 'is_recused': False,
            'has_conflict': False, 'conflict_reason': '',
            'acknowledged': entry.acknowledged, 'coi_declared': entry.coi_declared,
            'scores_submitted': entry.scores_submitted,
            'submitted_count': len(submitted_apps), 'percent': pct,
        })

    members_done = sum(1 for m in member_progress if not m['is_recused'] and m['scores_submitted'])
    all_scored = (members_done == active_count and active_count > 0)
    results_exist = InterviewResult.objects.filter(vacancy=vacancy).exists()

    if all_scored and not results_exist:
        _compute_interview_results(vacancy)
        results_exist = True

    all_scores_qs = InterviewScore.objects.filter(
        vacancy=vacancy, is_draft=False,
    ).exclude(panel_member_id__in=recused_ids).select_related('panel_member', 'criterion')

    scores_by_app = {}
    for s in all_scores_qs:
        scores_by_app.setdefault(s.application_id, []).append(s)

    results_by_app = {r.application_id: r for r in InterviewResult.objects.filter(vacancy=vacancy)}

    app_rows = []
    for app in applications:
        scores = scores_by_app.get(app.id, [])
        total = sum(s.score for s in scores) if scores else 0
        result = results_by_app.get(app.id)
        members_scored = len({s.panel_member_id for s in scores
                              if len([x for x in scores if x.panel_member_id == s.panel_member_id]) == len(criteria)})
        app_rows.append({'app': app, 'total': total, 'members_scored': members_scored, 'result': result})

    return render(request, 'recruitment/hr/interview/interview_progress.html', {
        'page': 'Interview Progress', 'vacancy': vacancy,
        'panel': member_progress, 'active_count': active_count,
        'recused_count': len(recused_ids), 'members_done': members_done,
        'all_scored': all_scored, 'app_count': app_count,
        'criteria': criteria, 'app_rows': app_rows, 'results_exist': results_exist,
    })


@login_required
def hr_interview_results(request, vacancy_id):
    vacancy = get_object_or_404(Vacancy, id=vacancy_id)

    results = list(
        InterviewResult.objects.filter(vacancy=vacancy)
        .select_related('application__user').order_by('rank')
    )
    criteria = list(InterviewCriterion.objects.filter(vacancy=vacancy))

    all_scores = InterviewScore.objects.filter(
        vacancy=vacancy, is_draft=False,
    ).select_related('panel_member', 'criterion')

    scores_map = {}
    for s in all_scores:
        scores_map.setdefault(s.application_id, {}).setdefault(
            s.panel_member_id, {}
        )[s.criterion_id] = s

    panel_members = list(
        InterviewPanel.objects.filter(vacancy=vacancy, is_active=True, has_conflict=False)
        .select_related('member')
    )

    result_rows = []
    for r in results:
        member_totals = []
        for pm in panel_members:
            member_scores = scores_map.get(r.application_id, {}).get(pm.member_id, {})
            subtotal = sum(s.score for s in member_scores.values()) if member_scores else None
            member_totals.append({'name': _display_name(pm.member), 'total': subtotal, 'scores': member_scores})
        result_rows.append({
            'result': r, 'app': r.application,
            'member_totals': member_totals,
            'is_top3': r.rank and r.rank <= 3,
        })

    return render(request, 'recruitment/hr/interview/interview_results.html', {
        'page': 'Interview Evaluation Summary', 'vacancy': vacancy,
        'result_rows': result_rows, 'criteria': criteria,
        'panel_members': panel_members, 'total_candidates': len(results),
    })


# ═════════════════════════════════════════════════════════════════════════════
# PANEL MEMBER PORTAL VIEWS
# ═════════════════════════════════════════════════════════════════════════════

def _panel_member_check(request, vacancy_id):
    """Return the active InterviewPanel entry for this user/vacancy, or None."""
    return InterviewPanel.objects.filter(
        member=request.user, vacancy_id=vacancy_id, is_active=True,
    ).select_related('vacancy').first()


@login_required
def panel_dashboard(request):
    assignments = InterviewPanel.objects.filter(
        member=request.user, is_active=True,
    ).select_related('vacancy').order_by('appointed_at')

    if not assignments.exists():
        return render(request, 'recruitment/panel/panel_dashboard.html', {
            'page': 'My Panel Assignments', 'assignments': [],
        })

    rows = []
    for entry in assignments:
        vacancy = entry.vacancy
        apps = JobApplication.objects.filter(vacancy=vacancy, status__code='shortlisted')
        app_count = apps.count()
        crit_count = InterviewCriterion.objects.filter(vacancy=vacancy).count()

        submitted_count = 0
        for app in apps:
            done = InterviewScore.objects.filter(
                vacancy=vacancy, application=app,
                panel_member=request.user, is_draft=False,
            ).count()
            if done == crit_count:
                submitted_count += 1

        if not entry.acknowledged:
            next_action = 'acknowledge'
        elif not entry.coi_declared:
            next_action = 'declare_coi'
        elif entry.has_conflict:
            next_action = 'recused'
        elif entry.scores_submitted:
            next_action = 'done'
        else:
            next_action = 'score'

        rows.append({
            'entry': entry, 'vacancy': vacancy,
            'app_count': app_count, 'submitted_count': submitted_count,
            'remaining': app_count - submitted_count,
            'percent': int(submitted_count / app_count * 100) if app_count else 0,
            'acknowledged': entry.acknowledged, 'coi_declared': entry.coi_declared,
            'has_conflict': entry.has_conflict, 'next_action': next_action,
        })

    return render(request, 'recruitment/panel/panel_dashboard.html', {
        'page': 'My Panel Assignments', 'assignments': rows,
    })


@login_required
@require_POST
def panel_acknowledge(request, vacancy_id):
    entry = _panel_member_check(request, vacancy_id)
    if not entry:
        return JsonResponse({'error': 'You are not on this panel.'}, status=403)

    if entry.acknowledged:
        return JsonResponse({'already': True, 'redirect_url': f'/recruitment/panel/vacancy/{vacancy_id}/coi/'})

    entry.acknowledged = True
    entry.acknowledged_at = timezone.now()
    entry.save(update_fields=['acknowledged', 'acknowledged_at'])

    InterviewLog.objects.create(
        vacancy=entry.vacancy, performed_by=request.user,
        action='member_acknowledged',
        notes=f'{_display_name(request.user)} acknowledged panel appointment.',
        metadata={'member_id': str(request.user.pk)},
        performed_by_label=_display_name(request.user),
    )
    return JsonResponse({'success': True, 'redirect_url': f'/recruitment/panel/vacancy/{vacancy_id}/coi/'})


@login_required
def panel_declare_coi(request, vacancy_id):
    entry = _panel_member_check(request, vacancy_id)
    if not entry:
        return render(request, 'recruitment/panel/not_assigned.html', {'page': 'Conflict of Interest Declaration'})

    if not entry.acknowledged:
        return redirect('panel_dashboard')

    if entry.coi_declared:
        if entry.has_conflict:
            return render(request, 'recruitment/panel/panel_coi.html', {
                'page': 'Conflict of Interest Declaration',
                'entry': entry, 'vacancy': entry.vacancy, 'already_declared': True,
            })
        return redirect('panel_score', vacancy_id=vacancy_id)

    if request.method == 'POST':
        decision = request.POST.get('decision', '').strip()
        reason = request.POST.get('conflict_reason', '').strip()

        if decision not in ('no_conflict', 'has_conflict'):
            return render(request, 'recruitment/panel/panel_coi.html', {
                'page': 'Conflict of Interest Declaration',
                'entry': entry, 'vacancy': entry.vacancy,
                'error': 'Please select one of the options below.',
            })

        if decision == 'has_conflict' and not reason:
            return render(request, 'recruitment/panel/panel_coi.html', {
                'page': 'Conflict of Interest Declaration',
                'entry': entry, 'vacancy': entry.vacancy,
                'error': 'You must provide a reason when declaring a conflict.',
                'decision_pre': 'has_conflict',
            })

        has_conflict = (decision == 'has_conflict')
        entry.coi_declared = True
        entry.has_conflict = has_conflict
        entry.conflict_reason = reason if has_conflict else ''
        entry.conflict_declared_at = timezone.now()
        entry.save(update_fields=['coi_declared', 'has_conflict', 'conflict_reason', 'conflict_declared_at'])

        InterviewLog.objects.create(
            vacancy=entry.vacancy, performed_by=request.user,
            action='coi_declared',
            notes=(
                    f'{_display_name(request.user)} declared '
                    + ('a conflict of interest. Reason: ' + reason if has_conflict else 'no conflict of interest.')
            ),
            metadata={'member_id': str(request.user.pk), 'has_conflict': has_conflict},
            performed_by_label=_display_name(request.user),
        )

        if has_conflict:
            _notify_hr_panel_coi(entry, reason)
            return render(request, 'recruitment/panel/panel_coi.html', {
                'page': 'Conflict of Interest Declaration',
                'entry': entry, 'vacancy': entry.vacancy, 'just_recused': True,
            })

        return redirect('panel_score', vacancy_id=vacancy_id)

    return render(request, 'recruitment/panel/panel_coi.html', {
        'page': 'Conflict of Interest Declaration',
        'entry': entry, 'vacancy': entry.vacancy,
    })


@login_required
def panel_score(request, vacancy_id):
    entry = _panel_member_check(request, vacancy_id)
    if not entry:
        return render(request, 'recruitment/panel/not_assigned.html', {'page': 'Interview Scoring'})

    vacancy = entry.vacancy

    if not entry.acknowledged:
        return render(request, 'recruitment/panel/panel_acknowledge.html', {
            'page': 'Interview Scoring', 'entry': entry, 'vacancy': vacancy,
        })
    if not entry.coi_declared:
        return redirect('panel_declare_coi', vacancy_id=vacancy_id)
    if entry.has_conflict:
        return render(request, 'recruitment/panel/panel_coi.html', {
            'page': 'Interview Scoring', 'entry': entry,
            'vacancy': vacancy, 'already_declared': True,
        })
    if entry.scores_submitted:
        return redirect('panel_results', vacancy_id=vacancy_id)

    applications = list(
        JobApplication.objects.filter(vacancy=vacancy, status__code='shortlisted')
        .select_related('user').order_by('application_number')
    )
    criteria = list(InterviewCriterion.objects.filter(vacancy=vacancy))

    my_scores = {
        (s.application_id, s.criterion_id): s
        for s in InterviewScore.objects.filter(vacancy=vacancy, panel_member=request.user)
    }

    slots_by_app = {s.application_id: s for s in InterviewSlot.objects.filter(vacancy=vacancy)}

    fully_submitted_count = 0
    app_rows = []
    for app in applications:
        criterion_rows = []
        all_submitted = True
        any_draft = False

        for c in criteria:
            score_obj = my_scores.get((app.id, c.id))
            is_sub = bool(score_obj and not score_obj.is_draft)
            if not is_sub:
                all_submitted = False
            if score_obj and score_obj.is_draft:
                any_draft = True
            criterion_rows.append({'criterion': c, 'score_obj': score_obj, 'is_submitted': is_sub})

        if all_submitted:
            fully_submitted_count += 1

        other_scores = []
        if all_submitted:
            other_scores = list(
                InterviewScore.objects.filter(vacancy=vacancy, application=app, is_draft=False)
                .exclude(panel_member=request.user)
                .select_related('panel_member', 'criterion')
            )

        app_rows.append({
            'app': app, 'criterion_rows': criterion_rows,
            'all_submitted': all_submitted, 'any_draft': any_draft,
            'other_scores': other_scores, 'can_score': not all_submitted,
            'slot': slots_by_app.get(app.id),
        })

    app_count = len(applications)
    return render(request, 'recruitment/panel/panel_score.html', {
        'page': 'Interview Scoring', 'entry': entry, 'vacancy': vacancy,
        'schedule': InterviewSchedule.objects.filter(vacancy=vacancy).first(),
        'app_rows': app_rows, 'app_count': app_count, 'criteria': criteria,
        'fully_submitted_count': fully_submitted_count,
        'remaining': app_count - fully_submitted_count,
        'all_submitted': fully_submitted_count == app_count,
        'active_count': _active_panel_count(vacancy),
        'percent': int(fully_submitted_count / app_count * 100) if app_count else 0,
    })


@login_required
@require_POST
def panel_score_save(request, vacancy_id):
    entry = _panel_member_check(request, vacancy_id)
    if not entry:
        return JsonResponse({'error': 'Not authorised.'}, status=403)
    if not entry.coi_declared or entry.has_conflict:
        return JsonResponse({'error': 'Cannot score — COI not declared or recused.'}, status=403)
    if entry.scores_submitted:
        return JsonResponse({'error': 'You have already submitted all scores.'}, status=400)

    app_id = request.POST.get('application_id', '').strip()
    criterion_id = request.POST.get('criterion_id', '').strip()
    score_val = request.POST.get('score', '').strip()
    comment = request.POST.get('comment', '').strip()
    action = request.POST.get('action', 'draft')

    if not app_id or not criterion_id:
        return JsonResponse({'error': 'Missing application or criterion.'}, status=400)

    try:
        score_dec = Decimal(score_val)
        if score_dec < 0:
            raise ValueError
    except (InvalidOperation, ValueError):
        return JsonResponse({'error': 'Invalid score value.'}, status=400)

    try:
        application = JobApplication.objects.get(pk=app_id, vacancy_id=vacancy_id, status__code='shortlisted')
        criterion = InterviewCriterion.objects.get(pk=criterion_id, vacancy_id=vacancy_id)
    except (JobApplication.DoesNotExist, InterviewCriterion.DoesNotExist):
        return JsonResponse({'error': 'Application or criterion not found.'}, status=404)

    if score_dec > criterion.max_score:
        return JsonResponse({'error': f'Score cannot exceed {criterion.max_score} for "{criterion.name}".'}, status=400)

    is_draft = (action == 'draft')
    now = timezone.now()

    InterviewScore.objects.update_or_create(
        vacancy=entry.vacancy, application=application,
        panel_member=request.user, criterion=criterion,
        defaults={
            'score': score_dec, 'comment': comment,
            'is_draft': is_draft, 'scored_at': now,
            'submitted_at': None if is_draft else now,
        },
    )

    if not is_draft:
        InterviewLog.objects.create(
            vacancy=entry.vacancy, application=application, performed_by=request.user,
            action='score_submitted',
            notes=f'{criterion.name}: {score_dec}/{criterion.max_score}',
            metadata={'member_id': str(request.user.pk), 'criterion_id': criterion.pk, 'score': str(score_dec)},
            performed_by_label=_display_name(request.user),
        )

    return JsonResponse({'success': True, 'is_draft': is_draft, 'score': str(score_dec), 'max': criterion.max_score})


@login_required
@require_POST
def panel_submit_all(request, vacancy_id):
    entry = _panel_member_check(request, vacancy_id)
    if not entry:
        return JsonResponse({'error': 'Not authorised.'}, status=403)
    if not entry.coi_declared or entry.has_conflict:
        return JsonResponse({'error': 'Cannot submit — recused or COI not declared.'}, status=403)
    if entry.scores_submitted:
        return JsonResponse({'error': 'Already submitted.'}, status=400)

    vacancy = entry.vacancy
    criteria = list(InterviewCriterion.objects.filter(vacancy=vacancy))

    applications = JobApplication.objects.filter(vacancy=vacancy, status__code='shortlisted')
    incomplete = []
    for app in applications:
        submitted = InterviewScore.objects.filter(
            vacancy=vacancy, application=app,
            panel_member=request.user, is_draft=False,
        ).count()
        if submitted < len(criteria):
            incomplete.append(str(app.application_number))

    if incomplete:
        return JsonResponse({
            'error': f'{len(incomplete)} candidate(s) still have incomplete scores. Please submit all criteria for each candidate before finalising.'
        }, status=400)

    entry.scores_submitted = True
    entry.scores_submitted_at = timezone.now()
    entry.save(update_fields=['scores_submitted', 'scores_submitted_at'])

    total_active = InterviewPanel.objects.filter(vacancy=vacancy, is_active=True, has_conflict=False).count()
    done_active = InterviewPanel.objects.filter(vacancy=vacancy, is_active=True, has_conflict=False,
                                                scores_submitted=True).count()

    results_generated = False
    if done_active == total_active and total_active > 0:
        _compute_interview_results(vacancy)
        results_generated = True

    return JsonResponse({
        'success': True, 'results_generated': results_generated,
        'redirect_url': f'/recruitment/panel/vacancy/{vacancy_id}/results/',
    })


@login_required
def panel_results(request, vacancy_id):
    entry = _panel_member_check(request, vacancy_id)
    if not entry:
        return render(request, 'recruitment/panel/not_assigned.html', {'page': 'Results'})

    vacancy = entry.vacancy
    results = list(InterviewResult.objects.filter(vacancy=vacancy).select_related('application__user').order_by('rank'))
    criteria = list(InterviewCriterion.objects.filter(vacancy=vacancy))

    my_scores = {
        (s.application_id, s.criterion_id): s
        for s in InterviewScore.objects.filter(vacancy=vacancy, panel_member=request.user, is_draft=False)
    }

    app_rows = []
    for r in results:
        criterion_scores = [{'criterion': c, 'score_obj': my_scores.get((r.application_id, c.id))} for c in criteria]
        app_rows.append({
            'result': r, 'app': r.application,
            'criterion_scores': criterion_scores,
            'my_total': sum(s['score_obj'].score for s in criterion_scores if s['score_obj']),
            'is_top3': r.rank and r.rank <= 3,
        })

    total_active = InterviewPanel.objects.filter(vacancy=vacancy, is_active=True, has_conflict=False).count()
    done_active = InterviewPanel.objects.filter(vacancy=vacancy, is_active=True, has_conflict=False,
                                                scores_submitted=True).count()

    return render(request, 'recruitment/panel/panel_results.html', {
        'page': 'Interview Results', 'entry': entry, 'vacancy': vacancy,
        'app_rows': app_rows, 'criteria': criteria,
        'all_done': done_active == total_active,
        'my_max': sum(c.max_score for c in criteria),
    })


# ═══════════════════════════════════════════════════════════════════════════════
# 2. HR SUBMIT TO CEO
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
@role_required(['hod_hr'])
def hr_submit_to_ceo(request, vacancy_id):
    """
    HR reviews ranked interview results and selects up to 3 candidates for
    CEO review. An override (selecting below rank 3) requires a written reason.
    Advances vacancy status → 'ceo_review'.
    """
    vacancy = get_object_or_404(Vacancy, id=vacancy_id)

    if vacancy.status not in ('interview_scheduling', 'interviews'):
        messages.error(request, "Vacancy is not at the interviews stage.")
        return redirect('hr_dashboard')

    # Ensure results exist
    results = list(
        InterviewResult.objects.filter(vacancy=vacancy)
        .select_related('application__user', 'application__status')
        .order_by('rank')
    )

    if not results:
        messages.error(
            request,
            "No interview results found. Ensure all panel members have submitted scores."
        )
        return redirect('hr_interview_results', vacancy_id=vacancy_id)

    criteria = list(InterviewCriterion.objects.filter(vacancy=vacancy))
    panel_members = list(
        InterviewPanel.objects.filter(
            vacancy=vacancy, is_active=True, has_conflict=False,
        ).select_related('member')
    )

    # Per-candidate score breakdown (for display)
    all_scores = InterviewScore.objects.filter(
        vacancy=vacancy, is_draft=False,
    ).select_related('panel_member', 'criterion')

    scores_map = {}
    for s in all_scores:
        scores_map.setdefault(s.application_id, {}).setdefault(
            s.panel_member_id, {}
        )[s.criterion_id] = s

    result_rows = []
    for r in results:
        member_totals = []
        for pm in panel_members:
            member_scores = scores_map.get(r.application_id, {}).get(pm.member_id, {})
            subtotal = sum(s.score for s in member_scores.values()) if member_scores else None
            member_totals.append({'name': _display_name(pm.member), 'total': subtotal})
        b = r.application.snapshot_basic or {}
        full_name = ' '.join(filter(None, [
            b.get('first_name', ''), b.get('second_name', ''), b.get('surname', ''),
        ])) or r.application.user.email
        result_rows.append({
            'result': r,
            'app': r.application,
            'full_name': full_name,
            'member_totals': member_totals,
            'is_top3': r.rank and r.rank <= 3,
        })

    total_candidates = len(result_rows)
    top_n = min(3, total_candidates)

    if request.method == 'POST':
        selected_ids = request.POST.getlist('selected_ids')
        override_reason = request.POST.get('override_reason', '').strip()

        # ── Validation ───────────────────────────────────────────────────────
        if not selected_ids:
            return render(request, 'recruitment/hr/interview/submit_to_ceo.html', {
                'page': 'Submit to CEO', 'vacancy': vacancy,
                'result_rows': result_rows, 'top_n': top_n,
                'criteria': criteria, 'panel_members': panel_members,
                'total_candidates': total_candidates,
                'error': 'Please select at least one candidate.',
            })

        if len(selected_ids) > 3:
            return render(request, 'recruitment/hr/interview/submit_to_ceo.html', {
                'page': 'Submit to CEO', 'vacancy': vacancy,
                'result_rows': result_rows, 'top_n': top_n,
                'criteria': criteria, 'panel_members': panel_members,
                'total_candidates': total_candidates,
                'error': 'You may select a maximum of 3 candidates for CEO review.',
            })

        # FIX: result_rows is a list of dicts — use r['app'], not r.app
        top3_app_ids = {str(r['app'].id) for r in result_rows if r['is_top3']}
        has_override = any(sid not in top3_app_ids for sid in selected_ids)

        if has_override and not override_reason:
            return render(request, 'recruitment/hr/interview/submit_to_ceo.html', {
                'page': 'Submit to CEO', 'vacancy': vacancy,
                'result_rows': result_rows, 'top_n': top_n,
                'criteria': criteria, 'panel_members': panel_members,
                'total_candidates': total_candidates,
                'error': 'A written reason is required when selecting a candidate outside the top 3.',
            })

        # ── Status objects ───────────────────────────────────────────────────
        top_candidate_status = _get_job_status('top_candidate')
        interviewed_status = _get_job_status('interviewed')

        if not top_candidate_status:
            messages.error(
                request,
                "System error: 'top_candidate' application status not found. "
                "Run: python manage.py seed_application_statuses"
            )
            return redirect('hr_interview_results', vacancy_id=vacancy_id)

        with transaction.atomic():
            # Reset any previous top_candidate selections for this vacancy
            prev_top = JobApplication.objects.filter(
                vacancy=vacancy, status__code='top_candidate'
            )
            for app in prev_top:
                old = app.status
                app.status = interviewed_status
                app.save(update_fields=['status'])
                JobApplicationStatusLog.objects.create(
                    application=app, from_status=old, to_status=interviewed_status,
                    changed_by=request.user,
                    notes='Top-candidate selection cleared (re-submission to CEO).',
                )

            # Mark selected apps as top_candidate
            for app_id in selected_ids:
                try:
                    app = JobApplication.objects.select_related('status').get(
                        pk=app_id, vacancy=vacancy
                    )
                    old_status = app.status
                    app.status = top_candidate_status
                    app.save(update_fields=['status'])

                    is_override = app_id not in top3_app_ids
                    try:
                        rank = InterviewResult.objects.get(vacancy=vacancy, application=app).rank
                    except InterviewResult.DoesNotExist:
                        rank = '?'

                    JobApplicationStatusLog.objects.create(
                        application=app,
                        from_status=old_status,
                        to_status=top_candidate_status,
                        changed_by=request.user,
                        notes=(
                            f'Selected for CEO review (rank #{rank}). '
                            + (f'Override — reason: {override_reason}' if is_override
                               else 'Within top 3 ranked candidates.')
                        ),
                    )
                    InterviewLog.objects.create(
                        vacancy=vacancy, application=app,
                        performed_by=request.user,
                        action='top_candidate_selected',
                        notes=(
                            f'Selected for CEO review. Rank #{rank}.'
                            + (f' Override: {override_reason}' if is_override else '')
                        ),
                        metadata={
                            'app_id': str(app.pk),
                            'rank': rank,
                            'is_override': is_override,
                            'override_reason': override_reason,
                        },
                        performed_by_label=_display_name(request.user),
                    )

                except JobApplication.DoesNotExist:
                    logger.warning(
                        f"hr_submit_to_ceo: app {app_id} not found for vacancy {vacancy_id}"
                    )

            # Advance vacancy → ceo_review
            vacancy.status = 'ceo_review'
            vacancy.save(update_fields=['status'])

            InterviewLog.objects.create(
                vacancy=vacancy,
                performed_by=request.user,
                action='submitted_to_ceo',
                notes=(
                    f'{len(selected_ids)} candidate(s) submitted to CEO for review.'
                    + (f' Override applied — {override_reason}' if has_override else '')
                ),
                metadata={
                    'selected_ids': selected_ids,
                    'has_override': has_override,
                    'override_reason': override_reason,
                },
                performed_by_label=_display_name(request.user),
            )

        messages.success(
            request,
            f"{len(selected_ids)} candidate(s) submitted to CEO for review. "
            f"Vacancy is now in CEO Review stage."
        )
        return redirect('hr_dashboard')

    return render(request, 'recruitment/hr/interview/submit_to_ceo.html', {
        'page': 'Submit to CEO',
        'vacancy': vacancy,
        'result_rows': result_rows,
        'top_n': top_n,
        'total_candidates': total_candidates,
        'criteria': criteria,
        'panel_members': panel_members,
    })


# ═══════════════════════════════════════════════════════════════════════════════
# 3. CEO DASHBOARD (replacement — uses JobApplication)
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
@role_required(['ceo'])
def ceo_dashboard(request):
    """
    CEO landing page. Shows all vacancies currently awaiting CEO selection.
    Also shows vacancies CEO has already actioned (ceo_approved) for reference.
    """
    pending = Vacancy.objects.filter(status='ceo_review').order_by('-created_at')
    actioned = Vacancy.objects.filter(status='ceo_approved').order_by('-created_at')[:10]

    pending_data = []
    for v in pending:
        candidates = JobApplication.objects.filter(
            vacancy=v, status__code='top_candidate'
        ).count()
        pending_data.append({'vacancy': v, 'candidate_count': candidates})

    return render(request, 'recruitment/ceo/ceo_dashboard.html', {
        'page': 'CEO Dashboard',
        'pending_data': pending_data,
        'actioned': actioned,
        'pending_count': len(pending_data),
    })


# ═══════════════════════════════════════════════════════════════════════════════
# 4. CEO VACANCY REVIEW
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
@role_required(['ceo'])
def ceo_vacancy_review(request, vacancy_id):
    """
    CEO sees the top candidates presented by HR, with full score breakdowns.
    They can also see all other interviewed candidates if they wish to override.
    """
    vacancy = get_object_or_404(Vacancy, id=vacancy_id)

    if vacancy.status not in ('ceo_review', 'ceo_approved'):
        messages.error(request, "This vacancy is not currently in CEO review stage.")
        return redirect('ceo_dashboard')

    # Top candidates submitted by HR
    top_apps = list(
        JobApplication.objects
        .filter(vacancy=vacancy, status__code='top_candidate')
        .select_related('user', 'status')
    )

    # All interviewed candidates (for override selection)
    all_interviewed = list(
        JobApplication.objects
        .filter(vacancy=vacancy, status__code__in=['interviewed', 'top_candidate', 'not_selected'])
        .select_related('user', 'status')
    )

    criteria = list(InterviewCriterion.objects.filter(vacancy=vacancy))
    panel_count = InterviewPanel.objects.filter(
        vacancy=vacancy, is_active=True, has_conflict=False,
    ).count()

    # Results (scores) keyed by application id
    results_by_app = {
        r.application_id: r
        for r in InterviewResult.objects.filter(vacancy=vacancy)
    }

    all_scores = InterviewScore.objects.filter(
        vacancy=vacancy, is_draft=False,
    ).select_related('panel_member', 'criterion')

    scores_map = {}
    for s in all_scores:
        scores_map.setdefault(s.application_id, {}).setdefault(
            s.panel_member_id, {}
        )[s.criterion_id] = s

    def _build_row(app):
        b = app.snapshot_basic or {}
        full_name = ' '.join(filter(None, [
            b.get('first_name', ''), b.get('second_name', ''), b.get('surname', ''),
        ])) or app.user.email
        result = results_by_app.get(app.id)
        member_scores_data = scores_map.get(app.id, {})
        crit_totals = {}
        for pm_id, crit_dict in member_scores_data.items():
            for crit_id, score_obj in crit_dict.items():
                crit_totals[crit_id] = crit_totals.get(crit_id, Decimal('0')) + score_obj.score
        return {
            'app': app,
            'full_name': full_name,
            'id_no': b.get('id_no', '—'),
            'result': result,
            'rank': result.rank if result else None,
            'total': result.total_score if result else Decimal('0'),
            'pct': result.percentage if result else Decimal('0'),
            'crit_totals': crit_totals,
            'is_top': app.status.code == 'top_candidate',
        }

    top_rows = sorted(
        [_build_row(a) for a in top_apps],
        key=lambda r: r['rank'] or 999,
    )
    all_rows = sorted(
        [_build_row(a) for a in all_interviewed],
        key=lambda r: r['rank'] or 999,
    )

    # Check if CEO has already made a selection
    already_selected = JobApplication.objects.filter(
        vacancy=vacancy, status__code='ceo_selected'
    ).select_related('user').first()

    return render(request, 'recruitment/ceo/ceo_vacancy_review.html', {
        'page': 'CEO Review',
        'vacancy': vacancy,
        'top_rows': top_rows,
        'all_rows': all_rows,
        'criteria': criteria,
        'panel_count': panel_count,
        'already_selected': already_selected,
        'can_select': vacancy.status == 'ceo_review',
    })


# ═══════════════════════════════════════════════════════════════════════════════
# 5. CEO MAKE SELECTION (POST)
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
@role_required(['ceo'])
@require_POST
def ceo_make_selection(request, vacancy_id):
    vacancy = get_object_or_404(Vacancy, id=vacancy_id, status='ceo_review')

    selected_id = request.POST.get('selected_id', '').strip()
    override_reason = request.POST.get('override_reason', '').strip()

    if not selected_id:
        return JsonResponse({'error': 'No candidate selected.'}, status=400)

    try:
        selected_app = JobApplication.objects.select_related('status').get(
            pk=selected_id, vacancy=vacancy
        )
    except JobApplication.DoesNotExist:
        return JsonResponse({'error': 'Application not found.'}, status=404)

    is_override = (selected_app.status.code != 'top_candidate')

    if is_override and not override_reason:
        return JsonResponse(
            {'error': 'A written reason is required when selecting a candidate '
                      'outside the HR-recommended list.'},
            status=400,
        )

    ceo_selected_status = _get_job_status('ceo_selected')
    not_selected_status = _get_job_status('not_selected')

    if not ceo_selected_status or not not_selected_status:
        return JsonResponse(
            {'error': 'System error: missing status codes. '
                      'Run seed_application_statuses.'},
            status=500,
        )

    b = selected_app.snapshot_basic or {}
    winner_name = ' '.join(filter(None, [
        b.get('first_name', ''), b.get('surname', ''),
    ])) or selected_app.user.email

    try:
        rank = InterviewResult.objects.get(
            vacancy=vacancy, application=selected_app
        ).rank
    except InterviewResult.DoesNotExist:
        rank = '?'

    with transaction.atomic():
        # All top_candidate + interviewed apps → not_selected (except winner)
        other_apps = JobApplication.objects.filter(
            vacancy=vacancy,
            status__code__in=['top_candidate', 'interviewed'],
        ).exclude(pk=selected_id).select_related('status')

        for app in other_apps:
            old = app.status
            app.status = not_selected_status
            app.save(update_fields=['status'])
            JobApplicationStatusLog.objects.create(
                application=app,
                from_status=old,
                to_status=not_selected_status,
                changed_by=request.user,
                notes=f'Not selected by CEO. Appointed candidate: {winner_name}.',
            )

        # Mark winner
        old_status = selected_app.status
        selected_app.status = ceo_selected_status
        selected_app.save(update_fields=['status'])

        JobApplicationStatusLog.objects.create(
            application=selected_app,
            from_status=old_status,
            to_status=ceo_selected_status,
            changed_by=request.user,
            notes=(
                    f'Selected by CEO (rank #{rank}).'
                    + (f' Override — reason: {override_reason}' if is_override else '')
            ),
        )

        vacancy.status = 'ceo_approved'
        vacancy.save(update_fields=['status'])

        InterviewLog.objects.create(
            vacancy=vacancy,
            application=selected_app,
            performed_by=request.user,
            action='ceo_selection_made',
            notes=(
                    f'CEO selected {winner_name} (rank #{rank}).'
                    + (f' Override: {override_reason}'
                       if is_override else ' From HR-recommended list.')
            ),
            metadata={
                'selected_app_id': str(selected_app.pk),
                'selected_name': winner_name,
                'rank': rank,
                'is_override': is_override,
                'override_reason': override_reason,
                'not_selected_count': other_apps.count(),
            },
            performed_by_label=_display_name(request.user),
        )

    # ── Notify HR by email (outside transaction) ─────────────────────────────
    _notify_hr_ceo_selection(
        vacancy=vacancy,
        winner_app=selected_app,
        winner_name=winner_name,
        is_override=is_override,
        override_reason=override_reason,
        selected_by=request.user,
    )

    return JsonResponse({
        'success': True,
        'winner': winner_name,
        'is_override': is_override,
        'redirect_url': '/recruitment/ceo/dashboard/',
    })


# ═══════════════════════════════════════════════════════════════════════════════
# 6. HR APPOINTMENTS LIST
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
@role_required(['hod_hr'])
def hr_appointments_list(request):
    """
    HR sees all vacancies in 'ceo_approved' stage, ready for appointment issuance.
    """
    vacancies = Vacancy.objects.filter(status='ceo_approved').order_by('-created_at')

    vacancy_data = []
    for v in vacancies:
        winner = JobApplication.objects.filter(
            vacancy=v, status__code='ceo_selected',
        ).select_related('user').first()
        vacancy_data.append({'vacancy': v, 'winner': winner})

    return render(request, 'recruitment/hr/appointment/appointments_list.html', {
        'page': 'Appointments',
        'vacancy_data': vacancy_data,
    })


# ═══════════════════════════════════════════════════════════════════════════════
# 7. HR ISSUE APPOINTMENT (GET preview + POST confirm)
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
@role_required(['hod_hr'])
def hr_issue_appointment(request, vacancy_id):
    vacancy = get_object_or_404(Vacancy, id=vacancy_id)

    if vacancy.status != 'ceo_approved':
        messages.error(request, "This vacancy is not in the CEO-approved stage.")
        return redirect('hr_appointments_list')

    winner = JobApplication.objects.filter(
        vacancy=vacancy, status__code='ceo_selected',
    ).select_related('user', 'status').first()

    if not winner:
        messages.error(
            request,
            "No CEO-selected candidate found for this vacancy."
        )
        return redirect('hr_appointments_list')

    b = winner.snapshot_basic or {}
    winner_name = ' '.join(filter(None, [
        b.get('first_name', ''), b.get('second_name', ''), b.get('surname', ''),
    ])) or winner.user.email

    try:
        result = InterviewResult.objects.get(vacancy=vacancy, application=winner)
    except InterviewResult.DoesNotExist:
        result = None

    if request.method == 'POST':
        appointed_status = _get_job_status('appointed')
        if not appointed_status:
            messages.error(
                request,
                "System error: 'appointed' status not found. "
                "Run seed_application_statuses."
            )
            return redirect('hr_appointments_list')

        with transaction.atomic():
            old_status = winner.status
            winner.status = appointed_status
            winner.save(update_fields=['status'])

            JobApplicationStatusLog.objects.create(
                application=winner,
                from_status=old_status,
                to_status=appointed_status,
                changed_by=request.user,
                notes=f'Appointment issued by HR ({_display_name(request.user)}).',
            )

            vacancy.status = 'appointed'
            vacancy.save(update_fields=['status'])

            InterviewLog.objects.create(
                vacancy=vacancy,
                application=winner,
                performed_by=request.user,
                action='appointment_issued',
                notes=f'Appointment issued to {winner_name}.',
                metadata={
                    'app_id': str(winner.pk),
                    'winner_name': winner_name,
                },
                performed_by_label=_display_name(request.user),
            )

        # ── Emails outside transaction ────────────────────────────────────────

        # 1. Appointment email to winner (collect letter + upload to portal)
        _send_appointment_email_v2(winner, vacancy, winner_name)

        # 2. Regret emails to candidates who reached CEO stage but lost.
        #    Find them via status log: top_candidate → not_selected for this vacancy.
        ceo_stage_losers = JobApplication.objects.filter(
            vacancy=vacancy,
            status__code='not_selected',
            status_logs__from_status__code='top_candidate',
            status_logs__to_status__code='not_selected',
        ).distinct().select_related('user')

        regret_count = 0
        for loser in ceo_stage_losers:
            _send_ceo_stage_regret(loser, vacancy)
            regret_count += 1

        logger.info(
            f"hr_issue_appointment: vacancy {vacancy.id} — "
            f"appointment issued to {winner_name}, "
            f"{regret_count} CEO-stage regret email(s) sent."
        )

        messages.success(
            request,
            f"Appointment issued to {winner_name}. "
            f"Notification email sent. "
            f"{regret_count} regret email(s) sent to other CEO-stage candidate(s)."
        )
        return redirect('hr_dashboard')

    # GET — preview
    return render(request, 'recruitment/hr/appointment/issue_appointment.html', {
        'page': 'Issue Appointment',
        'vacancy': vacancy,
        'winner': winner,
        'winner_name': winner_name,
        'result': result,
        'basic': b,
        'additional': winner.snapshot_additional or {},
        'academic': winner.snapshot_academic or [],
        'referees': winner.snapshot_referees or [],
    })


# ═══════════════════════════════════════════════════════════════════════════════
# HELPER — appointment email (new version for JobApplication flow)
# ═══════════════════════════════════════════════════════════════════════════════

def _send_appointment_email_v2(application, vacancy, winner_name):
    """
    Congratulations email to the appointed candidate.
    Instructs them to collect their letter from HR and upload
    the signed copy to their portal.
    """
    try:
        from django.conf import settings as django_settings
        site_url = getattr(django_settings, 'SITE_URL', 'https://portal.ufaa.go.ke')
    except Exception:
        site_url = 'https://portal.ufaa.go.ke'

    subject = f'Congratulations — Appointment Offer | {vacancy.title} | UFAA'

    message_html = f"""
        <p>Dear <strong>{winner_name}</strong>,</p>

        <p>
            We are delighted to inform you that following the completion of the
            competitive recruitment process for the position of
            <strong>{vacancy.title}</strong>
            (Reference: <strong>{vacancy.reference_number}</strong>),
            you have been <strong>selected for appointment</strong> to this role.
        </p>

        <div style="background:#f0f9f4;border-left:4px solid #1a7a45;
                    border-radius:0 .5rem .5rem 0;padding:1rem 1.25rem;margin:1.25rem 0;">
            <div style="font-size:.68rem;font-weight:700;color:#52906b;
                        text-transform:uppercase;letter-spacing:.06em;margin-bottom:.3rem;">
                Application Reference
            </div>
            <div style="font-size:.9rem;font-weight:700;color:#1a5c38;">
                {application.application_number}
            </div>
        </div>

        <div style="background:#fff8e1;border:1px solid #ffe082;border-radius:.5rem;
                    padding:1rem 1.25rem;margin:1.25rem 0;">
            <div style="font-size:.78rem;font-weight:700;color:#6d4c00;
                        text-transform:uppercase;letter-spacing:.04em;margin-bottom:.75rem;">
                📋 Next Steps
            </div>

            <div style="font-size:.82rem;color:#344767;margin-bottom:.6rem;
                        display:flex;align-items:flex-start;gap:.6rem;">
                <span style="background:#C39545;color:#fff;width:20px;height:20px;
                             border-radius:50%;font-size:.65rem;font-weight:700;
                             display:inline-flex;align-items:center;justify-content:center;
                             flex-shrink:0;margin-top:.1rem;">1</span>
                <span>
                    Visit the <strong>UFAA HR Office</strong> to collect your
                    formal appointment letter. Please bring a valid form of
                    identification.
                </span>
            </div>

            <div style="font-size:.82rem;color:#344767;margin-bottom:.6rem;
                        display:flex;align-items:flex-start;gap:.6rem;">
                <span style="background:#C39545;color:#fff;width:20px;height:20px;
                             border-radius:50%;font-size:.65rem;font-weight:700;
                             display:inline-flex;align-items:center;justify-content:center;
                             flex-shrink:0;margin-top:.1rem;">2</span>
                <span>
                    Review and sign the appointment letter.
                </span>
            </div>

            <div style="font-size:.82rem;color:#344767;
                        display:flex;align-items:flex-start;gap:.6rem;">
                <span style="background:#C39545;color:#fff;width:20px;height:20px;
                             border-radius:50%;font-size:.65rem;font-weight:700;
                             display:inline-flex;align-items:center;justify-content:center;
                             flex-shrink:0;margin-top:.1rem;">3</span>
                <span>
                    Log in to the <strong>UFAA Recruitment Portal</strong> and
                    upload the signed copy of your appointment letter under
                    <em>My Applications → Documents</em>.
                </span>
            </div>
        </div>

        <p style="font-size:.85rem;color:#344767;">
            If you have any questions about the appointment process, please
            contact the UFAA Human Resources Department directly.
        </p>

        <p>
            <a href="{site_url}/recruitment/job-status/"
               style="background:#262561;color:#F9E6A1;padding:.6rem 1.4rem;
                      border-radius:.4rem;text-decoration:none;font-weight:600;
                      font-size:.85rem;display:inline-block;">
                Go to Your Portal
            </a>
        </p>

        <p style="margin-top:1.5rem;">
            Congratulations and welcome to the UFAA team.<br><br>
            <strong>UFAA Human Resources Department</strong><br>
            <span style="color:#67748e;font-size:.82rem;">
                Unclaimed Financial Assets Authority
            </span>
        </p>
    """

    try:
        _send_html_email(subject, application.user.email, message_html)
    except Exception as e:
        logger.error(
            f'Appointment email failed for {application.user.email}: {e}',
            exc_info=True,
        )


def _notify_hr_ceo_selection(vacancy, winner_app, winner_name, is_override,
                             override_reason, selected_by):
    """Email HR to notify them the CEO has made their selection."""
    try:
        from django.conf import settings as django_settings
        hr_email = getattr(django_settings, 'HR_NOTIFICATION_EMAIL',
                           django_settings.DEFAULT_FROM_EMAIL)

        result = None
        try:
            result = InterviewResult.objects.get(
                vacancy=vacancy, application=winner_app
            )
        except InterviewResult.DoesNotExist:
            pass

        override_block = ''
        if is_override:
            override_block = f"""
            <div style="background:#fff3cd;border:1px solid #ffe082;border-radius:.5rem;
                        padding:.75rem 1rem;margin:1rem 0;font-size:.82rem;color:#7d5500;">
                <strong><i class="fas fa-exclamation-triangle"></i> Override Applied</strong><br>
                The selected candidate was outside the HR-recommended shortlist.<br>
                <strong>CEO's reason:</strong> {override_reason}
            </div>
            """

        rank_line = f"Rank #{result.rank} — {result.total_score}/{result.max_possible} ({result.percentage}%)" \
            if result else "Score data unavailable"

        subject = (f"CEO Selection Made — {vacancy.title} "
                   f"[{vacancy.reference_number}]")

        message_html = f"""
            <p>Dear HR,</p>
            <p>
                <strong>{_display_name(selected_by)}</strong> has made their
                candidate selection for the following vacancy:
            </p>
            <table style="border-collapse:collapse;width:100%;margin:1rem 0;">
                <tr>
                    <td style="padding:.5rem 1rem;background:#f8f9ff;font-weight:600;
                               border:1px solid #e0e4ef;width:35%;">Position</td>
                    <td style="padding:.5rem 1rem;border:1px solid #e0e4ef;">
                        {vacancy.title}
                    </td>
                </tr>
                <tr>
                    <td style="padding:.5rem 1rem;background:#f8f9ff;font-weight:600;
                               border:1px solid #e0e4ef;">Reference</td>
                    <td style="padding:.5rem 1rem;border:1px solid #e0e4ef;
                               font-family:monospace;">
                        {vacancy.reference_number}
                    </td>
                </tr>
                <tr>
                    <td style="padding:.5rem 1rem;background:#f8f9ff;font-weight:600;
                               border:1px solid #e0e4ef;">Selected Candidate</td>
                    <td style="padding:.5rem 1rem;border:1px solid #e0e4ef;
                               font-weight:700;color:#262561;">
                        {winner_name}
                    </td>
                </tr>
                <tr>
                    <td style="padding:.5rem 1rem;background:#f8f9ff;font-weight:600;
                               border:1px solid #e0e4ef;">Application No.</td>
                    <td style="padding:.5rem 1rem;border:1px solid #e0e4ef;
                               font-family:monospace;">
                        {winner_app.application_number}
                    </td>
                </tr>
                <tr>
                    <td style="padding:.5rem 1rem;background:#f8f9ff;font-weight:600;
                               border:1px solid #e0e4ef;">Interview Score</td>
                    <td style="padding:.5rem 1rem;border:1px solid #e0e4ef;">
                        {rank_line}
                    </td>
                </tr>
            </table>

            {override_block}

            <p>
                The vacancy is now in <strong>CEO Approved</strong> status.
                Please proceed to the appointments module to issue the formal
                appointment letter.
            </p>
            <p style="margin-top:1.5rem;">
                <a href="/recruitment/hr/appointments/"
                   style="background:#262561;color:#F9E6A1;padding:.6rem 1.4rem;
                          border-radius:.4rem;text-decoration:none;font-weight:600;
                          font-size:.85rem;display:inline-block;">
                    Go to Appointments
                </a>
            </p>
            <p style="margin-top:1.5rem;color:#67748e;font-size:.82rem;">
                This is an automated notification from the UFAA Recruitment Portal.
            </p>
        """

        _send_html_email(subject, hr_email, message_html)

    except Exception as e:
        logger.error(
            f'HR CEO-selection notification failed for vacancy {vacancy.id}: {e}',
            exc_info=True,
        )

def _send_ceo_stage_regret(application, vacancy):
    """
    Regret email sent to candidates who reached CEO review stage
    but were not selected. Called from hr_issue_appointment.
    """
    try:
        b = application.snapshot_basic or {}
        candidate_name = ' '.join(filter(None, [
            b.get('first_name', ''), b.get('surname', ''),
        ])) or application.user.email

        subject = (f"Application Outcome — {vacancy.title} "
                   f"[{vacancy.reference_number}]")

        message_html = f"""
            <p>Dear <strong>{candidate_name}</strong>,</p>
            <p>
                Thank you for participating in the recruitment process for the
                position of <strong>{vacancy.title}</strong>
                (Reference: <strong>{vacancy.reference_number}</strong>) at UFAA.
            </p>
            <div style="background:#f8f9ff;border-left:4px solid #8392ab;
                        border-radius:0 .5rem .5rem 0;
                        padding:1rem 1.25rem;margin:1.25rem 0;">
                <div style="font-size:.68rem;font-weight:700;color:#8392ab;
                            text-transform:uppercase;letter-spacing:.06em;
                            margin-bottom:.3rem;">Application Reference</div>
                <div style="font-size:.9rem;font-weight:700;color:#262561;">
                    {application.application_number}
                </div>
            </div>
            <p style="font-size:.88rem;color:#344767;line-height:1.65;">
                We write to inform you that, following the conclusion of the
                full recruitment process — including shortlisting, interviews,
                and final review — the position has been offered to another
                candidate whose overall profile most closely matched the
                requirements of the role at this time.
            </p>
            <p style="font-size:.88rem;color:#344767;line-height:1.65;">
                We wish to acknowledge the considerable effort you invested
                throughout this process, particularly at the interview stage.
                Reaching this stage is a significant achievement and reflects
                well on your qualifications and experience.
            </p>
            <div style="background:#f0f2f8;border-radius:.5rem;
                        padding:1rem 1.25rem;margin:1.25rem 0;">
                <div style="font-size:.78rem;font-weight:700;color:#262561;
                            text-transform:uppercase;letter-spacing:.04em;
                            margin-bottom:.5rem;">Future Opportunities</div>
                <p style="font-size:.82rem;color:#344767;line-height:1.6;margin:0;">
                    We encourage you to continue monitoring our recruitment
                    portal for future vacancies. Your profile remains active
                    and you are welcome to apply for positions that match your
                    skills and aspirations.
                </p>
            </div>
            <p style="margin-top:1.5rem;">
                Yours sincerely,<br>
                <strong>UFAA Human Resources Department</strong><br>
                <span style="color:#67748e;font-size:.82rem;">
                    Unclaimed Financial Assets Authority
                </span>
            </p>
        """

        _send_html_email(subject, application.user.email, message_html)

    except Exception as e:
        logger.error(
            f'CEO-stage regret email failed for {application.user.email}: {e}',
            exc_info=True,
        )





