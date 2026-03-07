"""
0043_create_committee_tables.py

Migration 0040 registered the committee models in Django's ORM state but
its raw SQL used hardcoded table names for the FK targets which may not
match your actual auth user table — so the CREATE TABLE statements failed
silently, leaving the ORM state out of sync with the real DB.

This migration creates any of the 6 committee tables that are missing,
using schema_editor so FK references are resolved from the actual models
(no hardcoded table names).

State operations are empty because the models are already registered
in Django's state from 0040.
"""

from django.db import migrations


def create_missing_committee_tables(apps, schema_editor):
    """
    For each committee model, check if the physical table exists.
    If not, create it using schema_editor (which resolves FKs properly).
    """
    model_names = [
        'ShortlistingCommittee',
        'CommitteeScore',
        'CommitteeScoreAmendment',
        'ShortlistPick',
        'ShortlistConsent',
        'ShortlistLog',
    ]

    with schema_editor.connection.cursor() as cursor:
        for model_name in model_names:
            model = apps.get_model('recruitment', model_name)
            table  = model._meta.db_table

            # Check if table already exists in the DB
            cursor.execute(
                """
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.tables
                    WHERE table_schema = 'public'
                      AND table_name   = %s
                )
                """,
                [table],
            )
            exists = cursor.fetchone()[0]

            if not exists:
                schema_editor.create_model(model)
                print(f"  Created table: {table}")
            else:
                print(f"  Already exists: {table} (skipped)")


class Migration(migrations.Migration):

    dependencies = [
        ('recruitment', '0042_fix_status_ordering'),
    ]

    operations = [
        # state_operations is empty — models already in state from 0040.
        # database_operations creates the physical tables that 0040 missed.
        migrations.SeparateDatabaseAndState(
            state_operations=[],
            database_operations=[
                migrations.RunPython(
                    create_missing_committee_tables,
                    reverse_code=migrations.RunPython.noop,
                ),
            ],
        ),
    ]
