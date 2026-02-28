from .models import Gender, EthnicGroup, County, Constituency, SubCounty, Ward, JobSeekerProfile
from .models import Application, Appointment, CEODecision, Gender, EthnicGroup, InterviewScore
from django.shortcuts import render, redirect, get_object_or_404
from accounts.models import JobseekerAccount, AdditionalDetail, ProfessionalQualification, WorkHistory, AcademicQualification
from django.http import JsonResponse
from accounts.models import JobseekerAccount, AdditionalDetail, JobseekerProfile, ProfessionalQualification, WorkHistory, AcademicQualification

from django.contrib.auth.decorators import login_required
from .models import Vacancy
from core.decorators import permission_required, role_required
from django.db.models import Avg
from django.contrib import messages
from django.utils import timezone
from datetime import datetime
from django.http import FileResponse, Http404

def dashboard(request):
    return render(request, 'recruitment/dashboard.html')

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

            # Validation
            if not first_name:
                return JsonResponse({'status': 'error', 'message': 'First name is required.'})
            if not surname:
                return JsonResponse({'status': 'error', 'message': 'Surname name is required.'})
            if not email:
                return JsonResponse({'status': 'error', 'message': 'Email is required.'})
            if not id_no:
                return JsonResponse({'status': 'error', 'message': 'ID number is required.'})
            if not date_of_birth:
                return JsonResponse({'status': 'error', 'message': 'Date of birth is required.'})

            # Save
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

def delete_profile(request):
    user_id = request.session.get("user_id")

    if not user_id:
        return redirect("/login/")

    try:
        user = JobseekerAccount.objects.get(id=user_id)
        profile = JobSeekerProfile.objects.filter(user=user).first()

        if profile:
            profile.delete()
    except JobseekerAccount.DoesNotExist:
        pass

    return redirect("profile")



def calculate_profile_completion(user):
    score = 0
    total = 100

    # ── Section 1: Basic Details (40 points) ──────────────────
    # Each field worth points, adds up to 40
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
        ]
        filled        = sum(1 for f in fields if f)
        field_score   = int((filled / len(fields)) * 40)
        score        += field_score

    # ── Section 2: Academic Qualifications (15 points) ────────
    if hasattr(user, 'academic_qualifications') and user.academic_qualifications.exists():
        score += 15

    # ── Section 3: Professional Qualifications (15 points) ────
    if hasattr(user, 'professional_qualifications') and user.professional_qualifications.exists():
        score += 15

    # ── Section 4: Work History (15 points) ───────────────────
    if hasattr(user, 'work_history') and user.work_history.exists():
        score += 15

    # ── Section 5: Additional Details (15 points) ─────────────
    if hasattr(user, 'additional_detail'):
        detail = user.additional_detail
        if detail.cover_letter:
            score += 7
        if detail.cv:
            score += 8

    return min(int(score), 100)

def academic_qualifications(request):


    if request.method == "POST":
        pass

    return render(request, "jobseekers/academic.html", )
    

def edit_academic(request, pk):
    jobseeker_id = request.session.get("jobseeker_id")

    if not jobseeker_id:
        return redirect("/login/")

    user = JobseekerAccount.objects.get(id=jobseeker_id)

    qualification = get_object_or_404(
        AcademicQualification,
        pk=pk,
        user=user
    )

    if request.method == "POST":
        qualification.level = request.POST.get("level")
        qualification.institution = request.POST.get("institution")

        if request.FILES.get("certificate"):
            qualification.certificate = request.FILES.get("certificate")

        if request.FILES.get("transcript"):
            qualification.transcript = request.FILES.get("transcript")

        qualification.save()

        return redirect("academic_qualifications")

    return render(
        request,
        "jobseekers/edit_academic.html",
        {"qualification": qualification}
    )
    
def delete_academic(request, pk):
    jobseeker_id = request.session.get("jobseeker_id")

    if not jobseeker_id:
        return redirect("/login/")

    user = JobseekerAccount.objects.get(id=jobseeker_id)

    qualification = get_object_or_404(
        AcademicQualification,
        pk=pk,
        user=user
    )

    qualification.delete()

    return redirect("academic_qualifications")

def professional_qualifications(request):
    
    jobseeker_id = request.session.get("jobseeker_id")
    user = JobseekerAccount.objects.get(id=jobseeker_id)
    if not user:
        return redirect("/login/")

    qualifications = ProfessionalQualification.objects.filter(user=user)

    if request.method == "POST":
        ProfessionalQualification.objects.create(
            user=user,
            institution=request.POST.get("institution"),
            course=request.POST.get("course"),
            completion_date=request.POST.get("completion_date"),
            grade=request.POST.get("grade"),
            certificate=request.FILES.get("certificate"),
        )
        return redirect("professional_qualifications")

    completion = calculate_profile_completion(user)

    return render(request, "jobseekers/professional.html", {
        "qualifications": qualifications,
        "completion": completion
    })

def edit_professional(request, pk):
    jobseeker_id = request.session.get("jobseeker_id")

    if not jobseeker_id:
        return redirect("/login/")

    user = JobseekerAccount.objects.get(id=jobseeker_id)

    qualification = get_object_or_404(
        ProfessionalQualification,
        pk=pk,
        user=user
    )

    if request.method == "POST":
        qualification.institution = request.POST.get("institution")
        qualification.course = request.POST.get("course")
        qualification.completion_date = request.POST.get("completion_date")
        qualification.grade = request.POST.get("grade")

        if request.FILES.get("certificate"):
            qualification.certificate = request.FILES.get("certificate")

        qualification.save()

        return redirect("professional_qualifications")

    return render(
        request,
        "jobseekers/edit_professional.html",
        {"qualification": qualification}
    )

def delete_professional(request, pk):
    jobseeker_id = request.session.get("jobseeker_id")

    if not jobseeker_id:
        return redirect("/login/")

    user = JobseekerAccount.objects.get(id=jobseeker_id)

    qualification = get_object_or_404(
        ProfessionalQualification,
        pk=pk,
        user=user
    )

    qualification.delete()

    return redirect("professional_qualifications")


def work_history(request):
    jobseeker_id = request.session.get("jobseeker_id")
    user = JobseekerAccount.objects.get(id=jobseeker_id)
    if not user:
        return redirect("/login/")

    jobs = WorkHistory.objects.filter(user=user).order_by("-start_date")

    if request.method == "POST":
        is_current = request.POST.get("is_current") == "on"

        if is_current:
            WorkHistory.objects.filter(user=user, is_current=True).update(is_current=False)

        WorkHistory.objects.create(
            user=user,
            company=request.POST.get("company"),
            job_title=request.POST.get("job_title"),
            duties=request.POST.get("duties"),
            start_date=request.POST.get("start_date"),
            end_date=None if is_current else request.POST.get("end_date"),
            exit_reason=None if is_current else request.POST.get("exit_reason"),
            is_current=is_current,
        )

        return redirect("work_history")

    completion = calculate_profile_completion(user)

    return render(request, "jobseekers/work_history.html", {
        "jobs": jobs,
        "completion": completion
    })

def edit_work_history(request, pk):
    jobseeker_id = request.session.get("jobseeker_id")

    if not jobseeker_id:
        return redirect("/login/")

    user = JobseekerAccount.objects.get(id=jobseeker_id)

    job = get_object_or_404(WorkHistory, pk=pk, user=user)

    if request.method == "POST":
        job.company = request.POST.get("company")
        job.job_title = request.POST.get("job_title")
        job.duties = request.POST.get("duties")
        job.start_date = request.POST.get("start_date")

        is_current = request.POST.get("is_current") == "on"

        if is_current:
            WorkHistory.objects.filter(user=user, is_current=True).exclude(pk=job.pk).update(is_current=False)
            job.end_date = None
            job.exit_reason = None
        else:
            job.end_date = request.POST.get("end_date")
            job.exit_reason = request.POST.get("exit_reason")

        job.is_current = is_current
        job.save()

        return redirect("work_history")

    return render(request, "jobseekers/edit_work_history.html", {"job": job})

def delete_work_history(request, pk):
    jobseeker_id = request.session.get("jobseeker_id")

    if not jobseeker_id:
        return redirect("/login/")

    user = JobseekerAccount.objects.get(id=jobseeker_id)

    job = get_object_or_404(WorkHistory, pk=pk, user=user)
    job.delete()

    return redirect("work_history")


def additional_details(request):
    jobseeker_id = request.session.get("jobseeker_id")

    if not jobseeker_id:
        return redirect("/login/")

    user = JobseekerAccount.objects.get(id=jobseeker_id)

    detail = AdditionalDetail.objects.filter(user=user).first()

    if request.method == "POST":
        cover_letter = request.POST.get("cover_letter")
        cv_file = request.FILES.get("cv")

        if detail:
            detail.cover_letter = cover_letter

            if cv_file:
                # delete old file if replacing
                if detail.cv:
                    detail.cv.delete(save=False)

                detail.cv = cv_file

            detail.save()
        else:
            AdditionalDetail.objects.create(
                user=user,
                cover_letter=cover_letter,
                cv=cv_file
            )

        return redirect("additional_details")

    completion = calculate_profile_completion(user)

    context = {
        "detail": detail,
        "completion": completion
    }

    return render(request, "jobseekers/additional.html", context)

def delete_cv(request):
    jobseeker_id = request.session.get("jobseeker_id")

    if not jobseeker_id:
        return redirect("/login/")

    user = JobseekerAccount.objects.get(id=jobseeker_id)

    detail = AdditionalDetail.objects.filter(user=user).first()

    if detail and detail.cv:
        detail.cv.delete(save=False)
        detail.cv = None
        detail.save()

    return redirect("additional_details")



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