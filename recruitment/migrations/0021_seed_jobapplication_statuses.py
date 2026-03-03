from django.db import migrations

def seed_statuses(apps, schema_editor):
    JobApplicationStatus = apps.get_model('recruitment', 'JobApplicationStatus')
    statuses = [
        ('submitted',           'Submitted',           'Application received by HR',         1, False),
        ('under_review',        'Under Review',        'Being reviewed by HR',               2, False),
        ('shortlisted',         'Shortlisted',         'Selected for further consideration', 3, False),
        ('interview_scheduled', 'Interview Scheduled', 'Interview has been arranged',        4, False),
        ('rejected',            'Rejected',            'Application unsuccessful',           5, True),
        ('offered',             'Offered',             'Job offer extended',                 6, True),
    ]
    for code, name, desc, order, terminal in statuses:
        JobApplicationStatus.objects.get_or_create(
            code=code,
            defaults={'name': name, 'description': desc,
                      'order': order, 'is_terminal': terminal}
        )

def unseed_statuses(apps, schema_editor):
    JobApplicationStatus = apps.get_model('recruitment', 'JobApplicationStatus')
    JobApplicationStatus.objects.all().delete()

class Migration(migrations.Migration):
    dependencies = [
        ('recruitment', '0020_jobapplicationstatus_jobapplication_and_more'),  # your migration number
    ]
    operations = [
        migrations.RunPython(seed_statuses, unseed_statuses),
    ]