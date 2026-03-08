from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone
from django.conf import settings


class Migration(migrations.Migration):
    """
    Creates committee stage models.
    Uses SeparateDatabaseAndState so if tables already exist
    (created by a colleague outside git) the migration won't crash.
    Fresh environments get the tables created normally via RunSQL IF NOT EXISTS.
    """

    dependencies = [
        ('recruitment', '0039_create_default_roles'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.CreateModel(
                    name='ShortlistingCommittee',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True)),
                        ('vacancy', models.ForeignKey('recruitment.Vacancy', on_delete=django.db.models.deletion.CASCADE, related_name='shortlisting_committee')),
                        ('member', models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=django.db.models.deletion.CASCADE, related_name='committee_assignments')),
                        ('appointed_by', models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=django.db.models.deletion.SET_NULL, null=True, blank=True, related_name='committee_appointments_made')),
                        ('appointed_at', models.DateTimeField(default=django.utils.timezone.now)),
                        ('is_active', models.BooleanField(default=True)),
                        ('scores_submitted', models.BooleanField(default=False)),
                        ('scores_submitted_at', models.DateTimeField(null=True, blank=True)),
                        ('picks_submitted', models.BooleanField(default=False)),
                        ('picks_submitted_at', models.DateTimeField(null=True, blank=True)),
                    ],
                    options={'unique_together': {('vacancy', 'member')}},
                ),
                migrations.CreateModel(
                    name='CommitteeScore',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True)),
                        ('vacancy', models.ForeignKey('recruitment.Vacancy', on_delete=django.db.models.deletion.CASCADE, related_name='committee_scores')),
                        ('application', models.ForeignKey('recruitment.JobApplication', on_delete=django.db.models.deletion.CASCADE, related_name='committee_scores')),
                        ('member', models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=django.db.models.deletion.CASCADE, related_name='committee_scores_given')),
                        ('score', models.PositiveSmallIntegerField()),
                        ('comment', models.TextField()),
                        ('is_draft', models.BooleanField(default=True)),
                        ('submitted', models.BooleanField(default=False)),
                        ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
                        ('submitted_at', models.DateTimeField(null=True, blank=True)),
                        ('updated_at', models.DateTimeField(auto_now=True)),
                    ],
                    options={'unique_together': {('vacancy', 'application', 'member')}},
                ),
                migrations.CreateModel(
                    name='CommitteeScoreAmendment',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True)),
                        ('score', models.ForeignKey('recruitment.CommitteeScore', on_delete=django.db.models.deletion.CASCADE, related_name='amendments')),
                        ('old_score', models.PositiveSmallIntegerField()),
                        ('new_score', models.PositiveSmallIntegerField()),
                        ('old_comment', models.TextField()),
                        ('new_comment', models.TextField()),
                        ('reason', models.TextField()),
                        ('amended_by', models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=django.db.models.deletion.SET_NULL, null=True, related_name='score_amendments')),
                        ('amended_at', models.DateTimeField(default=django.utils.timezone.now)),
                    ],
                ),
                migrations.CreateModel(
                    name='ShortlistPick',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True)),
                        ('vacancy', models.ForeignKey('recruitment.Vacancy', on_delete=django.db.models.deletion.CASCADE, related_name='shortlist_picks')),
                        ('application', models.ForeignKey('recruitment.JobApplication', on_delete=django.db.models.deletion.CASCADE, related_name='shortlist_picks')),
                        ('member', models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=django.db.models.deletion.CASCADE, related_name='shortlist_picks')),
                        ('include', models.BooleanField()),
                        ('reason', models.TextField()),
                        ('decided_at', models.DateTimeField(default=django.utils.timezone.now)),
                    ],
                    options={'unique_together': {('vacancy', 'application', 'member')}},
                ),
                migrations.CreateModel(
                    name='ShortlistConsent',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True)),
                        ('vacancy', models.ForeignKey('recruitment.Vacancy', on_delete=django.db.models.deletion.CASCADE, related_name='shortlist_consents')),
                        ('member', models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=django.db.models.deletion.CASCADE, related_name='shortlist_consents')),
                        ('response', models.CharField(max_length=20, choices=[('consented','Consented'),('dissented','Dissented'),('no_response','No Response')], default='no_response')),
                        ('dissent_reason', models.TextField(blank=True)),
                        ('responded_at', models.DateTimeField(null=True, blank=True)),
                    ],
                    options={'unique_together': {('vacancy', 'member')}},
                ),
                migrations.CreateModel(
                    name='ShortlistLog',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True)),
                        ('vacancy', models.ForeignKey('recruitment.Vacancy', on_delete=django.db.models.deletion.CASCADE, related_name='shortlist_logs')),
                        ('application', models.ForeignKey('recruitment.JobApplication', on_delete=django.db.models.deletion.SET_NULL, null=True, blank=True, related_name='shortlist_logs')),
                        ('performed_by', models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=django.db.models.deletion.SET_NULL, null=True, blank=True, related_name='shortlist_actions')),
                        ('action', models.CharField(max_length=50)),
                        ('notes', models.TextField(blank=True)),
                        ('metadata', models.JSONField(default=dict, blank=True)),
                        ('timestamp', models.DateTimeField(default=django.utils.timezone.now)),
                        ('performed_by_label', models.CharField(max_length=200, blank=True)),
                    ],
                ),
                migrations.AddField(model_name='vacancy', name='committee_appointed_at', field=models.DateTimeField(null=True, blank=True)),
                migrations.AddField(model_name='vacancy', name='shortlist_finalised_at', field=models.DateTimeField(null=True, blank=True)),
                migrations.AddField(model_name='vacancy', name='shortlist_finalised_by', field=models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=django.db.models.deletion.SET_NULL, null=True, blank=True, related_name='shortlists_finalised')),
                migrations.AddField(model_name='vacancy', name='is_overdue', field=models.BooleanField(default=False)),
            ],

            database_operations=[

                migrations.RunSQL("""
                    CREATE TABLE IF NOT EXISTS recruitment_shortlistingcommittee (
                        id bigserial PRIMARY KEY,
                        vacancy_id bigint NOT NULL REFERENCES recruitment_vacancy(id) ON DELETE CASCADE,
                        member_id uuid NOT NULL REFERENCES accounts_user(id) ON DELETE CASCADE,
                        appointed_by_id uuid REFERENCES accounts_user(id) ON DELETE SET NULL,
                        appointed_at timestamptz NOT NULL DEFAULT NOW(),
                        is_active boolean NOT NULL DEFAULT true,
                        scores_submitted boolean NOT NULL DEFAULT false,
                        scores_submitted_at timestamptz,
                        picks_submitted boolean NOT NULL DEFAULT false,
                        picks_submitted_at timestamptz,
                        UNIQUE (vacancy_id, member_id)
                    );
                """, migrations.RunSQL.noop),

                migrations.RunSQL("""
                    CREATE TABLE IF NOT EXISTS recruitment_committeescore (
                        id bigserial PRIMARY KEY,
                        vacancy_id bigint NOT NULL REFERENCES recruitment_vacancy(id) ON DELETE CASCADE,
                        application_id bigint NOT NULL REFERENCES recruitment_jobapplication(id) ON DELETE CASCADE,
                        member_id uuid NOT NULL REFERENCES accounts_user(id) ON DELETE CASCADE,
                        score smallint NOT NULL,
                        comment text NOT NULL,
                        is_draft boolean NOT NULL DEFAULT true,
                        submitted boolean NOT NULL DEFAULT false,
                        created_at timestamptz NOT NULL DEFAULT NOW(),
                        submitted_at timestamptz,
                        updated_at timestamptz NOT NULL DEFAULT NOW(),
                        UNIQUE (vacancy_id, application_id, member_id)
                    );
                """, migrations.RunSQL.noop),

                migrations.RunSQL("""
                    CREATE TABLE IF NOT EXISTS recruitment_committeescoreamendment (
                        id bigserial PRIMARY KEY,
                        score_id bigint NOT NULL REFERENCES recruitment_committeescore(id) ON DELETE CASCADE,
                        old_score smallint NOT NULL,
                        new_score smallint NOT NULL,
                        old_comment text NOT NULL,
                        new_comment text NOT NULL,
                        reason text NOT NULL,
                        amended_by_id uuid REFERENCES accounts_user(id) ON DELETE SET NULL,
                        amended_at timestamptz NOT NULL DEFAULT NOW()
                    );
                """, migrations.RunSQL.noop),

                migrations.RunSQL("""
                    CREATE TABLE IF NOT EXISTS recruitment_shortlistpick (
                        id bigserial PRIMARY KEY,
                        vacancy_id bigint NOT NULL REFERENCES recruitment_vacancy(id) ON DELETE CASCADE,
                        application_id bigint NOT NULL REFERENCES recruitment_jobapplication(id) ON DELETE CASCADE,
                        member_id uuid NOT NULL REFERENCES accounts_user(id) ON DELETE CASCADE,
                        include boolean NOT NULL,
                        reason text NOT NULL,
                        decided_at timestamptz NOT NULL DEFAULT NOW(),
                        UNIQUE (vacancy_id, application_id, member_id)
                    );
                """, migrations.RunSQL.noop),

                migrations.RunSQL("""
                    CREATE TABLE IF NOT EXISTS recruitment_shortlistconsent (
                        id bigserial PRIMARY KEY,
                        vacancy_id bigint NOT NULL REFERENCES recruitment_vacancy(id) ON DELETE CASCADE,
                        member_id uuid NOT NULL REFERENCES accounts_user(id) ON DELETE CASCADE,
                        response varchar(20) NOT NULL DEFAULT 'no_response',
                        dissent_reason text NOT NULL DEFAULT '',
                        responded_at timestamptz,
                        UNIQUE (vacancy_id, member_id)
                    );
                """, migrations.RunSQL.noop),

                migrations.RunSQL("""
                    CREATE TABLE IF NOT EXISTS recruitment_shortlistlog (
                        id bigserial PRIMARY KEY,
                        vacancy_id bigint NOT NULL REFERENCES recruitment_vacancy(id) ON DELETE CASCADE,
                        application_id bigint REFERENCES recruitment_jobapplication(id) ON DELETE SET NULL,
                        performed_by_id uuid REFERENCES accounts_user(id) ON DELETE SET NULL,
                        action varchar(50) NOT NULL,
                        notes text NOT NULL DEFAULT '',
                        metadata jsonb NOT NULL DEFAULT '{}',
                        timestamp timestamptz NOT NULL DEFAULT NOW(),
                        performed_by_label varchar(200) NOT NULL DEFAULT ''
                    );
                """, migrations.RunSQL.noop),

                migrations.RunSQL(
                    "ALTER TABLE recruitment_vacancy ADD COLUMN IF NOT EXISTS committee_appointed_at timestamptz;",
                    migrations.RunSQL.noop
                ),

                migrations.RunSQL(
                    "ALTER TABLE recruitment_vacancy ADD COLUMN IF NOT EXISTS shortlist_finalised_at timestamptz;",
                    migrations.RunSQL.noop
                ),

                migrations.RunSQL(
                    "ALTER TABLE recruitment_vacancy ADD COLUMN IF NOT EXISTS shortlist_finalised_by_id uuid REFERENCES accounts_user(id) ON DELETE SET NULL;",
                    migrations.RunSQL.noop
                ),

                migrations.RunSQL(
                    "ALTER TABLE recruitment_vacancy ADD COLUMN IF NOT EXISTS is_overdue boolean NOT NULL DEFAULT false;",
                    migrations.RunSQL.noop
                ),
            ],
        ),
    ]