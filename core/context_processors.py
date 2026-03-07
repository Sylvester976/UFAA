def user_roles(request):
    user_roles = []

    if request.user.is_authenticated:
        user_roles = request.user.role.values_list('name', flat=True)

    return {
        'user_roles': user_roles,
    }