from django.db import migrations


def populate_genders(apps, schema_editor):
    Gender = apps.get_model('recruitment', 'Gender')
    genders = ['Male', 'Female', 'Other']

    for gender in genders:
        Gender.objects.get_or_create(name=gender)


def reverse_genders(apps, schema_editor):
    Gender = apps.get_model('recruitment', 'Gender')
    Gender.objects.filter(
        name__in=['Male', 'Female', 'Other']
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('recruitment', '0004_jobseekerprofile_disability_other_and_more'),  
        # Replace with the last migration in recruitment
    ]

    operations = [
        migrations.RunPython(
            populate_genders,
            reverse_genders
        ),
    ]