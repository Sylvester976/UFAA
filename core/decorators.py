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