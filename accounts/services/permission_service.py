from roles.models import Permission
# # from audit.services import log_request

# def collect_role_permissions(role):
#     """
#     Recursively collect permissions from role and its parents.
#     """
#     permissions = set(role.permissions.values_list("code", flat=True))

#     if role.parent:
#         permissions |= collect_role_permissions(role.parent)

#     return permissions


# def get_user_permissions(user):
#     """
#     Aggregates permission codes from all assigned roles.
#     SuperAdmin gets all permissions.
#     """

#     if not user.is_authenticated:
#         return set()

#     if user.is_superadmin:
#         return set(
#             Permission.objects.values_list("code", flat=True)
#         )

#     all_permissions = set()

#     for role in user.role.all():
#         all_permissions |= collect_role_permissions(role)

#     return all_permissions


# def user_has_permission(user, permission_code):
#     if not user.is_authenticated:
#         return False

#     if user.is_superadmin:
#         return True

#     if not hasattr(user, "_cached_permissions"):
#         user._cached_permissions = get_user_permissions(user)

#     granted = permission_code in user._cached_permissions

#     # Log permission check
#     # log_request(
#     #     user=user,
#     #     path="permission_check",
#     #     method="SYSTEM",
#     #     permission_checked=permission_code,
#     #     permission_granted=granted
#     # )

#     return granted


#//
# def get_user_permissions(user):
#     if not user.is_authenticated:
#         return set()

#     if user.is_superadmin:
#         from roles.models import Permission
#         return set(Permission.objects.values_list("code", flat=True))

#     return set(
#         user.role
#             .values_list("permissions__code", flat=True)
#             .distinct()
#     )
#//

def get_user_permissions(user):
    """
    Returns a set of permission codes assigned to user via roles.
    SuperAdmin automatically gets all permissions.
    """
    if not user.is_authenticated:
        return set()

    if user.is_superadmin:
        from roles.models import Permission
        return set(Permission.objects.values_list("code", flat=True))

    if not user.role.exists():
        return set()

    return set(
        user.role
            .values_list("permissions__code", flat=True)
            .distinct()
    )

def user_has_permission(user, permission_code):
    if not user.is_authenticated:
        return False

    if user.is_superadmin:
        return True

    if not hasattr(user, "_cached_permissions"):
        user._cached_permissions = get_user_permissions(user)

    return permission_code in user._cached_permissions
