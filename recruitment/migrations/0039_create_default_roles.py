from django.db import migrations
from django.contrib.auth.hashers import make_password
import os


def seed_roles_and_admin(apps, schema_editor):

    Role = apps.get_model("roles", "Role")
    User = apps.get_model("accounts", "User")

    role_names = [
        "hod_hr",
        "panelist",
        "committee",
        "ceo",
        "admin",
        "auditor",
    ]

    roles = []

    for name in role_names:
        role, created = Role.objects.get_or_create(
            name=name,
            defaults={"description": f"{name} role"}
        )
        roles.append(role)

    email = "admin@ufaa.go.ke"

    # get password from environment variable
    password = os.getenv("DEFAULT_ADMIN_PASSWORD")

    if password and not User.objects.filter(email=email).exists():

        superadmin = User.objects.create(
            email=email,
            is_superadmin=True,
            user_type=1,
            is_active=True,
            password=make_password(password),
        )

        superadmin.role.set(roles)


class Migration(migrations.Migration):

    dependencies = [
        ("roles", "0001_initial"),
        ("recruitment", "0038_seed_application_statuses"),
    ]

    operations = [
        migrations.RunPython(seed_roles_and_admin),
    ]