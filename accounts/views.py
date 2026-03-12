import uuid
import logging
import requests
from datetime import timedelta, date

from django.contrib.auth import authenticate, login, logout
from django.core.cache import cache
from django.contrib.auth.hashers import make_password
from django.contrib.sessions.models import Session
from django.core.mail import EmailMultiAlternatives
from django.db import IntegrityError
from django.http import HttpResponse
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.views.generic import ListView

from accounts.permissions import permission_required
from config import settings
from recruitment.models import Vacancy
from roles.models import Role
from .models import JobseekerAccount

from django.utils.decorators import method_decorator
from core.decorators import role_required


logger = logging.getLogger(__name__)

def landing(request):
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
        
    # Retrieve all vacancies for rendering
    # vacancies = Vacancy.objects.all()
                
    # # External users should NOT see internal vacancies
    # # To be moved to the jobseeker dashboard
    # if request.user.role == 'applicant':
    #     vacancies = vacancies.filter(vacancy_type='external')

    return render(request, 'auth/landing.html', {'vacancies': vacancies})


def index(request):
    return render(request, 'auth/login.html')


# ── Email helpers ──────────────────────────────────────────────────────────

def _send_branded_email(to_email, subject, message_html):
    try:
        html_body = render_to_string('emails/email_base.html', {
            'subject':         subject,
            'message_content': message_html,
            'logo_url':        'https://ufaa.go.ke/wp-content/uploads/2022/07/LOGO_RVSD-2-1.png',
            'year':            date.today().year,
        })
        msg = EmailMultiAlternatives(
            subject    = subject,
            body       = subject,
            from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@ufaa.go.ke'),
            to         = [to_email],
        )
        msg.attach_alternative(html_body, 'text/html')
        msg.send(fail_silently=False)
        return True
    except Exception as e:
        logger.error(f"Email send failed to {to_email}: {e}", exc_info=True)
        return False


def _send_verification_email(user, request):
    verify_url = request.build_absolute_uri(f'/verify-email/{user.verification_token}/')
    subject = "Verify Your UFAA Job Portal Account"
    html = f"""
    <p>Dear <strong>{user.name}</strong>,</p>
    <p>Thank you for registering on the <strong>UFAA Job Portal</strong>.
    Please verify your email address to activate your account.</p>
    <div style="text-align:center; margin:2rem 0;">
        <a href="{verify_url}" style="display:inline-block; background:#C39545; color:#1D255B;
                  padding:0.75rem 2.25rem; border-radius:0.5rem; font-weight:700;
                  font-size:0.95rem; text-decoration:none; letter-spacing:0.03em;">
            ✔&nbsp; Verify Email Address
        </a>
    </div>
    <p style="font-size:0.82rem; color:#6b7280;">
        If the button does not work, copy and paste this link into your browser:<br>
        <a href="{verify_url}" style="color:#1D255B; word-break:break-all;">{verify_url}</a>
    </p>
    <p style="font-size:0.82rem; color:#6b7280;">If you did not create this account, please ignore this email.</p>
    <p style="margin-top:24px; color:#6b7280; font-size:13px;">
        Yours sincerely,<br>
        <strong style="color:#1D255B;">Human Resources &amp; Administration</strong><br>
        Unclaimed Financial Assets Authority (UFAA)
    </p>
    """
    return _send_branded_email(user.email, subject, html)


def _send_password_reset_email(user, request):
    reset_url = request.build_absolute_uri(f'/reset-password/{user.password_reset_token}/')
    subject = "Reset Your UFAA Job Portal Password"
    html = f"""
    <p>Dear <strong>{user.name}</strong>,</p>
    <p>We received a request to reset the password for your UFAA Job Portal account.</p>
    <div style="text-align:center; margin:2rem 0;">
        <a href="{reset_url}" style="display:inline-block; background:#1D255B; color:#F9E6A1;
                  padding:0.75rem 2.25rem; border-radius:0.5rem; font-weight:700;
                  font-size:0.95rem; text-decoration:none; letter-spacing:0.03em;">
            🔒&nbsp; Reset My Password
        </a>
    </div>
    <p style="font-size:0.82rem; color:#6b7280;">
        This link expires in <strong>30 minutes</strong>.<br>
        <a href="{reset_url}" style="color:#1D255B; word-break:break-all;">{reset_url}</a>
    </p>
    <p style="font-size:0.82rem; color:#6b7280;">
        If you did not request a password reset, please ignore this email.
    </p>
    <p style="margin-top:24px; color:#6b7280; font-size:13px;">
        Yours sincerely,<br>
        <strong style="color:#1D255B;">Human Resources &amp; Administration</strong><br>
        Unclaimed Financial Assets Authority (UFAA)
    </p>
    """
    return _send_branded_email(user.email, subject, html)


def _send_lockout_email(user, request):
    ip = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR', 'unknown'))
    subject = "UFAA Job Portal — Account Temporarily Locked"
    html = f"""
    <p>Dear <strong>{user.name}</strong>,</p>
    <p>We detected <strong>multiple failed login attempts</strong> on your UFAA Job Portal
    account and have <strong>temporarily locked it for 15 minutes</strong> as a security precaution.</p>
    <table style="width:100%;border-collapse:collapse;margin:1rem 0;font-size:0.85rem;">
        <tr style="border-bottom:1px solid #f0f2f8;">
            <td style="padding:0.5rem;color:#8392ab;font-weight:600;">Time</td>
            <td style="padding:0.5rem;color:#344767;">{timezone.now().strftime('%d %b %Y, %H:%M UTC')}</td>
        </tr>
        <tr>
            <td style="padding:0.5rem;color:#8392ab;font-weight:600;">IP Address</td>
            <td style="padding:0.5rem;color:#344767;">{ip}</td>
        </tr>
    </table>
    <p>If this was <strong>you</strong>, please wait 15 minutes and try again.<br>
    If this was <strong>not you</strong>, reset your password immediately.</p>
    <div style="text-align:center; margin:1.5rem 0;">
        <a href="{request.build_absolute_uri('/forgot-password/')}"
           style="display:inline-block; background:#C39545; color:#1D255B;
                  padding:0.65rem 1.75rem; border-radius:0.5rem; font-weight:700;
                  font-size:0.88rem; text-decoration:none;">
            Reset My Password
        </a>
    </div>
    <p style="margin-top:24px; color:#6b7280; font-size:13px;">
        Yours sincerely,<br>
        <strong style="color:#1D255B;">Human Resources &amp; Administration</strong><br>
        Unclaimed Financial Assets Authority (UFAA)
    </p>
    """
    _send_branded_email(user.email, subject, html)


# ── Auth Views ─────────────────────────────────────────────────────────────

def login_page(request):
    return render(request, 'auth/login.html')


def register(request):
    return render(request, 'auth/register.html')


def save_user_account(request):
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Invalid request method.'})

    name             = request.POST.get('name', '').strip()
    email            = request.POST.get('email', '').strip().lower()
    idno             = request.POST.get('idno', '').strip()
    password         = request.POST.get('password', '')
    confirm_password = request.POST.get('confirm_password', '')

    if not all([name, email, idno, password, confirm_password]):
        return JsonResponse({'status': 'error', 'message': 'All fields are required.'})

    if password != confirm_password:
        return JsonResponse({'status': 'error', 'message': 'Passwords do not match.'})

    try:
        user = JobseekerAccount.objects.create(
            name         = name,
            email        = email,
            id_no        = idno,
            password     = make_password(password),
            account_type = 1,
            is_active    = False,
            is_verified  = False,
        )

        sent = _send_verification_email(user, request)

        if sent:
            msg = (f'Registration successful. A verification link has been sent to '
                   f'<strong>{email}</strong>. Please check your inbox and spam folder.')
        else:
            msg = ('Registration successful, but we could not send the verification email. '
                   'Please use the "Resend verification" option on the login page.')

        return JsonResponse({'status': 'success', 'message': msg})

    except IntegrityError as e:
        err = str(e)
        if 'email' in err:
            msg = 'An account with this email already exists.'
        elif 'id_no' in err:
            msg = 'An account with this ID number already exists.'
        else:
            msg = 'Duplicate entry detected.'
        return JsonResponse({'status': 'error', 'message': msg})

    except Exception as e:
        return JsonResponse({'status': 'error', 'message': f'Error occurred: {e}'})



# ── Rate limiting constants ────────────────────────────────────────────────
MAX_ATTEMPTS = getattr(settings, 'LOGIN_MAX_ATTEMPTS', 5)
LOCKOUT_MINS = getattr(settings, 'LOGIN_LOCKOUT_MINS', 15)


# ── Rate limiting — stored on the model, not cache ────────────────────────

def is_locked_out(user):
    """Check if user is currently locked out."""
    if user.lockout_until and timezone.now() < user.lockout_until:
        return True
    # Auto-clear expired lockout
    if user.lockout_until and timezone.now() >= user.lockout_until:
        user.lockout_until         = None
        user.failed_login_attempts = 0
        user.save(update_fields=['lockout_until', 'failed_login_attempts'])
    return False


def get_lockout_remaining(user):
    """Return remaining lockout seconds."""
    if user.lockout_until:
        delta = user.lockout_until - timezone.now()
        return max(int(delta.total_seconds()), 0)
    return 0


def record_failed_attempt(user):
    """
    Increment failed attempt counter on the user record.
    Returns { locked, attempts, remaining }
    """
    user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
    attempts  = user.failed_login_attempts
    remaining = MAX_ATTEMPTS - attempts

    if attempts >= MAX_ATTEMPTS:
        user.lockout_until         = timezone.now() + timedelta(minutes=LOCKOUT_MINS)
        user.failed_login_attempts = 0   # reset for next lockout cycle
        user.save(update_fields=['failed_login_attempts', 'lockout_until'])
        return {'locked': True, 'attempts': attempts, 'remaining': 0}

    user.save(update_fields=['failed_login_attempts'])
    return {'locked': False, 'attempts': attempts, 'remaining': remaining}


def reset_attempts(user):
    """Clear counter on successful login."""
    user.failed_login_attempts = 0
    user.lockout_until         = None
    user.save(update_fields=['failed_login_attempts', 'lockout_until'])


# ── signin view ────────────────────────────────────────────────────────────

def signin(request):
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Invalid request method.'})

    idno     = request.POST.get('idno', '').strip()
    password = request.POST.get('password', '')

    if not idno or not password:
        return JsonResponse({'status': 'error',
                             'message': 'ID number and password are required.'})

    # ── Fetch user first (lockout is per-user, stored on model) ───────────
    try:
        user = JobseekerAccount.objects.get(id_no=idno)
    except JobseekerAccount.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Invalid credentials.'})

    # ── Lockout check ─────────────────────────────────────────────────────
    if is_locked_out(user):
        remaining = get_lockout_remaining(user)
        mins = remaining // 60
        secs = remaining % 60
        time_str = f"{mins}m {secs}s" if secs else f"{mins} minute(s)"
        return JsonResponse({
            'status':  'locked',
            'message': (f'Account temporarily locked due to too many failed attempts. '
                        f'Try again in {time_str}, or reset your password.'),
        })

    # ── Unverified ────────────────────────────────────────────────────────
    if not user.is_verified:
        return JsonResponse({
            'status':  'unverified',
            'message': 'Your email address has not been verified. Please check your inbox.',
            'email':   user.email,
        })

    # ── Inactive ──────────────────────────────────────────────────────────
    if not user.is_active:
        return JsonResponse({'status': 'error',
                             'message': 'Your account has been deactivated. Please contact HR.'})

    # ── Password check ────────────────────────────────────────────────────
    if not user.check_password(password):
        result = record_failed_attempt(user)

        if result['locked']:
            _send_lockout_email(user, request)
            return JsonResponse({
                'status':  'locked',
                'message': (f'Too many failed attempts. Account locked for {LOCKOUT_MINS} minutes. '
                            f'A notification has been sent to your registered email.'),
            })

        remaining = result['remaining']
        warn = " ⚠️ Last attempt before lockout!" if remaining == 1 else ""
        return JsonResponse({
            'status':  'error',
            'message': f'Invalid credentials. {remaining} attempt(s) remaining.{warn}',
        })

    # ── Success ───────────────────────────────────────────────────────────
    reset_attempts(user)

    if user.session_key:
        try:
            Session.objects.get(session_key=user.session_key).delete()
        except Session.DoesNotExist:
            pass

    request.session['user_id'] = user.id
    user.last_login             = timezone.now()
    user.session_key            = request.session.session_key
    user.save(update_fields=['last_login', 'session_key'])

    return JsonResponse({'status': 'success', 'message': 'Login successful.'})


def logout_view(request):
    user_id = request.session.get('user_id')
    if user_id:
        try:
            user = JobseekerAccount.objects.get(id=user_id)
            user.session_key = None
            user.save(update_fields=['session_key'])
        except JobseekerAccount.DoesNotExist:
            pass
    request.session.flush()
    return redirect('/login/')


# ── Email Verification ─────────────────────────────────────────────────────

def verify_email(request, token):
    try:
        user = JobseekerAccount.objects.get(verification_token=token)
    except JobseekerAccount.DoesNotExist:
        return render(request, 'auth/verification_result.html', {
            'success': False,
            'message': 'This verification link is invalid or has already been used.',
        })

    if user.is_verified and user.is_active:
        return render(request, 'auth/verification_result.html', {
            'success': True, 'already': True,
            'message': 'Your account is already verified. Please log in.',
        })

    user.is_active          = True
    user.is_verified        = True
    user.verification_token = uuid.uuid4()
    user.save(update_fields=['is_active', 'is_verified', 'verification_token'])

    return render(request, 'auth/verification_result.html', {
        'success': True, 'already': False,
        'message': 'Your email has been verified. Your account is now active.',
    })


def resend_verification(request):
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Invalid request method.'})

    identifier = request.POST.get('identifier', '').strip().lower()
    if not identifier:
        return JsonResponse({'status': 'error', 'message': 'Email or ID number is required.'})

    try:
        if '@' in identifier:
            user = JobseekerAccount.objects.get(email=identifier)
        else:
            user = JobseekerAccount.objects.get(id_no=identifier)
    except JobseekerAccount.DoesNotExist:
        return JsonResponse({'status': 'success',
                             'message': 'If an account exists, a verification link has been sent.'})

    if user.is_verified and user.is_active:
        return JsonResponse({'status': 'error',
                             'message': 'This account is already verified. Please log in.'})

    sent = _send_verification_email(user, request)
    return JsonResponse({
        'status':  'success' if sent else 'error',
        'message': ('Verification email sent. Please check your inbox.'
                    if sent else 'Failed to send email. Please try again later.'),
    })


# ── Forgot / Reset Password ────────────────────────────────────────────────

def forgot_password(request):
    return render(request, 'auth/forgot_password.html')


def send_reset_link(request):
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Invalid request method.'})

    identifier = request.POST.get('identifier', '').strip().lower()
    if not identifier:
        return JsonResponse({'status': 'error',
                             'message': 'Please enter your email or ID number.'})

    try:
        if '@' in identifier:
            user = JobseekerAccount.objects.get(email=identifier)
        else:
            user = JobseekerAccount.objects.get(id_no=identifier)
    except JobseekerAccount.DoesNotExist:
        return JsonResponse({'status': 'success',
                             'message': 'If an account exists, a reset link has been sent.'})

    if not user.is_active or not user.is_verified:
        return JsonResponse({'status': 'error',
                             'message': ('Your account is not yet verified. '
                                         'Please verify your email before resetting your password.')})

    user.password_reset_token      = uuid.uuid4()
    user.password_reset_expires_at = timezone.now() + timedelta(minutes=30)
    user.save(update_fields=['password_reset_token', 'password_reset_expires_at'])

    sent = _send_password_reset_email(user, request)
    return JsonResponse({
        'status':  'success' if sent else 'error',
        'message': ('Password reset link sent. Please check your inbox.'
                    if sent else 'Failed to send email. Please try again.'),
    })


def reset_password(request, token):
    try:
        user = JobseekerAccount.objects.get(password_reset_token=token)
    except JobseekerAccount.DoesNotExist:
        return render(request, 'auth/reset_password.html', {
            'valid': False,
            'error': 'This reset link is invalid or has already been used.',
        })

    if timezone.now() > user.password_reset_expires_at:
        return render(request, 'auth/reset_password.html', {
            'valid': False,
            'error': 'This reset link has expired. Please request a new one.',
        })

    return render(request, 'auth/reset_password.html', {'valid': True, 'token': str(token)})


def do_reset_password(request):
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Invalid request method.'})

    token            = request.POST.get('token', '').strip()
    password         = request.POST.get('password', '')
    confirm_password = request.POST.get('confirm_password', '')

    if not all([token, password, confirm_password]):
        return JsonResponse({'status': 'error', 'message': 'All fields are required.'})

    if password != confirm_password:
        return JsonResponse({'status': 'error', 'message': 'Passwords do not match.'})

    if len(password) < 8:
        return JsonResponse({'status': 'error',
                             'message': 'Password must be at least 8 characters.'})

    try:
        user = JobseekerAccount.objects.get(password_reset_token=uuid.UUID(token))
    except (JobseekerAccount.DoesNotExist, ValueError):
        return JsonResponse({'status': 'error', 'message': 'Invalid reset token.'})

    if timezone.now() > user.password_reset_expires_at:
        return JsonResponse({'status': 'error',
                             'message': 'This reset link has expired. Please request a new one.'})

    user.password                  = make_password(password)
    user.password_reset_token      = uuid.uuid4()
    user.password_reset_expires_at = timezone.now()
    user.save(update_fields=['password', 'password_reset_token', 'password_reset_expires_at'])

    return JsonResponse({'status': 'success',
                         'message': 'Password reset successfully. You can now log in.'})



def dashboard_logout(request):
    if request.user.is_authenticated:
        user = request.user

        # Clear stored session key
        user.session_key = None
        user.save(update_fields=["session_key"])

    # Clear Django auth session
    logout(request)

    # Completely flush session data
    request.session.flush()

    return redirect('/staff/')


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


# Setup for RBAC

def login_view(request):
    if request.method == "POST":
        email = request.POST.get("email")
        password = request.POST.get("password")

        user = authenticate(request, email=email, password=password)

        if user:
            login(request, user)
            # return HttpResponse("Logged in successfully")
            return redirect('redirect_dashboard')

    return render(request, "roles/login.html")


from django.contrib.auth.decorators import login_required


@login_required
def redirect_dashboard(request):

    priority = ["admin", "hod_hr",  "committee", "panelist", "ceo"]

    roles = request.user.role.values_list("name", flat=True)

    for role in priority:

        if role in roles:

            if role == "ceo":
                return redirect("ceo_dashboard")

            if role == "hod_hr":
                return redirect("hr_dashboard")

            if role == "committee":
                return redirect("committee_dashboard")

            if role == "panelist":
                return redirect("panelist_dashboard")
            
            if role == "admin":
                return redirect("admin_dashboard")

    # fallback if user has no role
    return redirect("login")
    # return HttpResponse("User has no role")


from django.shortcuts import render, redirect
from django.views import View
from django.contrib import messages
from accounts.models import User
from core.mixins import SuperAdminRequiredMixin

class UserCreateView(SuperAdminRequiredMixin, View):
    template_name = "accounts/user_form.html"

    def get(self, request):
        return render(request, self.template_name)

    def post(self, request):
        # Basic User fields
        email = request.POST.get("email")
        password = request.POST.get("password")
        first_name = request.POST.get("first_name")
        last_name = request.POST.get("last_name")
        national_id = request.POST.get("national_id")

        # InternalProfile fields
        date_of_birth = request.POST.get("date_of_birth")
        gender = request.POST.get("gender")
        ethnic_group = request.POST.get("ethnic_group")
        home_county = request.POST.get("home_county")
        disability_status = request.POST.get("disability_status") == "on"
        job_group = request.POST.get("job_group")
        designation = request.POST.get("designation")
        date_of_appointment = request.POST.get("date_of_appointment")

        # Validation
        if not email or not password:
            messages.error(request, "Email and password are required")
            return render(request, self.template_name)

        try:
            # Create User
            user = User.objects.create_user(
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
                national_id=national_id,
                user_type=2,  # internal user
                is_active=True
            )

            # Create InternalProfile
            # InternalProfile.objects.create(
            #     user=user,
            #     national_id=national_id,
            #     date_of_birth=date_of_birth,
            #     gender=gender,
            #     ethnic_group=ethnic_group,
            #     home_county=home_county,
            #     disability_status=disability_status,
            #     job_group=job_group,
            #     designation=designation,
            #     date_of_appointment=date_of_appointment
            # )
            
            messages.success(request, "Internal user created successfully")
            return redirect("user_list")

        except Exception as e:
            messages.error(request, f"Error creating user: {e}")
            return render(request, self.template_name)
        
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page"] = "Admin Dashboard"
        return context


@method_decorator(role_required(["admin", "hod_hr"]), name="dispatch")
class UserListView(ListView):
    model = User
    template_name = "accounts/user_list.html"
    context_object_name = "users"

    def get_queryset(self):
        # Only internal users (user_type=2)
        return User.objects.filter(user_type=2)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page"] = "Admin Dashboard"
        return context


def assign_role(request, user_id):
    user = User.objects.get(id=user_id)
    roles = Role.objects.all()

    if request.method == "POST":
        role_ids = request.POST.getlist("role")  # IMPORTANT: getlist()
        user.role.set(role_ids)  # replaces all existing roles
        user.save()
        return redirect("user_list")

    assigned_role_ids = user.role.values_list("id", flat=True)

    context = {
        "page": "Admin Dashboard",
        "user": user,
        "roles": roles,
        "assigned_role_ids": assigned_role_ids
    }
    return render(request, "roles/assign_role_form.html", context)


class UserUpdateView(SuperAdminRequiredMixin, View):
    template_name = "accounts/user_form.html"

    def get(self, request, pk):
        user = get_object_or_404(User, pk=pk)

        context = {
            "user_obj": user,
            "page": "Admin Dashboard",
        }

        return render(request, self.template_name, context)

    def post(self, request, pk):
        user = get_object_or_404(User, pk=pk)

        # Preserve current roles
        existing_roles = user.role.all()

        user.email = request.POST.get("email")
        user.first_name = request.POST.get("first_name")
        user.last_name = request.POST.get("last_name")
        user.national_id = request.POST.get("national_id")

        password = request.POST.get("password")
        if password:
            user.set_password(password)

        user.save()

        # Re-assign roles to ensure they remain unchanged
        user.role.set(existing_roles)

        messages.success(request, "User updated successfully")
        return redirect("user_list")
    

class UserDeleteView(SuperAdminRequiredMixin, View):

    def get(self, request, pk):
        user = get_object_or_404(User, pk=pk)

        context = {
            "user": user,
            "page": "Admin Dashboard",
        }

        return render(request, "accounts/confirm_delete.html", context)

    def post(self, request, pk):
        user = get_object_or_404(User, pk=pk)
        user.delete()

        messages.success(request, "User deleted successfully")
        return redirect("user_list")

# Sample permissions view for reference
@permission_required("view_dashboard")
def protected_dashboard(request):
    return HttpResponse("Welcome to protected dashboard")



@permission_required("view_dashboard")
def test_dashbord(request):
    return render(request, 'accounts/test_dashbord.html')