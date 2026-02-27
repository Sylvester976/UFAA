from rest_framework.permissions import BasePermission
from .services.permission_service import user_has_permission


class HasRBACPermission(BasePermission):

    def has_permission(self, request, view):
        required_permission = getattr(view, "permission_code", None)

        if not required_permission:
            return True

        return user_has_permission(request.user, required_permission)
