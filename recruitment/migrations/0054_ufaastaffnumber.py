from django.db import migrations, models

STAFF_DATA = [
    ('2025043',  'LABAN K MOLONKO'),
    ('20150007', 'PIUS KIBET KIMUTAI'),
    ('2017041',  'JACK OWINO GUMBOH'),
    ('2015008',  'NICK ARTHUR MUDAMBO'),
    ('20150009', 'PAUL NDIRANGU MUYA'),
    ('2015014',  'ERIC MWANIKI NJERU'),
    ('2015019',  'GIDEON MWANZIA NZIOKI'),
    ('2015020',  'BEATRICE CHELANGAT'),
    ('2015022',  'SUSAN WAMAITHA KIHARA'),
    ('2017037',  'LEONARD LANGAT'),
    ('2017038',  'GODFREY WAWERU WAMBUGU'),
    ('2017039',  'DAVID KANDIA MASAI'),
    ('2015015',  'JACOB KIPKOECH KIPTURGO'),
    ('2015024',  'KENNEDY OUMA OTIENO'),
    ('2017031',  'FREDRICK KIPCHUMBA MUGE'),
    ('2017034',  'MAUREEN WANGARI'),
    ('2017035',  'JOSEPH CHACHA MUNYORO'),
    ('2017036',  'BEATRICE TAIGONG'),
    ('2017026',  'REGINALD I. MATEKWA'),
    ('2015012',  'WILSON MACHARIA MUKUHA'),
    ('2015018',  'FREDRICK NGEI NZIOKA'),
    ('2017030',  'EMMANUEL SHEHI CHITTA'),
    ('2017032',  'PASCAL KIRWA'),
    ('2015011',  'RISPER LISA AKINYI'),
    ('2015023',  'JAPHETH KIPCHUMBA KORIR'),
    ('2017033',  'KEVIN MWOLE NTHIWA'),
    ('2017027',  'DAMARIS LEMBI NGILA'),
]


def seed_staff_numbers(apps, schema_editor):
    UFAAStaffNumber = apps.get_model('recruitment', 'UFAAStaffNumber')
    for number, name in STAFF_DATA:
        UFAAStaffNumber.objects.get_or_create(
            staff_number=number,
            defaults={'name': name, 'is_active': True}
        )


def remove_staff_numbers(apps, schema_editor):
    apps.get_model('recruitment', 'UFAAStaffNumber').objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('recruitment', '0053_remove_interviewsectionscore_section_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='UFAAStaffNumber',
            fields=[
                ('id',           models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('staff_number', models.CharField(max_length=20, unique=True)),
                ('name',         models.CharField(blank=True, max_length=200)),
                ('is_active',    models.BooleanField(default=True)),
            ],
            options={'verbose_name': 'UFAA Staff Number', 'verbose_name_plural': 'UFAA Staff Numbers', 'ordering': ['staff_number']},
        ),
        migrations.RunPython(seed_staff_numbers, remove_staff_numbers),
    ]
