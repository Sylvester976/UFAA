from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone
from django.conf import settings


class Migration(migrations.Migration):
    """
    Replaces the scoring/picks/consent approach with a simpler
    approve/disapprove vote model agreed in design session.

    Drops:
        - recruitment_committeescore
        - recruitment_committeescoreamendment
        - recruitment_shortlistpick
        - recruitment_shortlistconsent

    Creates:
        - recruitment_committeevote   (approve/disapprove + mandatory comment)
        - recruitment_shortlistresult (computed outcome per applicant)

    Updates ShortlistingCommittee:
        - renames scores_submitted  → votes_submitted
        - renames scores_submitted_at → votes_submitted_at
        - drops picks_submitted, picks_submitted_at
    """

    dependencies = [
        ('recruitment', '0049_remove_document_membership'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [

        # ── 1. State + DB: drop old tables ───────────────────────────────
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.DeleteModel('CommitteeScore'),
                migrations.DeleteModel('CommitteeScoreAmendment'),
                migrations.DeleteModel('ShortlistPick'),
                migrations.DeleteModel('ShortlistConsent'),
            ],
            database_operations=[
                migrations.RunSQL(
                    "DROP TABLE IF EXISTS recruitment_committeescoreamendment CASCADE;",
                    migrations.RunSQL.noop,
                ),
                migrations.RunSQL(
                    "DROP TABLE IF EXISTS recruitment_committeescore CASCADE;",
                    migrations.RunSQL.noop,
                ),
                migrations.RunSQL(
                    "DROP TABLE IF EXISTS recruitment_shortlistpick CASCADE;",
                    migrations.RunSQL.noop,
                ),
                migrations.RunSQL(
                    "DROP TABLE IF EXISTS recruitment_shortlistconsent CASCADE;",
                    migrations.RunSQL.noop,
                ),
            ],
        ),

        # ── 2. Update ShortlistingCommittee fields ────────────────────────
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RemoveField('ShortlistingCommittee', 'scores_submitted'),
                migrations.RemoveField('ShortlistingCommittee', 'scores_submitted_at'),
                migrations.RemoveField('ShortlistingCommittee', 'picks_submitted'),
                migrations.RemoveField('ShortlistingCommittee', 'picks_submitted_at'),
                migrations.AddField(
                    model_name='ShortlistingCommittee',
                    name='votes_submitted',
                    field=models.BooleanField(default=False),
                ),
                migrations.AddField(
                    model_name='ShortlistingCommittee',
                    name='votes_submitted_at',
                    field=models.DateTimeField(null=True, blank=True),
                ),
                migrations.AddField(
                    model_name='ShortlistingCommittee',
                    name='acknowledged',
                    field=models.BooleanField(default=False),
                    preserve_default=False,
                ),
                migrations.AddField(
                    model_name='ShortlistingCommittee',
                    name='acknowledged_at',
                    field=models.DateTimeField(null=True, blank=True),
                ),
            ],
            database_operations=[
                # Drop old columns
                migrations.RunSQL(
                    "ALTER TABLE recruitment_shortlistingcommittee DROP COLUMN IF EXISTS scores_submitted;",
                    migrations.RunSQL.noop,
                ),
                migrations.RunSQL(
                    "ALTER TABLE recruitment_shortlistingcommittee DROP COLUMN IF EXISTS scores_submitted_at;",
                    migrations.RunSQL.noop,
                ),
                migrations.RunSQL(
                    "ALTER TABLE recruitment_shortlistingcommittee DROP COLUMN IF EXISTS picks_submitted;",
                    migrations.RunSQL.noop,
                ),
                migrations.RunSQL(
                    "ALTER TABLE recruitment_shortlistingcommittee DROP COLUMN IF EXISTS picks_submitted_at;",
                    migrations.RunSQL.noop,
                ),
                # Add new columns
                migrations.RunSQL(
                    "ALTER TABLE recruitment_shortlistingcommittee ADD COLUMN IF NOT EXISTS votes_submitted boolean NOT NULL DEFAULT false;",
                    migrations.RunSQL.noop,
                ),
                migrations.RunSQL(
                    "ALTER TABLE recruitment_shortlistingcommittee ADD COLUMN IF NOT EXISTS votes_submitted_at timestamptz;",
                    migrations.RunSQL.noop,
                ),
                migrations.RunSQL(
                    "ALTER TABLE recruitment_shortlistingcommittee ADD COLUMN IF NOT EXISTS acknowledged boolean NOT NULL DEFAULT false;",
                    migrations.RunSQL.noop,
                ),
                migrations.RunSQL(
                    "ALTER TABLE recruitment_shortlistingcommittee ADD COLUMN IF NOT EXISTS acknowledged_at timestamptz;",
                    migrations.RunSQL.noop,
                ),
            ],
        ),

        # ── 3. Create CommitteeVote ───────────────────────────────────────
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.CreateModel(
                    name='CommitteeVote',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True)),
                        ('vacancy', models.ForeignKey(
                            'recruitment.Vacancy',
                            on_delete=django.db.models.deletion.CASCADE,
                            related_name='committee_votes',
                        )),
                        ('application', models.ForeignKey(
                            'recruitment.JobApplication',
                            on_delete=django.db.models.deletion.CASCADE,
                            related_name='committee_votes',
                        )),
                        ('member', models.ForeignKey(
                            settings.AUTH_USER_MODEL,
                            on_delete=django.db.models.deletion.CASCADE,
                            related_name='committee_votes_cast',
                        )),
                        # True = Approve, False = Disapprove
                        ('approve', models.BooleanField()),
                        # Mandatory — enforced at view level
                        ('comment', models.TextField()),
                        ('voted_at', models.DateTimeField(default=django.utils.timezone.now)),
                        # Allows saving a draft before final submission
                        ('is_draft', models.BooleanField(default=True)),
                        ('submitted_at', models.DateTimeField(null=True, blank=True)),
                    ],
                    options={
                        'unique_together': {('vacancy', 'application', 'member')},
                        'ordering': ['voted_at'],
                    },
                ),
            ],
            database_operations=[
                migrations.RunSQL("""
                    CREATE TABLE IF NOT EXISTS recruitment_committeevote (
                        id            bigserial PRIMARY KEY,
                        vacancy_id    bigint      NOT NULL REFERENCES recruitment_vacancy(id) ON DELETE CASCADE,
                        application_id bigint     NOT NULL REFERENCES recruitment_jobapplication(id) ON DELETE CASCADE,
                        member_id     uuid     NOT NULL REFERENCES accounts_user(id) ON DELETE CASCADE,
                        approve       boolean     NOT NULL,
                        comment       text        NOT NULL DEFAULT '',
                        voted_at      timestamptz NOT NULL DEFAULT NOW(),
                        is_draft      boolean     NOT NULL DEFAULT true,
                        submitted_at  timestamptz,
                        UNIQUE (vacancy_id, application_id, member_id)
                    );
                """, migrations.RunSQL.noop),
            ],
        ),

        # ── 4. Create ShortlistResult ─────────────────────────────────────
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.CreateModel(
                    name='ShortlistResult',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True)),
                        ('vacancy', models.ForeignKey(
                            'recruitment.Vacancy',
                            on_delete=django.db.models.deletion.CASCADE,
                            related_name='shortlist_results',
                        )),
                        ('application', models.ForeignKey(
                            'recruitment.JobApplication',
                            on_delete=django.db.models.deletion.CASCADE,
                            related_name='shortlist_result',
                        )),
                        ('total_votes',   models.PositiveSmallIntegerField(default=0)),
                        ('approve_count', models.PositiveSmallIntegerField(default=0)),
                        ('reject_count',  models.PositiveSmallIntegerField(default=0)),
                        ('threshold',     models.PositiveSmallIntegerField(default=0)),
                        # True = shortlisted, False = not shortlisted
                        ('shortlisted',   models.BooleanField()),
                        ('computed_at',   models.DateTimeField(default=django.utils.timezone.now)),
                    ],
                    options={
                        'unique_together': {('vacancy', 'application')},
                        'ordering': ['-approve_count'],
                    },
                ),
            ],
            database_operations=[
                migrations.RunSQL("""
                    CREATE TABLE IF NOT EXISTS recruitment_shortlistresult (
                        id             bigserial PRIMARY KEY,
                        vacancy_id     bigint  NOT NULL REFERENCES recruitment_vacancy(id) ON DELETE CASCADE,
                        application_id bigint  NOT NULL REFERENCES recruitment_jobapplication(id) ON DELETE CASCADE,
                        total_votes    smallint NOT NULL DEFAULT 0,
                        approve_count  smallint NOT NULL DEFAULT 0,
                        reject_count   smallint NOT NULL DEFAULT 0,
                        threshold      smallint NOT NULL DEFAULT 0,
                        shortlisted    boolean  NOT NULL,
                        computed_at    timestamptz NOT NULL DEFAULT NOW(),
                        UNIQUE (vacancy_id, application_id)
                    );
                """, migrations.RunSQL.noop),
            ],
        ),

    ]
