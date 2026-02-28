import json
import os
from datetime import datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Avg
from django.http import FileResponse, Http404
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone

from accounts.models import JobseekerAccount
from core.decorators import role_required
from .models import Application, Appointment, CEODecision, Gender, EthnicGroup, InterviewScore, \
    ProfessionalQualification, WorkHistory, AdditionalDetail
from .models import County, Constituency, SubCounty, Ward, JobSeekerProfile, AcademicQualification, \
    EducationLevel, DocumentType, Document
from .models import PanelAssignment
from .models import Vacancy


# ── Helper ───────────────────────────────────────────────────
def get_logged_in_user(request):
    user_id = request.session.get('user_id')
    if not user_id:
        return None
    return JobseekerAccount.objects.filter(id=user_id).first()


def dashboard(request):
    return render(request, 'jobseekers/dashboard.html', {'page': 'Dashboard'})


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
            salutation = request.POST.get('salutation', '')
            surname = request.POST.get('surname', '').strip()
            first_name = request.POST.get('first_name', '').strip()
            second_name = request.POST.get('second_name', '').strip()
            email = request.POST.get('email', '').strip()
            id_no = request.POST.get('id_no', '').strip()
            date_of_birth = request.POST.get('date_of_birth') or None
            gender_id = request.POST.get('gender') or None
            ethnic_group_id = request.POST.get('ethnic_group') or None
            home_county_id = request.POST.get('home_county') or None
            constituency_id = request.POST.get('constituency') or None
            sub_county_id = request.POST.get('sub_county') or None
            ward_id = request.POST.get('ward') or None
            disability_status = request.POST.get('disability_status', '').strip()

            if not first_name:
                return JsonResponse({'status': 'error', 'message': 'First name is required.'})
            if not surname:
                return JsonResponse({'status': 'error', 'message': 'Surname is required.'})
            if not email:
                return JsonResponse({'status': 'error', 'message': 'Email is required.'})
            if not id_no:
                return JsonResponse({'status': 'error', 'message': 'ID number is required.'})
            if not date_of_birth:
                return JsonResponse({'status': 'error', 'message': 'Date of birth is required.'})

            profile.surname = surname
            profile.salutation = salutation
            profile.first_name = first_name
            profile.second_name = second_name
            profile.email = email
            profile.id_no = id_no
            profile.date_of_birth = date_of_birth
            profile.gender_id = gender_id
            profile.ethnic_group_id = ethnic_group_id
            profile.home_county_id = home_county_id
            profile.constituency_id = constituency_id
            profile.sub_county_id = sub_county_id
            profile.ward_id = ward_id
            profile.disability_status = disability_status
            profile.save()

            return JsonResponse({'status': 'success', 'message': 'Profile saved successfully.'})

        except Exception as e:
            return JsonResponse({'status': 'error', 'message': f'Something went wrong: {str(e)}'})

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
    }
    return render(request, 'jobseekers/academic.html', context)


# ── Profile Delete ───────────────────────────────────────────
def delete_profile(request):
    user_id = request.session.get('user_id')
    if not user_id:
        return redirect('index')

    user = JobseekerAccount.objects.filter(id=user_id).first()
    profile = JobSeekerProfile.objects.filter(user=user).first()
    if profile:
        profile.delete()

    return redirect('profile')


# ── Progress Calculation ─────────────────────────────────────
def calculate_profile_completion(user):
    score = 0

    # ── Section 1: Basic Details (40 points) ──────────────────
    if hasattr(user, 'profile'):
        profile = user.profile
        fields  = [
            profile.salutation,
            profile.surname,
            profile.first_name,
            profile.date_of_birth,
            profile.gender_id,
            profile.ethnic_group_id,
            profile.home_county_id,
            profile.constituency_id,
            profile.disability_status,
        ]
        filled = sum(1 for f in fields if f)
        score += int((filled / len(fields)) * 40)

    # ── Section 2: Academic Qualifications (15 points) ────────
    if AcademicQualification.objects.filter(user=user).exists():
        score += 15

    # ── Section 3: Professional Qualifications (15 points) ────
    if ProfessionalQualification.objects.filter(user=user).exists():
        score += 15

    # ── Section 4: Work History (15 points) ───────────────────
    if WorkHistory.objects.filter(user=user).exists():
        score += 15

    # ── Section 5: Additional Details (15 points) ─────────────
    detail = AdditionalDetail.objects.filter(user=user).first()
    if detail:
        if detail.cv:              score += 5   # CV uploaded
        if detail.cover_letter:    score += 4   # cover letter written
        if detail.linkedin_url:    score += 2   # LinkedIn added
        if detail.availability:    score += 2   # availability set
        if detail.languages:       score += 2   # languages added
                                                # total = 15

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


@login_required
@role_required(['panelist'])
def panelist_dashboard(request):
    assigned = Vacancy.objects.filter(panel_assignments__panelist=request.user)

    context = {
        'assigned_vacancies_count': assigned.count()
    }
    return render(request, 'panelist/dashboard.html', context)


@login_required
@role_required(['officer'])
def officer_dashboard(request):
    context = {
        'internal_vacancies_count': Vacancy.objects.filter(status='open').count(),
        'my_applications_count': request.user.application_set.count()
    }
    return render(request, 'officer/dashboard.html', context)


@login_required
@role_required(['ceo'])
def ceo_dashboard(request):
    context = {
        'pending_approval_count': Vacancy.objects.filter(status='pending_ceo_approval').count()
    }
    return render(request, 'ceo/dashboard.html', context)


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
@role_required(['ceo'])
def ceo_approve(request, vacancy_id):
    vacancy = get_object_or_404(Vacancy, id=vacancy_id)

    if request.method == 'POST':
        application_id = request.POST.get('application_id')
        reason = request.POST.get('reason', '')

        selected = Application.objects.get(id=application_id)

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

        return redirect('ceo_dashboard')


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

    if vacancy.status != 'draft':
        messages.error(request, "Only draft vacancies can be edited.")
        return redirect('hr_dashboard')

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

    if vacancy.status != 'draft':
        messages.error(request, "Only draft vacancies can be deleted.")
        return redirect('hr_dashboard')

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


# @login_required
# @role_required(['applicant', 'officer'])
def apply_for_vacancy(request, vacancy_id):
    vacancy = get_object_or_404(Vacancy, id=vacancy_id)

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
            # Save application
            application = Application(
                vacancy=vacancy,
                applicant=request.user,
                cv=cv_file,
                cover_letter=cover_letter
            )
            application.save()
            messages.success(request, "Application submitted successfully.")
            return redirect('dashboard')

    return render(request, 'recruitment/applicant/apply.html', {'vacancy': vacancy})


@login_required
# @role_required(['hod_hr'])
def hr_view_applications(request, vacancy_id):
    vacancy = get_object_or_404(Vacancy, id=vacancy_id)

    if vacancy.status not in ['closed', 'longlisting', 'shortlisting', 'interviews']:
        messages.error(request, "Applications not available for review yet.")
        return redirect('hr_dashboard')

    applications = Application.objects.filter(vacancy=vacancy)

    return render(request, 'recruitment/hr/view_applications.html', {
        'vacancy': vacancy,
        'applications': applications
    })


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


@login_required
@role_required(['hod_hr'])
def appoint_panelists(request, vacancy_id):
    vacancy = get_object_or_404(Vacancy, id=vacancy_id)

    if vacancy.status != 'shortlisting':
        messages.error(request, "Complete shortlisting first.")
        return redirect('hr_dashboard')

    panelists = request.user.objects.filter(role='panelist')

    if request.method == 'POST':
        selected_panelists = request.POST.getlist('panelists')

        PanelAssignment.objects.filter(vacancy=vacancy).delete()

        for pid in selected_panelists:
            PanelAssignment.objects.create(
                vacancy=vacancy,
                panelist_id=pid
            )

        vacancy.status = 'interviews'
        vacancy.save()

        messages.success(request, "Panel appointed. Interview stage started.")
        return redirect('hr_dashboard')

    return render(request, 'recruitment/hr/appoint_panel.html', {
        'vacancy': vacancy,
        'panelists': panelists
    })
