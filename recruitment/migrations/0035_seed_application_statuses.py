from django.db import migrations


def seed_job_application_statuses(apps, schema_editor):
    JobApplicationStatus = apps.get_model('recruitment', 'JobApplicationStatus')

    statuses = [
        # code                  name                        order  is_terminal
        ('longlisted',          'Longlisted',               15,    False),
        ('not_selected',        'Not Selected',             99,    True),
        ('committee_review',    'Committee Review',         20,    False),
        ('appointed',           'Appointed',                70,    True),
        ('withdrawn',           'Withdrawn',                98,    True),
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
    # Only remove what we added — don't touch pre-existing records
    JobApplicationStatus = apps.get_model('recruitment', 'JobApplicationStatus')
    codes_to_remove = [
        'longlisted',
        'not_selected',
        'committee_review',
        'appointed',
        'withdrawn',
    ]
    JobApplicationStatus.objects.filter(code__in=codes_to_remove).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('recruitment', '0034_alter_jobapplication_screening_flags_and_more'),
    ]

    operations = [
        migrations.RunPython(
            seed_job_application_statuses,
            reverse_code=reverse_seed,
        ),
    ]