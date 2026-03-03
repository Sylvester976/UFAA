from .models import JobseekerAccount
from recruitment.models import JobApplicationNotification

def logged_in_user(request):
    user_id = request.session.get('user_id')

    user = None
    if user_id:
        user = JobseekerAccount.objects.filter(pk=user_id).first()

    return {
        'logged_user': user
    }

def notifications(request):
    user_id = request.session.get('user_id')
    if not user_id:
        return {'notifications': [], 'unread_notif_count': 0}

    notifs = (
        JobApplicationNotification.objects
        .filter(user_id=user_id)
        .select_related('related_application__vacancy')
        .order_by('-created_at')[:10]   # latest 10 shown in dropdown
    )
    unread = JobApplicationNotification.objects.filter(
        user_id=user_id, is_read=False
    ).count()

    return {
        'notifications':      notifs,
        'unread_notif_count': unread,
    }