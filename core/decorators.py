from django.http import HttpResponseForbidden
from functools import wraps


def superadmin_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return HttpResponseForbidden("Authentication required")

        if not getattr(request.user, "is_superadmin", False):
            return HttpResponseForbidden("SuperAdmin access required")

        return view_func(request, *args, **kwargs)

    return _wrapped_view

from functools import wraps
from django.core.exceptions import PermissionDenied


def role_required(allowed_roles):
    """
    allowed_roles = list of role names
    Example: @role_required(["Admin", "Manager"])
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            user = request.user

            if not user.is_authenticated:
                raise PermissionDenied

            if not user.role.exists():
                raise PermissionDenied

            if not user.role.filter(name__in=allowed_roles).exists():
                raise PermissionDenied

            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator

from functools import wraps
from django.core.exceptions import PermissionDenied


def permission_required(*permission_codes):
    """
    Example:
    @permission_required("view_reports")
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            user = request.user

            if not user.is_authenticated:
                raise PermissionDenied

            if not user.role.exists():
                raise PermissionDenied

            has_permission = user.role.filter(
                permissions__code__in=permission_codes
            ).exists()

            if not has_permission:
                raise PermissionDenied

            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


# from functools import wraps
# from django.contrib import messages
# from django.core.exceptions import PermissionDenied
# from django.shortcuts import redirect
# from django.conf import settings


# def permission_required(*permission_codes):
#     """
#     Example:
#         @permission_required("view_reports")
#     """
#     def decorator(view_func):
#         @wraps(view_func)
#         def wrapper(request, *args, **kwargs):
#             user = request.user

#             # Not authenticated
#             if not user.is_authenticated:
#                 messages.error(request, "You must be logged in to access this page.")
#                 return redirect(settings.LOGIN_URL)

#             # No roles assigned
#             if not user.role.exists():
#                 messages.error(
#                     request,
#                     "Your account has no roles assigned. Please contact the administrator."
#                 )
#                 return redirect("home")  # change to your safe fallback view

#             # Missing required permission
#             has_permission = user.role.filter(
#                 permissions__code__in=permission_codes
#             ).exists()

#             if not has_permission:
#                 messages.error(
#                     request,
#                     "You do not have permission to access this page."
#                 )
#                 return redirect("dashboard")  # change to your safe fallback view

#             return view_func(request, *args, **kwargs)

#         return wrapper
#     return decorator