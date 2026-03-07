from django.http import HttpResponseForbidden


class SuperAdminRequiredMixin:
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return HttpResponseForbidden("Authentication required")

        if not request.user.is_superadmin:
            return HttpResponseForbidden("System administrator access required")

        return super().dispatch(request, *args, **kwargs)
