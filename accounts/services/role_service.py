def assign_role_to_user(user, role):
    user.role = role
    user.save()
    return user
