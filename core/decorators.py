from django.http import HttpResponseForbidden
from functools import wraps
from django.core.exceptions import PermissionDenied

from django.contrib import messages
from django.shortcuts import redirect

from config import settings


def superadmin_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return HttpResponseForbidden("Authentication required")

        if not getattr(request.user, "is_superadmin", False):
            return HttpResponseForbidden("SuperAdmin access required")

        return view_func(request, *args, **kwargs)

    return _wrapped_view


def role_required(allowed_roles):
    """
    Example:
        @role_required(["admin", "hod_hr"])
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            user = request.user

            # Not authenticated
            if not user.is_authenticated:
                messages.error(request, "You must be logged in to access this page.")
                return redirect('/login/')


            # Superuser bypass
            if user.is_superuser:
                return view_func(request, *args, **kwargs)
            
            # No roles assigned
            if not user.role.exists():
                messages.error(
                    request,
                    "Your account has no roles assigned. Please contact the administrator."
                )
                return redirect("landing")

            # Missing required role
            if not user.role.filter(name__in=allowed_roles).exists():
                messages.error(
                    request,
                    "You do not have the required role to access this page."
                )
                return redirect("redirect_dashboard")

            return view_func(request, *args, **kwargs)

        return wrapper
    return decorator



def permission_required(*permission_codes):
    """
    Example:
        @permission_required("view_reports")
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            user = request.user

            # Not authenticated
            if not user.is_authenticated:
                messages.error(request, "You must be logged in to access this page.")
                return redirect(settings.LOGIN_URL)

            # No roles assigned
            if not user.role.exists():
                messages.error(
                    request,
                    "Your account has no roles assigned. Please contact the administrator."
                )
                return redirect("home")  # change to your safe fallback view

            # Missing required permission
            has_permission = user.role.filter(
                permissions__code__in=permission_codes
            ).exists()

            if not has_permission:
                messages.error(
                    request,
                    "You do not have permission to access this page."
                )
                return redirect("dashboard")  # change to your safe fallback view

            return view_func(request, *args, **kwargs)

        return wrapper
    return decorator