from django.core.mail import EmailMultiAlternatives
from django.shortcuts import render, redirect
from django.http import JsonResponse, HttpResponse
from django.contrib.auth.hashers import make_password, check_password
from django.template.loader import render_to_string
from django.urls import reverse
from config import settings
from .models import JobseekerAccount
from .models import AdditionalDetail, JobseekerAccount, JobseekerProfile, ProfessionalQualification, WorkHistory
from django.db import IntegrityError
from django.utils import timezone
from django.contrib.sessions.models import Session


from django.shortcuts import render, redirect
from .models import JobseekerProfile


from django.shortcuts import render, redirect, get_object_or_404
from .models import AcademicQualification
from accounts.models import JobseekerAccount

def landing(request):
    return render(request, 'auth/landing.html')

def index(request):
    return render(request, 'auth/login.html')

def register(request):
    return render(request, 'auth/register.html')

def save_user_account(request):
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Invalid request method.'})

    # Get POST data
    name = request.POST.get('name', '').strip()
    email = request.POST.get('email', '').strip()
    idno = request.POST.get('idno', '').strip()
    password = request.POST.get('password', '')
    confirm_password = request.POST.get('confirm_password', '')

    # Basic validations
    if not all([name, email, idno, password, confirm_password]):
        return JsonResponse({'status': 'error', 'message': 'All fields are required.'})

    if password != confirm_password:
        return JsonResponse({'status': 'error', 'message': 'Passwords do not match.'})

    # Hash password
    encrypted_password = make_password(password)

    try:
        # Save user to DB
        JobseekerAccount.objects.create(
            name=name,
            email=email,
            id_no=idno,
            password=encrypted_password,
            account_type=1,
            is_active=True,
            is_verified=False,
        )

        return JsonResponse({'status': 'success', 'message': 'Registration successful.'})

    except IntegrityError as e:
        # Check which field caused the integrity error
        if 'email' in str(e):
            msg = 'An account with this email already exists.'
        elif 'id_no' in str(e):
            msg = 'An account with this ID number already exists.'
        else:
            msg = 'Duplicate entry detected.'
        return JsonResponse({'status': 'error', 'message': msg})

    except Exception as e:
        return JsonResponse({'status': 'error', 'message': f'Error occurred: {e}'})

def signin(request):
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Invalid request method.'})

    idno = request.POST.get('idno', '').strip()
    password = request.POST.get('password', '')

    if not idno or not password:
        return JsonResponse({'status': 'error', 'message': 'ID number and password are required.'})

    try:
        user = JobseekerAccount.objects.get(id_no=idno)

        if not user.is_active:
            return JsonResponse({'status': 'error', 'message': 'Account is disabled.'})
        # if not user.is_verified:
        #     send_verification_email(request, user)
        #     return JsonResponse({
        #         'status': 'error',
        #         'message': 'Account not verified. Verification link sent to your email.'
        #     })
        if not user.check_password(password):
            return JsonResponse({'status': 'error', 'message': 'Invalid credentials.'})

        # Single-session enforcement
        if user.session_key:
            try:
                Session.objects.get(session_key=user.session_key).delete()
            except Session.DoesNotExist:
                pass

        # Create new session
        request.session['user_id'] = user.id
        user.last_login = timezone.now()
        user.session_key = request.session.session_key
        user.save()

        return JsonResponse({'status': 'success', 'message': 'Login successful.'})

    except JobseekerAccount.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'User not found.'})

def logout(request):
    user_id = request.session.get('user_id')
    if user_id:
        try:
            user = JobseekerAccount.objects.get(id=user_id)
            # Clear session key in DB
            user.session_key = None
            user.save()
        except JobseekerAccount.DoesNotExist:
            pass

    # Delete session completely
    request.session.flush()  # clears all session data

    return redirect('/login/')

def verify_email(request, token):
    try:
        user = JobseekerAccount.objects.get(verification_token=token)
        user.is_verified = True
        user.save()
        return HttpResponse("Email verified successfully. You can now login.")
    except JobseekerAccount.DoesNotExist:
        return HttpResponse("Invalid or expired verification link.")

def send_verification_email(request, user):
    verification_url = request.build_absolute_uri(
        reverse('verify_email', args=[user.verification_token])
    )

    context = {
        'user': user,
        'verification_url': verification_url,
    }

    subject = "Verify Your Account"
    from_email = settings.DEFAULT_FROM_EMAIL
    to_email = [user.email]

    html_content = render_to_string('emails/verification_email.html', context)

    email = EmailMultiAlternatives(subject, '', from_email, to_email)
    email.attach_alternative(html_content, "text/html")
    email.send()



def get_logged_in_user(request):
    user_id = request.session.get("user_id")

    if not user_id:
        return None

    try:
        return JobseekerAccount.objects.get(id=user_id)
    except JobseekerAccount.DoesNotExist:
        request.session.flush()
        return None

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

from django.urls import reverse
from django.shortcuts import redirect

def enforce_step(user, current_step):
    next_required = get_next_step(user)

    if current_step != next_required:
        return redirect(next_required)

    return None

def profile_view(request):
    user_id = request.session.get("user_id")

    if not user_id:
        return redirect("/login/")

    try:
        user = JobseekerAccount.objects.get(id=user_id)
    except JobseekerAccount.DoesNotExist:
        request.session.flush()
        return redirect("/login/")

    profile = JobseekerProfile.objects.filter(user=user).first()

    if request.method == "POST":
        first_name = request.POST.get("first_name")
        second_name = request.POST.get("second_name")
        date_of_birth = request.POST.get("date_of_birth")
        gender = request.POST.get("gender")
        ethnic_group = request.POST.get("ethnic_group")
        home_county = request.POST.get("home_county")
        disability_status = request.POST.get("disability_status")

        if profile:
            profile.first_name = first_name
            profile.second_name = second_name
            profile.date_of_birth = date_of_birth
            profile.gender = gender
            profile.ethnic_group = ethnic_group
            profile.home_county = home_county
            profile.disability_status = disability_status
            profile.save()
        else:
            profile = JobseekerProfile.objects.create(
                user=user,
                first_name=first_name,
                second_name=second_name,
                date_of_birth=date_of_birth,
                gender=gender,
                ethnic_group=ethnic_group,
                home_county=home_county,
                disability_status=disability_status
            )

        return redirect("profile")

    return render(request, "jobseekers/profile.html", {"profile": profile})


def delete_profile(request):
    user_id = request.session.get("user_id")

    if not user_id:
        return redirect("/login/")

    try:
        user = JobseekerAccount.objects.get(id=user_id)
        profile = JobseekerProfile.objects.filter(user=user).first()

        if profile:
            profile.delete()
    except JobseekerAccount.DoesNotExist:
        pass

    return redirect("profile")



def calculate_profile_completion(user):
    score = 0
    total = 5

    if hasattr(user, "profile"):
        score += 1

    if user.academic_qualifications.exists():
        score += 1

    if user.professional_qualifications.exists():
        score += 1

    if user.work_history.exists():
        score += 1

    if hasattr(user, "additional_detail"):
        detail = user.additional_detail
        if detail.cover_letter or detail.cv:
            score += 1

    return int((score / total) * 100)

def academic_qualifications(request):
    user = get_logged_in_user(request)
    if not user:
        return redirect("/login/")

    qualifications = AcademicQualification.objects.filter(user=user)

    if request.method == "POST":
        AcademicQualification.objects.create(
            user=user,
            level=request.POST.get("level"),
            certificate=request.FILES.get("certificate"),
            transcript=request.FILES.get("transcript"),
        )
        return redirect("academic_qualifications")

    completion = calculate_profile_completion(user)

    return render(request, "jobseekers/academic.html", {
        "qualifications": qualifications,
        "completion": completion
    })


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