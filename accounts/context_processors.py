from .models import JobseekerAccount

def logged_in_user(request):
    user_id = request.session.get('user_id')

    user = None
    if user_id:
        user = JobseekerAccount.objects.filter(pk=user_id).first()

    return {
        'logged_user': user
    }