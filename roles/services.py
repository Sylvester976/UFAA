from .models import Role, Permission


# CREATE
def create_permission(data):
    return Permission.objects.create(**data)


# READ (single)
def get_permission(permission_id):
    return Permission.objects.filter(id=permission_id).first()


# READ (all)
def list_permissions():
    return Permission.objects.all()


# UPDATE
def update_permission(permission, data):
    for field, value in data.items():
        setattr(permission, field, value)
    permission.save()
    return permission


# DELETE
def delete_permission(permission):
    permission.delete()
    
    
# CREATE
def create_role(data):
    permissions = data.pop("permissions", [])
    role = Role.objects.create(**data)
    role.permissions.set(permissions)
    return role


# READ (single)
def get_role(role_id):
    return Role.objects.filter(id=role_id).prefetch_related("permissions").first()


# READ (all)
def list_roles():
    return Role.objects.prefetch_related("permissions").all()


# UPDATE (full role update)
def update_role(role, data):
    permissions = data.pop("permissions", None)

    for field, value in data.items():
        setattr(role, field, value)

    role.save()

    if permissions is not None:
        role.permissions.set(permissions)

    return role


# UPDATE (permissions only — your existing logic)
def update_role_permissions(role, permissions):
    role.permissions.set(permissions)
    role.save()
    return role


# DELETE
def delete_role(role):
    role.delete()