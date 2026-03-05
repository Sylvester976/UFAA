from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('recruitment', '0032_alter_vacancy_advert_pdf_and_more'),
    ]

    operations = [

        # ── 1. EducationLevel — add level integer ─────────────────────
        migrations.AddField(
            model_name='educationlevel',
            name='level',
            field=models.PositiveIntegerField(
                default=0,
                help_text='Hierarchy integer — higher = more qualified. Not unique — equivalent quals share the same level.'
            ),
        ),

        # Populate level values for existing rows
        migrations.RunSQL(
            sql="""
                UPDATE recruitment_educationlevel SET level = CASE name
                    WHEN 'Kenya Certificate of Primary Education (KCPE)' THEN 1
                    WHEN 'Kenya Certificate of Secondary Education (KCSE)' THEN 2
                    WHEN 'O-Levels (British System)'                      THEN 2
                    WHEN 'IGCSE'                                          THEN 2
                    WHEN 'GED (American System)'                          THEN 2
                    WHEN 'A-Levels (British System)'                      THEN 3
                    WHEN 'International Baccalaureate (IB)'               THEN 3
                    WHEN 'Certificate'                                     THEN 4
                    WHEN 'Diploma'                                         THEN 5
                    WHEN 'Higher National Diploma (HND)'                  THEN 6
                    WHEN 'Bachelor''s Degree'                             THEN 7
                    WHEN 'Masters Degree'                                  THEN 9
                    WHEN 'PhD / Doctorate'                                 THEN 10
                    WHEN 'Other Foreign Qualification'                     THEN 11
                    ELSE 0
                END
                WHERE level = 0;
            """,
            reverse_sql=migrations.RunSQL.noop,
        ),

        # level is NOT unique — equivalent qualifications share the same level.
        # e.g. KCSE, O-Levels, IGCSE, GED are all level 2.
        # Screening uses >= comparison so ties work correctly.
        migrations.AlterField(
            model_name='educationlevel',
            name='level',
            field=models.PositiveIntegerField(
                default=0,
                help_text=(
                    'Hierarchy integer — higher = more qualified. '
                    'Equivalent qualifications share the same level. '
                    '1=KCPE, 2=KCSE/O-Levels/IGCSE/GED, '
                    '3=A-Levels/IB, 4=Certificate, 5=Diploma, '
                    '6=HND, 7=Degree, 9=Masters, 10=PhD, '
                    '11=Other Foreign (soft flag).'
                ),
            ),
        ),

        # ── 2. Vacancy — add screening_criteria ──────────────────────
        migrations.AddField(
            model_name='vacancy',
            name='screening_criteria',
            field=models.JSONField(
                default=dict,
                blank=True,
                help_text=(
                    'Screening rules defined at vacancy creation. '
                    'Keys: require_cv, require_cover_letter, '
                    'minimum_education_level, require_academic_cert, '
                    'require_professional_qualification, '
                    'minimum_experience_years, check_salary, salary_max, '
                    'check_availability, maximum_notice_days.'
                ),
            ),
        ),

        # ── 3a. JobApplication — screening fields ────────────────────
        migrations.AddField(
            model_name='jobapplication',
            name='screening_passed',
            field=models.BooleanField(
                null=True, blank=True,
                help_text='null=not yet screened, True=passed, False=failed.'
            ),
        ),
        migrations.AddField(
            model_name='jobapplication',
            name='screening_reasons',
            field=models.JSONField(
                default=list,
                help_text=(
                    'Hard fail reasons — INTERNAL ONLY. '
                    'Never shown to applicant. '
                    'Stored for audit and committee review only.'
                ),
            ),
        ),
        migrations.AddField(
            model_name='jobapplication',
            name='screening_flags',
            field=models.JSONField(
                default=list,
                help_text=(
                    'Soft flag warnings — applicant longlisted but '
                    'committee should verify these items manually.'
                ),
            ),
        ),
        migrations.AddField(
            model_name='jobapplication',
            name='screening_ran_at',
            field=models.DateTimeField(null=True, blank=True),
        ),

        # ── 3b. JobApplication — assignment fields ───────────────────
        migrations.AddField(
            model_name='jobapplication',
            name='assigned_to',
            field=models.ForeignKey(
                to=settings.AUTH_USER_MODEL,
                on_delete=django.db.models.deletion.SET_NULL,
                null=True, blank=True,
                related_name='assigned_applications',
            ),
        ),
        migrations.AddField(
            model_name='jobapplication',
            name='assigned_by',
            field=models.ForeignKey(
                to=settings.AUTH_USER_MODEL,
                on_delete=django.db.models.deletion.SET_NULL,
                null=True, blank=True,
                related_name='assignments_made',
            ),
        ),
        migrations.AddField(
            model_name='jobapplication',
            name='assigned_at',
            field=models.DateTimeField(null=True, blank=True),
        ),

        # ── 3c. JobApplication — longlist decision fields ────────────
        migrations.AddField(
            model_name='jobapplication',
            name='longlist_decision',
            field=models.CharField(
                max_length=20,
                choices=[
                    ('shortlisted', 'Shortlisted'),
                    ('rejected',    'Rejected'),
                    ('hold',        'Hold'),
                ],
                null=True, blank=True,
            ),
        ),
        migrations.AddField(
            model_name='jobapplication',
            name='longlist_decision_by',
            field=models.ForeignKey(
                to=settings.AUTH_USER_MODEL,
                on_delete=django.db.models.deletion.SET_NULL,
                null=True, blank=True,
                related_name='longlist_decisions',
            ),
        ),
        migrations.AddField(
            model_name='jobapplication',
            name='longlist_decision_at',
            field=models.DateTimeField(null=True, blank=True),
        ),
        migrations.AddField(
            model_name='jobapplication',
            name='longlist_notes',
            field=models.TextField(blank=True),
        ),

        # ── 4. LonglistReviewLog — new model ─────────────────────────
        migrations.CreateModel(
            name='LonglistReviewLog',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True,
                    serialize=False, verbose_name='ID'
                )),
                ('action', models.CharField(
                    max_length=30,
                    choices=[
                        ('viewed',          'Viewed Application'),
                        ('shortlisted',     'Marked Shortlist'),
                        ('rejected',        'Marked Reject'),
                        ('held',            'Marked Hold'),
                        ('override',        'Override System Decision'),
                        ('assigned',        'Assigned to Officer'),
                        ('bulk_shortlist',  'Bulk Shortlist'),
                        ('bulk_reject',     'Bulk Reject'),
                        ('bulk_assign',     'Bulk Assign'),
                        ('note_added',      'Added Note'),
                        ('decision_changed','Decision Changed'),
                    ],
                )),
                ('notes',       models.TextField(blank=True)),
                ('metadata',    models.JSONField(default=dict)),
                ('actioned_at', models.DateTimeField(auto_now_add=True)),
                ('vacancy', models.ForeignKey(
                    to='recruitment.vacancy',
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='longlist_logs',
                )),
                ('application', models.ForeignKey(
                    to='recruitment.jobapplication',
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='longlist_logs',
                    null=True, blank=True,
                )),
                ('officer', models.ForeignKey(
                    to=settings.AUTH_USER_MODEL,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='longlist_logs',
                    null=True, blank=True,
                )),
            ],
            options={
                'ordering': ['-actioned_at'],
            },
        ),
    ]