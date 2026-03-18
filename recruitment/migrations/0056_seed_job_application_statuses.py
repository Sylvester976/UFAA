# recruitment/migrations/0056_seed_job_application_statuses.py

from django.db import migrations


STATUSES = [
    # code                 name                        order   is_terminal
    ('submitted',          'Submitted',                10,     False),
    ('longlisted',         'Longlisted',               15,     False),
    ('final_longlisted',   'Final Longlisted',         20,     False),
    ('shortlisted',        'Shortlisted',              25,     False),
    ('interviewed',        'Interviewed',              30,     False),
    ('top_candidate',      'Top Candidate',            40,     False),
    ('ceo_selected',       'CEO Selected',             50,     False),
    ('appointed',          'Appointed',                60,     True),
    ('not_selected',       'Not Selected',             99,     True),
]


def seed_statuses(apps, schema_editor):
    JobApplicationStatus = apps.get_model('recruitment', 'JobApplicationStatus')
    for code, name, order, is_terminal in STATUSES:
        JobApplicationStatus.objects.update_or_create(
            code=code,
            defaults={
                'name':        name,
                'order':       order,
                'is_terminal': is_terminal,
            },
        )


def unseed_statuses(apps, schema_editor):
    """
    Reverse: remove only the codes we added.
    Codes that already existed before this migration are left untouched
    because update_or_create would have preserved them.
    Safe to call on rollback.
    """
    JobApplicationStatus = apps.get_model('recruitment', 'JobApplicationStatus')
    codes_added = [row[0] for row in STATUSES]
    JobApplicationStatus.objects.filter(code__in=codes_added).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('recruitment', '0055_referee_organization_and_more'),
    ]

    operations = [
        migrations.RunPython(seed_statuses, reverse_code=unseed_statuses),
    ]
