import json

from .models import Gender, EthnicGroup, County, Constituency, SubCounty, Ward, JobSeekerProfile, AcademicQualification, \
    EducationLevel, DocumentType, Document
from django.shortcuts import render, redirect, get_object_or_404
from accounts.models import JobseekerAccount, AdditionalDetail, ProfessionalQualification, WorkHistory
from django.http import JsonResponse


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
            salutation        = request.POST.get('salutation', '')
            surname           = request.POST.get('surname', '').strip()
            first_name        = request.POST.get('first_name', '').strip()
            second_name       = request.POST.get('second_name', '').strip()
            email             = request.POST.get('email', '').strip()
            id_no             = request.POST.get('id_no', '').strip()
            date_of_birth     = request.POST.get('date_of_birth') or None
            gender_id         = request.POST.get('gender') or None
            ethnic_group_id   = request.POST.get('ethnic_group') or None
            home_county_id    = request.POST.get('home_county') or None
            constituency_id   = request.POST.get('constituency') or None
            sub_county_id     = request.POST.get('sub_county') or None
            ward_id           = request.POST.get('ward') or None
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

            profile.surname           = surname
            profile.salutation        = salutation
            profile.first_name        = first_name
            profile.second_name       = second_name
            profile.email             = email
            profile.id_no             = id_no
            profile.date_of_birth     = date_of_birth
            profile.gender_id         = gender_id
            profile.ethnic_group_id   = ethnic_group_id
            profile.home_county_id    = home_county_id
            profile.constituency_id   = constituency_id
            profile.sub_county_id     = sub_county_id
            profile.ward_id           = ward_id
            profile.disability_status = disability_status
            profile.save()

            return JsonResponse({'status': 'success', 'message': 'Profile saved successfully.'})

        except Exception as e:
            return JsonResponse({'status': 'error', 'message': f'Something went wrong: {str(e)}'})

    context = {
        'profile':        profile,
        'user':           user,
        'page':           'Profile',
        'counties':       County.objects.all(),
        'constituencies': Constituency.objects.all(),
        'sub_counties':   SubCounty.objects.all(),
        'wards':          Ward.objects.all(),
        'genders':        Gender.objects.all(),
        'ethnic_groups':  EthnicGroup.objects.all(),
        'completion':     completion,
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

    profile    = JobSeekerProfile.objects.filter(user=user).first()
    completion = calculate_profile_completion(user)

    if request.method == 'POST':
        action = request.POST.get('action', 'save')

        # ── DELETE ───────────────────────────────────────────
        if action == 'delete':
            try:
                qual_id = request.POST.get('qual_id')
                qual    = AcademicQualification.objects.filter(id=qual_id, user=user).first()

                if not qual:
                    return JsonResponse({'status': 'error', 'message': 'Qualification not found.'})

                qual.delete()
                return JsonResponse({
                    'status':  'success',
                    'message': 'Qualification deleted successfully.',
                })

            except Exception as e:
                return JsonResponse({'status': 'error', 'message': f'Error: {str(e)}'})

        # ── EDIT ─────────────────────────────────────────────
        if action == 'edit':
            try:
                qual_id = request.POST.get('qual_id')
                qual    = AcademicQualification.objects.filter(id=qual_id, user=user).first()

                if not qual:
                    return JsonResponse({'status': 'error', 'message': 'Qualification not found.'})

                level_id        = request.POST.get('education_level')
                education_level = EducationLevel.objects.filter(id=level_id).first()

                if not education_level:
                    return JsonResponse({'status': 'error', 'message': 'Invalid education level.'})

                institution = request.POST.get('institution', '').strip()
                year        = request.POST.get('year_completed', '').strip()

                if not institution:
                    return JsonResponse({'status': 'error', 'message': 'Institution is required.'})
                if not year:
                    return JsonResponse({'status': 'error', 'message': 'Year completed is required.'})

                qual.education_level = education_level
                qual.institution     = institution
                qual.field_of_study  = request.POST.get('field_of_study', '').strip()
                qual.year_completed  = year
                qual.grade           = request.POST.get('grade', '').strip()
                qual.cert_number     = request.POST.get('cert_number', '').strip()
                qual.country         = request.POST.get('country', 'Kenya').strip() or 'Kenya'
                qual.save()

                # New documents uploaded during edit
                files     = request.FILES.getlist('edit_files')
                doc_types = request.POST.getlist('edit_doc_types')
                doc_count = Document.objects.filter(user=user).count()

                for i, file in enumerate(files):
                    doc_type_id = doc_types[i] if i < len(doc_types) else None
                    doc_type    = DocumentType.objects.filter(id=doc_type_id).first()
                    if file and doc_type:
                        Document.objects.create(
                            user          = user,
                            profile       = profile,
                            document_type = doc_type,
                            file          = file,
                        )
                        doc_count += 1

                # Re-count docs linked to this qualification (approximate by user for now)
                total_docs = Document.objects.filter(user=user).count()

                return JsonResponse({
                    'status':  'success',
                    'message': 'Qualification updated successfully.',
                    'qual': {
                        'id':             qual.id,
                        'level_id':       education_level.id,
                        'level_name':     education_level.name,
                        'institution':    qual.institution,
                        'field_of_study': qual.field_of_study or '',
                        'year_completed': qual.year_completed,
                        'grade':          qual.grade or '',
                        'cert_number':    qual.cert_number or '',
                        'country':        qual.country,
                        'doc_count':      total_docs,
                    }
                })

            except Exception as e:
                return JsonResponse({'status': 'error', 'message': f'Error: {str(e)}'})

        # ── SAVE NEW ─────────────────────────────────────────
        try:
            qualifications = json.loads(request.POST.get('qualifications', '[]'))
            level_count    = int(request.POST.get('level_count', 0))

            if not qualifications:
                return JsonResponse({
                    'status':  'error',
                    'message': 'Please add at least one qualification.'
                })

            saved = []

            for idx, q in enumerate(qualifications):
                education_level = EducationLevel.objects.filter(
                    id=q.get('education_level')).first()

                if not education_level:
                    continue

                institution = q.get('institution', '').strip()
                year        = q.get('year_completed', '')

                if not institution or not year:
                    continue

                qual = AcademicQualification.objects.create(
                    user            = user,
                    education_level = education_level,
                    institution     = institution,
                    field_of_study  = q.get('field_of_study', '').strip(),
                    country         = q.get('country', 'Kenya').strip() or 'Kenya',
                    year_completed  = year,
                    grade           = q.get('grade', '').strip(),
                    cert_number     = q.get('cert_number', '').strip(),
                )

                # Documents per level
                files     = request.FILES.getlist(f'level_files_{idx}')
                doc_types = request.POST.getlist(f'level_doc_types_{idx}')
                doc_count = 0

                for i, file in enumerate(files):
                    doc_type_id = doc_types[i] if i < len(doc_types) else None
                    doc_type    = DocumentType.objects.filter(id=doc_type_id).first()
                    if file and doc_type:
                        Document.objects.create(
                            user          = user,
                            profile       = profile,
                            document_type = doc_type,
                            file          = file,
                        )
                        doc_count += 1

                saved.append({
                    'id':             qual.id,
                    'level_id':       education_level.id,
                    'level_name':     education_level.name,
                    'institution':    qual.institution,
                    'field_of_study': qual.field_of_study or '',
                    'year_completed': qual.year_completed,
                    'grade':          qual.grade or '',
                    'cert_number':    qual.cert_number or '',
                    'country':        qual.country,
                    'doc_count':      doc_count,
                })

            if not saved:
                return JsonResponse({
                    'status':  'error',
                    'message': 'No valid qualifications were saved. Check all required fields.'
                })

            return JsonResponse({
                'status':  'success',
                'message': f'{len(saved)} qualification(s) saved successfully.',
                'saved':   saved,
            })

        except Exception as e:
            return JsonResponse({'status': 'error', 'message': f'Something went wrong: {str(e)}'})

    # ── GET ───────────────────────────────────────────────────
    existing_qualifications = AcademicQualification.objects.filter(user=user).select_related(
        'education_level').order_by('education_level__rank')
    existing_documents      = Document.objects.filter(user=user)

    context = {
        'profile':                 profile,
        'user':                    user,
        'page':                    'Academic Qualifications',
        'education_levels':        EducationLevel.objects.all().order_by('rank'),
        'document_types':          DocumentType.objects.all(),
        'existing_qualifications': existing_qualifications,
        'existing_documents':      existing_documents,
        'completion':              completion,
        'has_academic':            existing_qualifications.exists(),
        'has_professional':        user.professional_qualifications.exists()
                                   if hasattr(user, 'professional_qualifications') else False,
        'has_work_history':        user.work_history.exists()
                                   if hasattr(user, 'work_history') else False,
        'has_additional':          hasattr(user, 'additional_detail'),
    }
    return render(request, 'jobseekers/academic.html', context)


# ── Profile Delete ───────────────────────────────────────────
def delete_profile(request):
    user_id = request.session.get('user_id')
    if not user_id:
        return redirect('index')

    user    = JobseekerAccount.objects.filter(id=user_id).first()
    profile = JobSeekerProfile.objects.filter(user=user).first()
    if profile:
        profile.delete()

    return redirect('profile')


# ── Progress Calculation ─────────────────────────────────────
def calculate_profile_completion(user):
    score = 0

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
        filled  = sum(1 for f in fields if f)
        score  += int((filled / len(fields)) * 40)

    if hasattr(user, 'academic_qualifications') and user.academic_qualifications.exists():
        score += 15

    if hasattr(user, 'professional_qualifications') and user.professional_qualifications.exists():
        score += 15

    if hasattr(user, 'work_history') and user.work_history.exists():
        score += 15

    if hasattr(user, 'additional_detail'):
        detail = user.additional_detail
        if detail.cover_letter:
            score += 7
        if detail.cv:
            score += 8

    return min(int(score), 100)


# ── Professional Qualifications ──────────────────────────────
def professional_qualifications(request):
    user = get_logged_in_user(request)
    if not user:
        return redirect('index')

    qualifications = ProfessionalQualification.objects.filter(user=user)

    if request.method == 'POST':
        ProfessionalQualification.objects.create(
            user            = user,
            institution     = request.POST.get('institution'),
            course          = request.POST.get('course'),
            completion_date = request.POST.get('completion_date'),
            grade           = request.POST.get('grade'),
            certificate     = request.FILES.get('certificate'),
        )
        return redirect('professional_qualifications')

    completion = calculate_profile_completion(user)
    return render(request, 'jobseekers/professional.html', {
        'qualifications': qualifications,
        'completion':     completion,
    })


def edit_professional(request, pk):
    user = get_logged_in_user(request)
    if not user:
        return redirect('index')

    qualification = get_object_or_404(ProfessionalQualification, pk=pk, user=user)

    if request.method == 'POST':
        qualification.institution     = request.POST.get('institution')
        qualification.course          = request.POST.get('course')
        qualification.completion_date = request.POST.get('completion_date')
        qualification.grade           = request.POST.get('grade')
        if request.FILES.get('certificate'):
            qualification.certificate = request.FILES.get('certificate')
        qualification.save()
        return redirect('professional_qualifications')

    return render(request, 'jobseekers/edit_professional.html', {'qualification': qualification})


def delete_professional(request, pk):
    user = get_logged_in_user(request)
    if not user:
        return redirect('index')

    qualification = get_object_or_404(ProfessionalQualification, pk=pk, user=user)
    qualification.delete()
    return redirect('professional_qualifications')


# ── Work History ─────────────────────────────────────────────
def work_history(request):
    user = get_logged_in_user(request)
    if not user:
        return redirect('index')

    jobs = WorkHistory.objects.filter(user=user).order_by('-start_date')

    if request.method == 'POST':
        is_current = request.POST.get('is_current') == 'on'
        if is_current:
            WorkHistory.objects.filter(user=user, is_current=True).update(is_current=False)

        WorkHistory.objects.create(
            user        = user,
            company     = request.POST.get('company'),
            job_title   = request.POST.get('job_title'),
            duties      = request.POST.get('duties'),
            start_date  = request.POST.get('start_date'),
            end_date    = None if is_current else request.POST.get('end_date'),
            exit_reason = None if is_current else request.POST.get('exit_reason'),
            is_current  = is_current,
        )
        return redirect('work_history')

    completion = calculate_profile_completion(user)
    return render(request, 'jobseekers/work_history.html', {
        'jobs':       jobs,
        'completion': completion,
    })


def edit_work_history(request, pk):
    user = get_logged_in_user(request)
    if not user:
        return redirect('index')

    job = get_object_or_404(WorkHistory, pk=pk, user=user)

    if request.method == 'POST':
        job.company    = request.POST.get('company')
        job.job_title  = request.POST.get('job_title')
        job.duties     = request.POST.get('duties')
        job.start_date = request.POST.get('start_date')
        is_current     = request.POST.get('is_current') == 'on'

        if is_current:
            WorkHistory.objects.filter(user=user, is_current=True).exclude(pk=job.pk).update(is_current=False)
            job.end_date    = None
            job.exit_reason = None
        else:
            job.end_date    = request.POST.get('end_date')
            job.exit_reason = request.POST.get('exit_reason')

        job.is_current = is_current
        job.save()
        return redirect('work_history')

    return render(request, 'jobseekers/edit_work_history.html', {'job': job})


def delete_work_history(request, pk):
    user = get_logged_in_user(request)
    if not user:
        return redirect('index')

    job = get_object_or_404(WorkHistory, pk=pk, user=user)
    job.delete()
    return redirect('work_history')


# ── Additional Details ───────────────────────────────────────
def additional_details(request):
    user = get_logged_in_user(request)
    if not user:
        return redirect('index')

    detail = AdditionalDetail.objects.filter(user=user).first()

    if request.method == 'POST':
        cover_letter = request.POST.get('cover_letter')
        cv_file      = request.FILES.get('cv')

        if detail:
            detail.cover_letter = cover_letter
            if cv_file:
                if detail.cv:
                    detail.cv.delete(save=False)
                detail.cv = cv_file
            detail.save()
        else:
            AdditionalDetail.objects.create(
                user         = user,
                cover_letter = cover_letter,
                cv           = cv_file,
            )
        return redirect('additional_details')

    completion = calculate_profile_completion(user)
    return render(request, 'jobseekers/additional.html', {
        'detail':     detail,
        'completion': completion,
    })


def delete_cv(request):
    user = get_logged_in_user(request)
    if not user:
        return redirect('index')

    detail = AdditionalDetail.objects.filter(user=user).first()
    if detail and detail.cv:
        detail.cv.delete(save=False)
        detail.cv = None
        detail.save()

    return redirect('additional_details')