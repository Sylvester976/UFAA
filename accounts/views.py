from django.contrib.auth.hashers import make_password
from django.contrib.sessions.models import Session
from django.core.mail import EmailMultiAlternatives
from django.db import IntegrityError
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, redirect
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from config import settings
from .models import JobseekerAccount
from django.contrib.auth import authenticate, login


from django.views import View
from django.contrib import messages
from django.shortcuts import get_object_or_404
from .models import User
from core.mixins import SuperAdminRequiredMixin
from django.views.generic import CreateView, ListView
from roles.models import Role
from django.http import HttpResponse
from accounts.permissions import permission_required

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


# Setup for RBAC

def login_view(request):
    if request.method == "POST":
        email = request.POST.get("email")
        password = request.POST.get("password")

        user = authenticate(request, email=email, password=password)

        if user:
            login(request, user)
            return HttpResponse("Logged in successfully")

    return render(request, "roles/login.html")


class UserCreateView(SuperAdminRequiredMixin, View):
    template_name = "accounts/user_form.html"

    def get(self, request):
        return render(request, self.template_name)

    def post(self, request):
        email = request.POST.get("email")
        password = request.POST.get("password")
        first_name = request.POST.get("first_name")
        last_name = request.POST.get("last_name")
        national_id = request.POST.get("national_id")

        if not email or not password:
            messages.error(request, "Email and password are required")
            return render(request, self.template_name)

        user = User.objects.create_user(
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
            national_id=national_id,
        )

        messages.success(request, "User created successfully")
        return redirect("user_list")

class UserListView(SuperAdminRequiredMixin, ListView): 
    model = User 
    template_name = "accounts/user_list.html" 
    context_object_name = "users"


def assign_role(request, user_id):
    user = User.objects.get(id=user_id)
    roles = Role.objects.all()

    if request.method == "POST":
        role_ids = request.POST.getlist("role")  # IMPORTANT: getlist()

        user.role.set(role_ids)  # replaces all existing roles
        user.save()

        return redirect("user_list")

    return render(request, "roles/assign_role_form.html", {
        "user": user,
        "roles": roles
    })

class UserUpdateView(SuperAdminRequiredMixin, View):
    template_name = "accounts/user_form.html"

    def get(self, request, pk):
        user = get_object_or_404(User, pk=pk)
        return render(request, self.template_name, {"user_obj": user})

    def post(self, request, pk):
        user = get_object_or_404(User, pk=pk)

        user.email = request.POST.get("email")
        user.first_name = request.POST.get("first_name")
        user.last_name = request.POST.get("last_name")
        user.national_id = request.POST.get("national_id")

        password = request.POST.get("password")
        if password:
            user.set_password(password)

        user.save()

        messages.success(request, "User updated successfully")
        return redirect("user_list")
    

class UserDeleteView(SuperAdminRequiredMixin, View):
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