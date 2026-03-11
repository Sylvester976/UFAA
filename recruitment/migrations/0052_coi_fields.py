from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('recruitment', '0051_alter_committeevote_id_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='shortlistingcommittee',
            name='coi_declared',
            field=models.BooleanField(
                default=False,
                help_text='Member has completed the COI declaration step (either way).'
            ),
        ),
        migrations.AddField(
            model_name='shortlistingcommittee',
            name='has_conflict',
            field=models.BooleanField(
                default=False,
                help_text='Member declared a conflict of interest and is recused.'
            ),
        ),
        migrations.AddField(
            model_name='shortlistingcommittee',
            name='conflict_reason',
            field=models.TextField(
                blank=True,
                help_text='Mandatory reason provided when declaring a conflict.'
            ),
        ),
        migrations.AddField(
            model_name='shortlistingcommittee',
            name='conflict_declared_at',
            field=models.DateTimeField(
                null=True,
                blank=True,
                help_text='Timestamp when COI declaration was completed.'
            ),
        ),
    ]
