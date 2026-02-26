from django.shortcuts import redirect
from django.urls import reverse

class LoginRequiredMiddleware:
    """
    Protect all URLs except public ones: login, signup, landing
    """

    def __init__(self, get_response):
        self.get_response = get_response
        # Define public URLs by name or path
        self.PUBLIC_URLS = [
            '/',                       # landing
            '/login/',                  # login page
            '/signup/',                 # registration
            '/authregister/',           # POST endpoint for registration
            '/authlogin/',              # POST endpoint for login
            '/logout/',  # logout route must be public
        ]

    def __call__(self, request):
        path = request.path_info

        if not any(path.startswith(url) for url in self.PUBLIC_URLS):
            if 'user_id' not in request.session:
                # Handle AJAX request separately
                if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                    from django.http import JsonResponse
                    return JsonResponse({'status': 'error', 'message': 'Login required.'}, status=401)
                return redirect('/login/')

        response = self.get_response(request)
        return response