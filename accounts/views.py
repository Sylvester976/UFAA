from django.contrib.auth.hashers import make_password
from django.contrib.sessions.models import Session
from django.core.mail import EmailMultiAlternatives
from django.db import IntegrityError
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from config import settings
from .models import JobseekerAccount



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
