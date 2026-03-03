import json
import os
from datetime import datetime

from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404
from django.http import JsonResponse
from django.utils import timezone

from accounts.models import User, JobseekerAccount
from core.decorators import role_required
from recruitment.utils import check_and_lock_application
from roles.models import Role
from .models import Application, Appointment, CEODecision, Gender, EthnicGroup, InterviewScore, \
    ProfessionalQualification, ShortlistVote, WorkHistory, AdditionalDetail, ProfessionalBodyMembership, Referee
from .models import County, Constituency, SubCounty, Ward, JobSeekerProfile, AcademicQualification, \
    EducationLevel, DocumentType, Document
from .services import aggregate_shortlist, build_profile_snapshot, is_shortlisting_complete

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

    return render(request, 'jobseekers/jobs.html', {'vacancies': vacancies})


def instrutions_view(request):
    return render(request, 'jobseekers/instructions.html')


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
    }
    return render(request, 'jobseekers/dashboard.html', context)


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
    """Return additional-details completion as 0–100."""
    if not detail:
        return 0
    score = 0
    if detail.cv:           score += 5
    if detail.cover_letter: score += 4
    if detail.linkedin_url: score += 2
    if detail.availability: score += 2
    if detail.languages:    score += 2
    return min(int(score / 15 * 100), 100)


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
            salutation = request.POST.get('salutation', '').strip()
            surname = request.POST.get('surname', '').strip()
            first_name = request.POST.get('first_name', '').strip()
            second_name = request.POST.get('second_name', '').strip()
            id_no = request.POST.get('id_no', '').strip()
            date_of_birth = request.POST.get('date_of_birth') or None
            gender_id = request.POST.get('gender') or None
            ethnic_group_id = request.POST.get('ethnic_group') or None
            home_county_id = request.POST.get('home_county') or None
            constituency_id = request.POST.get('constituency') or None
            sub_county_id = request.POST.get('sub_county') or None
            ward_id = request.POST.get('ward') or None
            disability_status = request.POST.get('disability_status', '').strip()
            disability_other = request.POST.get('disability_other', '').strip()
            disability_no = request.POST.get('disability_no', '').strip()
            is_employee = request.POST.get('is_employee') == 'true'
            employee_number = request.POST.get('employee_number', '').strip()
            phone_number = request.POST.get('phone_number', '').strip()

            # ── Validations ───────────────────────────────────
            if not first_name:
                return JsonResponse({'status': 'error',
                                     'message': 'First name is required.'})
            if not surname:
                return JsonResponse({'status': 'error',
                                     'message': 'Surname is required.'})
            if not id_no:
                return JsonResponse({'status': 'error',
                                     'message': 'ID number is required.'})
            if not date_of_birth:
                return JsonResponse({'status': 'error',
                                     'message': 'Date of birth is required.'})
            if not phone_number:
                return JsonResponse({'status': 'error',
                                     'message': 'Phone number is required.'})
            if is_employee and not employee_number:
                return JsonResponse({'status': 'error',
                                     'message': 'Please enter your UFAA employee number.'})
            if disability_status == 'Other' and not disability_other:
                return JsonResponse({'status': 'error',
                                     'message': 'Please describe your disability.'})

            # Disability no — clear if no disability
            has_disability = disability_status not in ('', 'None')

            # ── Save profile ──────────────────────────────────
            profile.salutation = salutation
            profile.surname = surname
            profile.first_name = first_name
            profile.second_name = second_name
            profile.email = user.email
            profile.id_no = id_no
            profile.date_of_birth = date_of_birth
            profile.gender_id = gender_id
            profile.ethnic_group_id = ethnic_group_id
            profile.home_county_id = home_county_id
            profile.constituency_id = constituency_id
            profile.sub_county_id = sub_county_id
            profile.ward_id = ward_id
            profile.disability_status = disability_status
            profile.disability_other = disability_other if disability_status == 'Other' else ''
            profile.disability_no = disability_no if has_disability else ''
            profile.employee_number = employee_number if is_employee else ''
            profile.phone_number = phone_number
            profile.save()

            # Save is_employee on account
            JobseekerAccount.objects.filter(id=user.id).update(is_employee=is_employee)

            return JsonResponse({
                'status': 'success',
                'message': 'Profile saved successfully.',
                'completion': calculate_profile_completion(user),
            })

        except Exception as e:
            return JsonResponse({'status': 'error',
                                 'message': f'Something went wrong: {str(e)}'})

    context = {
        'profile': profile,
        'user': user,
        'page': 'Profile',
        'counties': County.objects.all(),
        'constituencies': Constituency.objects.all(),
        'sub_counties': SubCounty.objects.all(),
        'wards': Ward.objects.all(),
        'genders': Gender.objects.all(),
        'ethnic_groups': EthnicGroup.objects.all(),
        'completion': completion,
        'has_academic': AcademicQualification.objects.filter(user=user).exists(),
        'has_professional': ProfessionalQualification.objects.filter(user=user).exists(),
        'has_work_history': WorkHistory.objects.filter(user=user).exists(),
        'has_additional': AdditionalDetail.objects.filter(user=user).exists(),
        'has_memberships': ProfessionalBodyMembership.objects.filter(user=user).exists(),
        'has_referees': Referee.objects.filter(user=user).count() >= 2,
    }
    return render(request, 'jobseekers/profile.html', context)


# ── Academic Qualifications ──────────────────────────────────
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
                return JsonResponse({
                    'status': 'success',
                    'message': 'Qualification deleted successfully.',
                })

            except Exception as e:
                return JsonResponse({'status': 'error', 'message': f'Error: {str(e)}'})

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

                # New documents uploaded during edit
                files = request.FILES.getlist('edit_files')
                doc_types = request.POST.getlist('edit_doc_types')
                doc_count = Document.objects.filter(user=user).count()

                for i, file in enumerate(files):
                    doc_type_id = doc_types[i] if i < len(doc_types) else None
                    doc_type = DocumentType.objects.filter(id=doc_type_id).first()
                    if file and doc_type:
                        Document.objects.create(
                            user=user,
                            profile=profile,
                            document_type=doc_type,
                            file=file,
                        )
                        doc_count += 1

                # Re-count docs linked to this qualification (approximate by user for now)
                total_docs = Document.objects.filter(user=user).count()

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
                        'doc_count': total_docs,
                    }
                })

            except Exception as e:
                return JsonResponse({'status': 'error', 'message': f'Error: {str(e)}'})

        # ── SAVE NEW ─────────────────────────────────────────
        try:
            qualifications = json.loads(request.POST.get('qualifications', '[]'))
            level_count = int(request.POST.get('level_count', 0))

            if not qualifications:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Please add at least one qualification.'
                })

            saved = []

            for idx, q in enumerate(qualifications):
                education_level = EducationLevel.objects.filter(
                    id=q.get('education_level')).first()

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

                # Documents per level
                files = request.FILES.getlist(f'level_files_{idx}')
                doc_types = request.POST.getlist(f'level_doc_types_{idx}')
                doc_count = 0

                for i, file in enumerate(files):
                    doc_type_id = doc_types[i] if i < len(doc_types) else None
                    doc_type = DocumentType.objects.filter(id=doc_type_id).first()
                    if file and doc_type:
                        Document.objects.create(
                            user=user,
                            profile=profile,
                            document_type=doc_type,
                            file=file,
                        )
                        doc_count += 1

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
                    'doc_count': doc_count,
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
            return JsonResponse({'status': 'error', 'message': f'Something went wrong: {str(e)}'})

    # ── GET ───────────────────────────────────────────────────
    existing_qualifications = AcademicQualification.objects.filter(user=user).select_related(
        'education_level').order_by('education_level__rank')
    existing_documents = Document.objects.filter(user=user)

    context = {
        'profile': profile,
        'user': user,
        'page': 'Academic Qualifications',
        'education_levels': EducationLevel.objects.all().order_by('rank'),
        'document_types': DocumentType.objects.all(),
        'existing_qualifications': existing_qualifications,
        'existing_documents': existing_documents,
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
    return render(request, 'jobseekers/academic.html', context)


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
        if detail.cv:            score += 4
        if detail.cover_letter:  score += 3
        if detail.linkedin_url:  score += 1
        if detail.availability:  score += 1
        if detail.languages:     score += 1

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
                qual = ProfessionalQualification.objects.filter(
                    id=qual_id, user=user).first()
                if not qual:
                    return JsonResponse({'status': 'error',
                                         'message': 'Qualification not found.'})
                qual.delete()
                return JsonResponse({'status': 'success',
                                     'message': 'Qualification deleted successfully.'})
            except Exception as e:
                return JsonResponse({'status': 'error', 'message': str(e)})

        # ── EDIT ─────────────────────────────────────────────
        if action == 'edit':
            try:
                qual_id = request.POST.get('qual_id')
                qual = ProfessionalQualification.objects.filter(
                    id=qual_id, user=user).first()
                if not qual:
                    return JsonResponse({'status': 'error',
                                         'message': 'Qualification not found.'})

                qualification = request.POST.get('qualification', '').strip()
                awarding_body = request.POST.get('awarding_body', '').strip()
                year_obtained = request.POST.get('year_obtained', '').strip()

                if not qualification:
                    return JsonResponse({'status': 'error',
                                         'message': 'Qualification name is required.'})
                if not awarding_body:
                    return JsonResponse({'status': 'error',
                                         'message': 'Awarding body is required.'})
                if not year_obtained:
                    return JsonResponse({'status': 'error',
                                         'message': 'Year obtained is required.'})

                expiry_raw = request.POST.get('expiry_year', '').strip()

                qual.qualification = qualification
                qual.awarding_body = awarding_body
                qual.year_obtained = year_obtained
                qual.expiry_year = int(expiry_raw) if expiry_raw else None
                qual.grade = request.POST.get('grade', '').strip()
                qual.cert_number = request.POST.get('cert_number', '').strip()
                qual.country = request.POST.get('country', 'Kenya').strip() or 'Kenya'
                qual.save()

                # New documents uploaded during edit
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
                        )

                doc_count = Document.objects.filter(user=user).count()

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
                        'doc_count': doc_count,
                    }
                })

            except Exception as e:
                return JsonResponse({'status': 'error', 'message': str(e)})

        # ── SAVE NEW ─────────────────────────────────────────
        try:
            qualifications = json.loads(request.POST.get('qualifications', '[]'))

            if not qualifications:
                return JsonResponse({'status': 'error',
                                     'message': 'Please add at least one qualification.'})

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

                # Documents per qualification
                files = request.FILES.getlist(f'qual_files_{idx}')
                doc_types = request.POST.getlist(f'qual_doc_types_{idx}')
                doc_count = 0

                for i, file in enumerate(files):
                    doc_type_id = doc_types[i] if i < len(doc_types) else None
                    doc_type = DocumentType.objects.filter(id=doc_type_id).first()
                    if file and doc_type:
                        Document.objects.create(
                            user=user,
                            profile=profile,
                            document_type=doc_type,
                            file=file,
                        )
                        doc_count += 1

                saved.append({
                    'id': qual.id,
                    'qualification': qual.qualification,
                    'awarding_body': qual.awarding_body,
                    'year_obtained': qual.year_obtained,
                    'expiry_year': qual.expiry_year or '',
                    'grade': qual.grade or '',
                    'cert_number': qual.cert_number or '',
                    'country': qual.country,
                    'doc_count': doc_count,
                })

            if not saved:
                return JsonResponse({'status': 'error',
                                     'message': 'No valid qualifications saved. '
                                                'Check all required fields.'})

            return JsonResponse({
                'status': 'success',
                'message': f'{len(saved)} qualification(s) saved successfully.',
                'saved': saved,
            })

        except Exception as e:
            return JsonResponse({'status': 'error',
                                 'message': f'Something went wrong: {str(e)}'})

    # ── GET ───────────────────────────────────────────────────
    existing = ProfessionalQualification.objects.filter(user=user)

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
    return render(request, 'jobseekers/professional.html', context)


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
                return JsonResponse({'status': 'error', 'message': str(e)})

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
                return JsonResponse({'status': 'error', 'message': str(e)})

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
            return JsonResponse({'status': 'error',
                                 'message': f'Something went wrong: {str(e)}'})

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
    return render(request, 'jobseekers/work_history.html', context)


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
                return JsonResponse({'status': 'error', 'message': str(e)})

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
                return JsonResponse({'status': 'error', 'message': str(e)})

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
        'has_memberships': ProfessionalBodyMembership.objects.filter(user=user).exists(),
        'has_referees': Referee.objects.filter(user=user).count() >= 2,
    }
    return render(request, 'jobseekers/membership.html', context)


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
            # ── Collect both referees first ───────────────────
            refs_data = {}
            for no in [1, 2]:
                refs_data[no] = {
                    'name': request.POST.get(f'ref{no}_name', '').strip(),
                    'occupation': request.POST.get(f'ref{no}_occupation', '').strip(),
                    'mobile': request.POST.get(f'ref{no}_mobile', '').strip(),
                    'email': request.POST.get(f'ref{no}_email', '').strip(),
                    'period_known': request.POST.get(f'ref{no}_period_known', '').strip(),
                }

            # ── Validate BOTH before saving EITHER ───────────
            for no in [1, 2]:
                d = refs_data[no]
                if not all([d['name'], d['occupation'], d['mobile'],
                            d['email'], d['period_known']]):
                    return JsonResponse({
                        'status': 'error',
                        'message': f'All fields for Referee {no} are required. '
                                   f'Both referees must be complete before saving.'
                    })

            # ── Both valid — now save ─────────────────────────
            saved = []
            for no in [1, 2]:
                d = refs_data[no]
                referee, _ = Referee.objects.update_or_create(
                    user=user,
                    referee_no=no,
                    defaults={
                        'name': d['name'],
                        'occupation': d['occupation'],
                        'mobile': d['mobile'],
                        'email': d['email'],
                        'period_known': d['period_known'],
                    }
                )
                saved.append(_referee_to_dict(referee))

            return JsonResponse({
                'status': 'success',
                'message': 'Referee details saved successfully.',
                'completion': calculate_profile_completion(user),
                'saved': saved,
            })

        except Exception as e:
            return JsonResponse({'status': 'error',
                                 'message': f'Something went wrong: {str(e)}'})

    # ── GET ───────────────────────────────────────────────────
    ref1 = Referee.objects.filter(user=user, referee_no=1).first()
    ref2 = Referee.objects.filter(user=user, referee_no=2).first()

    period_choices = Referee.PERIOD_CHOICES

    context = {
        'profile': profile,
        'user': user,
        'page': 'Referees',
        'ref1': ref1,
        'ref2': ref2,
        'period_choices': period_choices,
        'completion': completion,
        'has_academic': AcademicQualification.objects.filter(user=user).exists(),
        'has_professional': ProfessionalQualification.objects.filter(user=user).exists(),
        'has_work_history': WorkHistory.objects.filter(user=user).exists(),
        'has_memberships': ProfessionalBodyMembership.objects.filter(user=user).exists(),
        'has_referees': Referee.objects.filter(user=user).count() >= 2,
        'has_additional': AdditionalDetail.objects.filter(user=user).exists(),
    }
    return render(request, 'jobseekers/referee.html', context)


def _referee_to_dict(ref):
    """Serialise a Referee for JSON responses."""
    return {
        'id': ref.id,
        'referee_no': ref.referee_no,
        'name': ref.name,
        'occupation': ref.occupation,
        'mobile': ref.mobile,
        'email': ref.email,
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

        # ── DELETE CV ─────────────────────────────────────────
        if action == 'delete_cv':
            try:
                if detail and detail.cv:
                    if os.path.isfile(detail.cv.path):
                        os.remove(detail.cv.path)
                    detail.cv = None
                    detail.save()
                return JsonResponse({'status': 'success',
                                     'message': 'CV removed successfully.'})
            except Exception as e:
                return JsonResponse({'status': 'error', 'message': str(e)})

        # ── SAVE / UPDATE ─────────────────────────────────────
        try:
            cover_letter = request.POST.get('cover_letter', '').strip()
            linkedin_url = request.POST.get('linkedin_url', '').strip()
            portfolio_url = request.POST.get('portfolio_url', '').strip()
            languages_raw = request.POST.get('languages', '').strip()
            availability = request.POST.get('availability', '').strip()
            salary_raw = request.POST.get('expected_salary', '').strip()
            cv_file = request.FILES.get('cv')

            # Validate CV if uploaded
            if cv_file:
                ext = '.' + cv_file.name.split('.')[-1].lower()
                if ext != '.pdf':
                    return JsonResponse({'status': 'error',
                                         'message': 'CV must be a PDF file.'})
                if cv_file.size > 2 * 1024 * 1024:
                    return JsonResponse({'status': 'error',
                                         'message': 'CV must be smaller than 2MB.'})

            # Clean languages — remove blanks, de-dupe
            languages = ', '.join(
                dict.fromkeys(
                    l.strip().title()
                    for l in languages_raw.split(',')
                    if l.strip()
                )
            )

            expected_salary = int(salary_raw) if salary_raw.isdigit() else None

            if detail:
                # Replace CV file if new one uploaded
                if cv_file:
                    if detail.cv and os.path.isfile(detail.cv.path):
                        os.remove(detail.cv.path)
                    detail.cv = cv_file

                detail.cover_letter = cover_letter
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
                    cover_letter=cover_letter,
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
                'completion': new_completion,
            })

        except Exception as e:
            return JsonResponse({'status': 'error',
                                 'message': f'Something went wrong: {str(e)}'})

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
    return render(request, 'jobseekers/additional.html', context)


@login_required
@role_required(['hod_hr'])
# @permission_required("view_reports")
def hr_dashboard(request):
    vacancies = Vacancy.objects.all()  # Or filter(status='draft') if you only want drafts
    context = {
        'vacancies': vacancies,
        'open_vacancies_count': Vacancy.objects.filter(status='open').count(),
        'pending_ceo_count': Vacancy.objects.filter(status='pending_ceo_approval').count(),
        'appointed_count': Vacancy.objects.filter(status='appointed').count(),
    }
    return render(request, 'recruitment/hr/dashboard.html', context)


# @login_required
# @role_required(['panelist'])
# def panelist_dashboard(request):
#     vacancies = Vacancy.objects.filter(
#         panel_assignments__panelist=request.user,
#         status='interviews'
#     ).distinct()

#     return render(request, 'recruitment/panelist/dashboard.html', {
#         'vacancies': vacancies
#     })
@login_required
@role_required(['panelist'])
def panelist_dashboard(request):

    vacancies = Vacancy.objects.filter(
        panel_assignments__panelist=request.user,
        status='interviews'
    ).distinct()

    assignments = PanelAssignment.objects.filter(
        panelist=request.user
    ).select_related('vacancy')

    return render(request, 'recruitment/panelist/dashboard.html', {
        'vacancies': vacancies,
        'assignments': assignments
    })


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
def respond_panel_assignment(request, assignment_id):

    assignment = get_object_or_404(
        PanelAssignment,
        id=assignment_id,
        panelist=request.user
    )

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'accept':
            assignment.status = 'accepted'
            assignment.responded_at = timezone.now()
            assignment.save()
            messages.success(request, "You accepted the panel assignment.")

        elif action == 'decline':
            reason = request.POST.get('reason')
            assignment.status = 'declined'
            assignment.decline_reason = reason
            assignment.responded_at = timezone.now()
            assignment.save()
            messages.warning(request, "You declined the panel assignment.")

        return redirect('panelist_dashboard')

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
def create_vacancy(request):
    if request.method == 'POST':
        title = request.POST.get('title')
        reference_number = request.POST.get('reference_number')
        description = request.POST.get('description')
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date')
        advert_pdf = request.FILES.get('advert_pdf')

        # ---- Validation ----

        if not all([title, reference_number, description, start_date, end_date]):
            messages.error(request, "All fields are required.")
            return redirect('create_vacancy')

        # Validate PDF
        if advert_pdf:
            if not advert_pdf.name.lower().endswith('.pdf'):
                messages.error(request, "Only PDF files are allowed.")
                return redirect('create_vacancy')

        # Validate Dates
        try:
            start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
            end_date = datetime.strptime(end_date, "%Y-%m-%d").date()
        except ValueError:
            messages.error(request, "Invalid date format.")
            return redirect('create_vacancy')

        today = timezone.now().date()

        if start_date < today:
            messages.error(request, "Start date cannot be in the past.")
            return redirect('create_vacancy')

        if end_date <= start_date:
            messages.error(request, "End date must be after start date.")
            return redirect('create_vacancy')

        # Prevent duplicate reference numbers
        if Vacancy.objects.filter(reference_number=reference_number).exists():
            messages.error(request, "Reference number already exists.")
            return redirect('create_vacancy')

        # ---- Save Vacancy ----
        Vacancy.objects.create(
            title=title,
            reference_number=reference_number,
            description=description,
            advert_pdf=advert_pdf,
            start_date=start_date,
            end_date=end_date,
            created_by=request.user,
            status='draft'
        )

        messages.success(request, "Vacancy created successfully as Draft.")
        return redirect('hr_dashboard')

    return render(request, 'recruitment/hr/create_vacancy.html')


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
def update_vacancy(request, vacancy_id):
    vacancy = get_object_or_404(Vacancy, id=vacancy_id)

    # if vacancy.status != 'draft':
    #     messages.error(request, "Only draft vacancies can be edited.")
    #     return redirect('hr_dashboard')

    if request.method == 'POST':
        # Get values from HTML form
        title = request.POST.get('title')
        reference_number = request.POST.get('reference_number')
        description = request.POST.get('description')
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date')
        advert_pdf = request.FILES.get('advert_pdf')

        # --- Basic validation ---
        if not all([title, reference_number, description, start_date, end_date]):
            messages.error(request, "All fields are required.")
            return redirect('update_vacancy', vacancy_id=vacancy.id)

        try:
            start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
            end_date = datetime.strptime(end_date, "%Y-%m-%d").date()
        except ValueError:
            messages.error(request, "Invalid date format.")
            return redirect('update_vacancy', vacancy_id=vacancy.id)

        today = timezone.now().date()
        if start_date < today:
            messages.error(request, "Start date cannot be in the past.")
            return redirect('update_vacancy', vacancy_id=vacancy.id)
        if end_date <= start_date:
            messages.error(request, "End date must be after start date.")
            return redirect('update_vacancy', vacancy_id=vacancy.id)

        # Update the vacancy
        vacancy.title = title
        vacancy.reference_number = reference_number
        vacancy.description = description
        vacancy.start_date = start_date
        vacancy.end_date = end_date
        if advert_pdf:
            if not advert_pdf.name.lower().endswith('.pdf'):
                messages.error(request, "Only PDF files are allowed.")
                return redirect('update_vacancy', vacancy_id=vacancy.id)
            vacancy.advert_pdf = advert_pdf

        vacancy.save()
        messages.success(request, "Vacancy updated successfully.")
        return redirect('hr_dashboard')

    return render(request, 'recruitment/hr/update_vacancy.html', {'vacancy': vacancy})


@login_required
@role_required(['hod_hr'])
def delete_vacancy(request, vacancy_id):
    vacancy = get_object_or_404(Vacancy, id=vacancy_id)

    # if vacancy.status != 'draft':
    #     messages.error(request, "Only draft vacancies can be deleted.")
    #     return redirect('hr_dashboard')

    if request.method == 'POST':
        vacancy.delete()
        messages.success(request, "Vacancy deleted successfully.")
        return redirect('hr_dashboard')

    return render(request, 'recruitment/hr/confirm_delete.html', {'vacancy': vacancy})


@login_required
@role_required(['hod_hr'])
def publish_vacancy(request, vacancy_id):
    vacancy = get_object_or_404(Vacancy, id=vacancy_id)

    if vacancy.status != 'draft':
        messages.error(request, "Only draft vacancies can be published.")
        return redirect('hr_dashboard')

    vacancy.status = 'open'
    vacancy.save()
    messages.success(request, "Vacancy published successfully.")
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

    # user = JobseekerAccount.objects.filter(id=user_id).first()
    user = JobseekerAccount.objects.filter(pk=user_id).first()
    # # Check if vacancy is open
    # if not vacancy.is_open():
    #     messages.error(request, "This vacancy is no longer open.")
    #     return redirect('public_vacancies')

    # # Restrict internal vacancies
    # if vacancy.vacancy_type == 'internal' and request.user.role == 'applicant':
    #     messages.error(request, "You cannot apply for internal vacancies.")
    #     return redirect('public_vacancies')

    # # Prevent duplicate application (DB + view)
    # if Application.objects.filter(vacancy=vacancy, applicant=request.user).exists():
    #     messages.error(request, "You have already applied for this vacancy.")
    #     return redirect('public_vacancies')

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
# @role_required(['hod_hr'])
def hr_view_applications(request, vacancy_id):
    vacancy = get_object_or_404(Vacancy, id=vacancy_id)

    # if vacancy.status not in ['closed', 'longlisting', 'shortlisting', 'interviews']:
    #     messages.error(request, "Applications not available for review yet.")
    #     return redirect('hr_dashboard')

    applications = Application.objects.filter(vacancy=vacancy) \
    #     .select_related(
    #     "applicant",
    #     "applicant__profile",
    #     "applicant__additional_detail"
    # ).prefetch_related(
    #     "applicant__academic_qualifications",
    #     "applicant__work_history",
    #     "applicant__professional_qualifications",
    #     "applicant__documents"
    # )

    return render(request, 'recruitment/hr/view_applications.html', {
        'vacancy': vacancy,
        'applications': applications
    })


# HR View to Move Vacancy to Longlisting
# @login_required
# @role_required(['hod_hr'])
# def start_longlisting(request, vacancy_id):
#     vacancy = get_object_or_404(Vacancy, id=vacancy_id)

#     if vacancy.status != 'open':
#         messages.error(request, "Vacancy must be open to start longlisting.")
#         return redirect('hr_dashboard')

#     vacancy.move_to('longlisting')
#     messages.success(request, "Vacancy moved to Longlisting stage.")
#     return redirect('longlist_candidates', vacancy_id=vacancy.id)

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
    return redirect('hr_view_applications', vacancy_id=vacancy.id)

@login_required
@role_required(['hod_hr'])
def shortlist_candidates(request, vacancy_id):
    vacancy = get_object_or_404(Vacancy, id=vacancy_id)

    if vacancy.status != 'longlisting':
        messages.error(request, "Not in longlisting stage.")
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

    return render(request, 'recruitment/hr/shortlist.html', {
        'vacancy': vacancy,
        'applications': applications
    })


from django.contrib.auth import get_user_model

User = get_user_model()


@login_required
@role_required(['hod_hr'])
def appoint_panelists(request, vacancy_id):
    vacancy = get_object_or_404(Vacancy, id=vacancy_id)

    if vacancy.status != 'shortlisting':
        messages.error(request, "Complete shortlisting first.")
        return redirect('hr_dashboard')

    # panelists = User.objects.filter(role__name='panelist')
    panelist_role = get_object_or_404(Role, name='panelist')

    panelists = User.objects.filter(
        user_type=2,
        role=panelist_role
    )

    if request.method == 'POST':
        selected_panelists = request.POST.getlist('panelists')

        PanelAssignment.objects.filter(vacancy=vacancy).delete()

        for user_id in selected_panelists:
            PanelAssignment.objects.create(
                vacancy=vacancy,
                panelist_id=user_id
            )

        vacancy.status = 'interviews'
        vacancy.save()

        messages.success(request, "Panel appointed. Interview stage started.")
        return redirect('hr_dashboard')

    # Already assigned panelists for this vacancy
    assigned_panelists = User.objects.filter(
        panelassignment__vacancy=vacancy
    )

    return render(request, 'recruitment/hr/appoint_panel.html', {
        'vacancy': vacancy,
        'panelists': panelists,
        'assigned_panelists': assigned_panelists
    })


@login_required
@role_required(['hod_hr'])
def appoint_committee(request, vacancy_id):
    vacancy = get_object_or_404(Vacancy, id=vacancy_id)

    if vacancy.status != 'shortlisting':
        messages.error(request, "Complete shortlisting first.")
        return redirect('hr_dashboard')

    # panelists = User.objects.filter(role__name='panelist')
    panelist_role = get_object_or_404(Role, name='panelist')

    panelists = User.objects.filter(
        user_type=2,
        role=panelist_role
    )

    if request.method == 'POST':
        selected_panelists = request.POST.getlist('panelists')

        PanelAssignment.objects.filter(vacancy=vacancy).delete()

        for user_id in selected_panelists:
            PanelAssignment.objects.create(
                vacancy=vacancy,
                panelist_id=user_id
            )

        vacancy.status = 'interviews'
        vacancy.save()

        messages.success(request, "Panel appointed. Interview stage started.")
        return redirect('hr_dashboard')

    # Already assigned panelists for this vacancy
    assigned_panelists = User.objects.filter(
        panelassignment__vacancy=vacancy
    )

    return render(request, 'recruitment/hr/appoint_panel.html', {
        'vacancy': vacancy,
        'panelists': panelists,
        'assigned_panelists': assigned_panelists
    })

@login_required
@role_required(['hod_hr'])
def appointed_committee(request, vacancy_id):
    vacancy = get_object_or_404(Vacancy, id=vacancy_id)

    if vacancy.status != 'shortlisting':
        messages.error(request, "Complete shortlisting first.")
        return redirect('vacancy_shortlisting')

    panelist_role = get_object_or_404(Role, name='panelist')
    panelists = User.objects.filter(user_type=2, role=panelist_role)

    if request.method == 'POST':
        selected_panelists = request.POST.getlist('panelists')
        PanelAssignment.objects.filter(vacancy=vacancy).delete()
        for user_id in selected_panelists:
            PanelAssignment.objects.create(vacancy=vacancy, panelist_id=user_id)
        vacancy.status = 'interviews'
        vacancy.save()
        messages.success(request, "Panel appointed. Interview stage started.")
        return redirect('vacancy_interviews')

    assigned_panelists = User.objects.filter(panelassignment__vacancy=vacancy)

    return render(request, 'recruitment/hr/appoint_panel.html', {
        'vacancy': vacancy,
        'panelists': panelists,
        'assigned_panelists': assigned_panelists
    })


@login_required
@role_required(['hod_hr'])
def manage_panelists(request):
    panelist_role = get_object_or_404(Role, name='panelist')

    internal_users = User.objects.filter(user_type=2)

    if request.method == "POST":
        selected_users = request.POST.getlist("panelists")

        # Remove role from everyone first
        for user in internal_users:
            user.role.remove(panelist_role)

        # Assign role to selected users
        for user_id in selected_users:
            user = User.objects.get(id=user_id, user_type=2)
            user.role.add(panelist_role)

        messages.success(request, "Panelist role updated successfully.")
        return redirect("manage_panelists")

    # Users who already have role
    current_panelists = internal_users.filter(role=panelist_role)

    return render(request, "hr/manage_panelists.html", {
        "internal_users": internal_users,
        "current_panelists": current_panelists
    })

@login_required
@role_required(['panelist'])
def submit_shortlist(request, vacancy_id):

    vacancy = get_object_or_404(Vacancy, id=vacancy_id)

    if vacancy.status != 'committee_stage':
        messages.error(request, "Shortlisting is not active.")
        return redirect('panelist_dashboard')

    assignment = PanelAssignment.objects.filter(
        vacancy=vacancy,
        panelist=request.user,
        committee_type='shortlisting',
        status='accepted'
    ).first()

    if not assignment:
        messages.error(request, "You are not part of this shortlisting committee.")
        return redirect('panelist_dashboard')

    # Prevent duplicate submission
    existing_votes = ShortlistVote.objects.filter(
        vacancy=vacancy,
        committee_member=request.user
    )

    if existing_votes.exists():
        messages.warning(request, "You have already submitted your shortlist.")
        return redirect('panelist_dashboard')

    applications = Application.objects.filter(
        vacancy=vacancy,
        status='submitted'
    )

    if request.method == 'POST':
        selected_ids = request.POST.getlist('selected_applications')

        if not selected_ids:
            messages.error(request, "Select at least one candidate.")
            return redirect(request.path)

        for app in applications:
            if str(app.id) in selected_ids:
                ShortlistVote.objects.create(
                    vacancy=vacancy,
                    committee_member=request.user,
                    application=app
                )

        # Check if all members submitted
        if is_shortlisting_complete(vacancy):
            aggregate_shortlist(vacancy)

        messages.success(request, "Your shortlist has been submitted.")
        return redirect('panelist_dashboard')

    return render(request, 'recruitment/panelist/shortlist.html', {
        'vacancy': vacancy,
        'applications': applications
    })

@login_required
def vacancy_panelists(request, vacancy_id):
    vacancy = get_object_or_404(Vacancy, id=vacancy_id)

    panelists = User.objects.filter(
        panelassignment__vacancy=vacancy
    )

    return render(request, "recruitment/hr/vacancy_panelists.html", {
        "vacancy": vacancy,
        "panelists": panelists
    })


from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied


@login_required
@role_required(['hod_hr'])
def open_vacancy(request, vacancy_id):
    vacancy = get_object_or_404(Vacancy, id=vacancy_id)
    if vacancy.status != 'closed':
        messages.warning(request, "Only closed vacancies can be opened.")
        return redirect('hr_dashboard')

    vacancy.status = 'open'
    vacancy.save()
    messages.success(request, "Vacancy is now open.")
    return redirect('hr_dashboard')


@login_required
@role_required(['hod_hr'])
def close_vacancy(request, vacancy_id):
    vacancy = get_object_or_404(Vacancy, id=vacancy_id)
    if vacancy.status != 'open':
        messages.warning(request, "Only open vacancies can be closed.")
        return redirect('hr_dashboard')

    vacancy.status = 'closed'
    vacancy.save()
    messages.success(request, "Vacancy is now closed.")
    return redirect('hr_dashboard')


@login_required
@role_required(['panelist'])
def panelist_interview_list(request, vacancy_id):
    vacancy = get_object_or_404(
        Vacancy,
        id=vacancy_id,
        status='interviews'
    )

    # Ensure panelist is assigned
    if not PanelAssignment.objects.filter(
            vacancy=vacancy,
            panelist=request.user
    ).exists():
        raise PermissionDenied

    applications = Application.objects.filter(
        vacancy=vacancy,
        status='shortlisted'
    )

    return render(request, 'recruitment/panelist/interview_list.html', {
        'vacancy': vacancy,
        'applications': applications
    })


@login_required
@role_required(['panelist'])
def panelist_score_candidate(request, application_id):
    application = get_object_or_404(Application, id=application_id)
    vacancy = application.vacancy

    if vacancy.status != 'interviews':
        messages.error(request, "Interview stage is not active.")
        return redirect('panelist_dashboard')

    # Ensure panelist is assigned
    if not PanelAssignment.objects.filter(
            vacancy=vacancy,
            panelist=request.user
    ).exists():
        raise PermissionDenied

    score_obj = InterviewScore.objects.filter(
        application=application,
        panelist=request.user
    ).first()

    if application.interview_locked:
        messages.error(request, "Scoring for this candidate is locked.")
        return redirect('panelist_interview_list', vacancy_id=vacancy.id)

    if request.method == 'POST':
        score_value = request.POST.get('score')
        remarks = request.POST.get('remarks')

        if not score_value:
            messages.error(request, "Score is required.")
            return redirect('panelist_score_candidate', application_id=application.id)

        InterviewScore.objects.update_or_create(
            application=application,
            panelist=request.user,
            defaults={
                'score': score_value,
                'remarks': remarks
            }
        )

        check_and_lock_application(application)

        messages.success(request, "Score saved successfully.")
        return redirect('panelist_interview_list', vacancy_id=vacancy.id)

    return render(request, 'recruitment/panelist/score_candidate.html', {
        'application': application,
        'existing_score': score_obj
    })


from django.db.models import Count


@login_required
@role_required(['hod_hr'])
def hr_ranking_view(request, vacancy_id):
    vacancy = get_object_or_404(Vacancy, id=vacancy_id)

    if vacancy.status != 'interviews':
        messages.error(request, "Ranking available only during interview stage.")
        return redirect('hr_dashboard')

    applications = Application.objects.filter(
        vacancy=vacancy
        # ,interview_locked=True
    ).annotate(
        avg_score=Avg('scores__score'),
        score_count=Count('scores')
    ).filter(
        score_count__gt=0  # Only show applications with at least one score
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


from django.db.models import Avg


@login_required
@role_required(['ceo'])
def ceo_dashboard(request):
    vacancies = Vacancy.objects.filter(status='selected_top_three')

    context = {
        'pending_approval_count': vacancies.count(),
        'vacancies': vacancies
    }
    return render(request, 'recruitment/ceo/dashboard.html', context)


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


@login_required
@role_required(['ceo'])
def ceo_review_view(request, vacancy_id):
    vacancy = get_object_or_404(Vacancy, id=vacancy_id)

    if vacancy.status != 'ceo_review':
        messages.error(request, "This vacancy is not in CEO review stage.")
        return redirect('ceo_dashboard')

    applications = Application.objects.filter(
        vacancy=vacancy
        # interview_locked=True
    ).annotate(
        avg_score=Avg('scores__score')
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
    is_override = application.status != 'ceo_review'

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
def application_detail(request, application_id):
    application = get_object_or_404(
        Application.objects.select_related(
            "applicant",
            "applicant__profile",
            "applicant__additional_detail"
        ).prefetch_related(
            "applicant__academic_qualifications",
            "applicant__work_history",
            "applicant__professional_qualifications",
            "applicant__documents"
        ),
        id=application_id
    )

    return render(request, "recruitment/hr/application_detail.html", {
        "application": application
    })


from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Vacancy, PanelAssignment
from core.decorators import role_required


# ----------------------
# Stage: Longlisting
# ----------------------
@login_required
@role_required(['hod_hr'])
def vacancy_longlisting(request):
    vacancies = Vacancy.objects.filter(status='longlisting')
    return render(request, 'recruitment/hr/longlisting.html', {
        'vacancies': vacancies
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
@login_required
@role_required(['hod_hr'])
def vacancy_shortlisting(request):
    vacancies = Vacancy.objects.filter(status='shortlisting')
    return render(request, 'recruitment/hr/shortlisting.html', {
        'vacancies': vacancies
    })


# ----------------------
# Stage: Interviews
# ----------------------
@login_required
@role_required(['hod_hr'])
def vacancy_interviews(request):
    vacancies = Vacancy.objects.filter(status='interviews')
    return render(request, 'recruitment/hr/vacancy_interviews.html', {
        'vacancies': vacancies
    })


# ----------------------
# Stage: Appointments (with panelists)
# ----------------------
@login_required
@role_required(['hod_hr'])
def vacancy_appointments(request):
    vacancies = Vacancy.objects.filter(status='appointed').prefetch_related('panelassignment_set__panelist')
    return render(request, 'recruitment/hr/vacancy_appointments.html', {
        'vacancies': vacancies
    })


# ----------------------
# Optional: Detailed view to appoint panelists
# ----------------------
@login_required
@role_required(['hod_hr'])
def appointed_panelists(request, vacancy_id):
    vacancy = get_object_or_404(Vacancy, id=vacancy_id)

    if vacancy.status != 'shortlisting':
        messages.error(request, "Complete shortlisting first.")
        return redirect('vacancy_shortlisting')

    panelist_role = get_object_or_404(Role, name='panelist')
    panelists = User.objects.filter(user_type=2, role=panelist_role)

    if request.method == 'POST':
        selected_panelists = request.POST.getlist('panelists')
        PanelAssignment.objects.filter(vacancy=vacancy).delete()
        for user_id in selected_panelists:
            PanelAssignment.objects.create(vacancy=vacancy, panelist_id=user_id)
        vacancy.status = 'interviews'
        vacancy.save()
        messages.success(request, "Panel appointed. Interview stage started.")
        return redirect('vacancy_interviews')

    assigned_panelists = User.objects.filter(panelassignment__vacancy=vacancy)

    return render(request, 'recruitment/hr/appoint_panel.html', {
        'vacancy': vacancy,
        'panelists': panelists,
        'assigned_panelists': assigned_panelists
    })


@login_required
@role_required(['hod_hr'])
def vacancy_list(request):
    vacancies = Vacancy.objects.filter(status='open')
    context = {
        'vacancies': vacancies,
        'open_vacancies_count': Vacancy.objects.filter(status='open').count(),
    }
    return render(request, 'recruitment/hr/vacancy_list.html', context)


@login_required
@role_required(['hod_hr'])
def appoint_shortlisting_committee(request, vacancy_id):

    vacancy = get_object_or_404(Vacancy, id=vacancy_id)

    if vacancy.status != 'longlisting':
        messages.error(request, "Committee can only be appointed during longlisting stage.")
        return redirect('hr_dashboard')

    panel_role = Role.objects.get(name='panelist')
    panelists = User.objects.filter(role=panel_role)

    if request.method == 'POST':
        selected_panelists = request.POST.getlist('panelists')

        if not selected_panelists:
            messages.error(request, "Select at least one committee member.")
            return redirect(request.path)

        # Remove old committee if exists
        PanelAssignment.objects.filter(
            vacancy=vacancy,
            committee_type='shortlisting'
        ).delete()

        for user_id in selected_panelists:
            PanelAssignment.objects.create(
                vacancy=vacancy,
                panelist_id=user_id,
                committee_type='shortlisting'
            )

        vacancy.move_to('committee_stage')

        messages.success(request, "Shortlisting committee appointed successfully.")
        return redirect('hr_dashboard')

    return render(request, 'recruitment/hr/appoint_shortlisting.html', {
        'vacancy': vacancy,
        'panelists': panelists
    })
    
# @login_required
# @role_required(['panelist'])
# def submit_shortlist(request, vacancy_id):

#     vacancy = get_object_or_404(Vacancy, id=vacancy_id)

#     assignment = PanelAssignment.objects.filter(
#         vacancy=vacancy,
#         panelist=request.user,
#         committee_type='shortlisting',
#         status='accepted'
#     ).first()

#     if not assignment:
#         messages.error(request, "You are not part of this shortlisting committee.")
#         return redirect('panelist_dashboard')

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

#         messages.success(request, "Shortlist submitted successfully.")
#         return redirect('panelist_dashboard')

#     return render(request, 'recruitment/panelist/shortlist.html', {
#         'vacancy': vacancy,
#         'applications': applications
#     })
    
