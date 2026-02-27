from django.http import HttpResponseForbidden
from .services.permission_service import user_has_permission


def permission_required(permission_code):
    def decorator(view_func):
        def wrapper(request, *args, **kwargs):
            if not user_has_permission(request.user, permission_code):
                return HttpResponseForbidden("Permission denied")
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


class PermissionRequiredMixin:
    permission_code = None

    def dispatch(self, request, *args, **kwargs):
        if not self.permission_code:
            raise ValueError("permission_code not set")

        if not user_has_permission(request.user, self.permission_code):
            return HttpResponseForbidden("Permission denied")

        return super().dispatch(request, *args, **kwargs)
