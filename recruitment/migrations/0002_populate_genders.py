from django.db import migrations


def populate_genders(apps, schema_editor):
    Gender = apps.get_model('recruitment', 'Gender')
    genders = ['Male', 'Female', 'Other']
    for gender in genders:
        Gender.objects.get_or_create(name=gender)


def reverse_genders(apps, schema_editor):
    Gender = apps.get_model('your_app_name', 'Gender')
    Gender.objects.filter(name__in=['Male', 'Female', 'Other']).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('recruitment', '0001_initial'),  # make sure this matches your last migration
    ]

    operations = [
        migrations.RunPython(populate_genders, reverse_genders),
    ]