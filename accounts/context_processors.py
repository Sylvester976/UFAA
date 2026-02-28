from .models import User

def logged_in_user(request):
    user_id = request.session.get('user_id')

    user = None
    if user_id:
        user = User.objects.filter(pk=user_id, user_type=1).first()

    return {
        'logged_user': user
    }