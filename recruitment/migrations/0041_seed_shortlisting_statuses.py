from django.db import migrations


def seed_shortlisting_statuses(apps, schema_editor):
    """Ensure final_longlisted and shortlisted statuses exist."""
    JobApplicationStatus = apps.get_model('recruitment', 'JobApplicationStatus')
    statuses = [
        ('final_longlisted', 'Final Longlisted', 18, False),
        ('shortlisted',      'Shortlisted',      25, False),
    ]
    for code, name, order, is_terminal in statuses:
        JobApplicationStatus.objects.get_or_create(
            code=code,
            defaults={
                'name':        name,
                'order':       order,
                'is_terminal': is_terminal,
            }
        )


def reverse_seed(apps, schema_editor):
    pass  # leave statuses in place on reverse — safe to keep


class Migration(migrations.Migration):

    dependencies = [
        ('recruitment', '0040_committee_stage_models'),
    ]

    operations = [
        migrations.RunPython(
            seed_shortlisting_statuses,
            reverse_code=reverse_seed,
        ),
    ]
