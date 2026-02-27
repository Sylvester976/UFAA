from accounts.services.permission_service import get_user_permissions


class RBACMiddleware:
    """
    Attaches permission set to request for fast access.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):

        if request.user.is_authenticated:
            request.user._cached_permissions = get_user_permissions(request.user)

        response = self.get_response(request)
        return response
