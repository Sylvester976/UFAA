from django.shortcuts import redirect
from django.urls import resolve

class LoginRequiredMiddleware:

    PUBLIC_VIEWS = {
        'landing',
        'index',
        'signup',
        'authregister',
        'authlogin',
        'logout',
        'verify_email',
        'send_verification_email',
        'vacancy_detail',
        'login_view',
        'hr_dashboard',

    }

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):

        # Always allow admin
        if request.path.startswith('/admin/'):
            return self.get_response(request)

        try:
            current_view = resolve(request.path_info).view_name
        except:
            current_view = None

        # If public view → allow
        if current_view in self.PUBLIC_VIEWS:
            return self.get_response(request)

        # Otherwise require login
        if not request.session.get('user_id'):
            return redirect('/login/')

        return self.get_response(request)