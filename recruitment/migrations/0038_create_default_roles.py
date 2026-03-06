from django.db import migrations


def seed_roles_and_admin(apps, schema_editor):

    Role = apps.get_model("roles", "Role")
    User = apps.get_model("accounts", "User")

    role_names = [
        "hod_hr",
        "panelist",
        "committee",
        "ceo",
        "admin",
    ]

    roles = []

    for name in role_names:

        role, created = Role.objects.get_or_create(
            name=name,
            defaults={"description": f"{name} role"}
        )

        roles.append(role)

    email = "admin@ufaa.go.ke"

    if not User.objects.filter(email=email).exists():

        superadmin = User.objects.create(
            email=email,
            is_superadmin=True,
            user_type=2,
            is_active=True,
        )

        superadmin.password = make_password("Admin@123")
        superadmin.save()

        superadmin.role.set(roles)


class Migration(migrations.Migration):

    dependencies = [
        ("roles", "0001_initial"),
        ("recruitment", "0037_rename_summary_panelistreport_report_summary_and_more"),  # last migration in users app
    ]

    operations = [
        migrations.RunPython(seed_roles_and_admin),
    ]