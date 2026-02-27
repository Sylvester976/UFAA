from .models import Gender, EthnicGroup, County, Constituency, SubCounty, Ward, JobSeekerProfile
from django.shortcuts import render, redirect, get_object_or_404
from accounts.models import JobseekerAccount, AdditionalDetail, ProfessionalQualification, WorkHistory, AcademicQualification
from django.http import JsonResponse

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
    user = get_logged_in_user(request)
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
    user = get_logged_in_user(request)
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