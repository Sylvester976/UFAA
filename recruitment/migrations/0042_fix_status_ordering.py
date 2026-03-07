from django.db import migrations


def fix_status_ordering(apps, schema_editor):
    JobApplicationStatus = apps.get_model('recruitment', 'JobApplicationStatus')

    updates = [
        ('submitted',           1,   False),
        ('under_review',        2,   False),
        ('longlisted',          15,  False),
        ('final_longlisted',    18,  False),
        ('committee_review',    20,  False),
        ('shortlisted',         25,  False),
        ('interview_scheduled', 40,  False),
        ('offered',             60,  False),
        ('appointed',           70,  True),
        ('withdrawn',           98,  True),
        ('not_selected',        99,  True),
        ('rejected',            100, True),
    ]

    for code, order, is_terminal in updates:
        JobApplicationStatus.objects.filter(code=code).update(
            order=order,
            is_terminal=is_terminal,
        )


def reverse_migration(apps, schema_editor):
    pass  # ordering changes are non-destructive, no need to reverse


class Migration(migrations.Migration):

    dependencies = [
        ('recruitment', '0041_seed_shortlisting_statuses'),
    ]

    operations = [
        migrations.RunPython(
            fix_status_ordering,
            reverse_code=reverse_migration,
        ),
    ]
