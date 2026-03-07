"""
0044_recreate_committee_tables.py

Migration 0040 used hardcoded SQL with accounts_systemaccount as the FK target.
Some tables were partially created (missing FK columns) and 0043 skipped them
because they appeared to exist.

This migration drops all 6 committee tables unconditionally and recreates them
using schema_editor, which resolves FK targets from the actual model definitions.

Safe to run: no production data exists in these tables yet.
"""

from django.db import migrations


COMMITTEE_TABLES = [
    # Drop in reverse FK dependency order
    'recruitment_committeescoreamendment',
    'recruitment_committeescore',
    'recruitment_shortlistpick',
    'recruitment_shortlistconsent',
    'recruitment_shortlistlog',
    'recruitment_shortlistingcommittee',
]

COMMITTEE_MODELS = [
    # Recreate in FK dependency order
    'ShortlistingCommittee',
    'CommitteeScore',
    'CommitteeScoreAmendment',
    'ShortlistPick',
    'ShortlistConsent',
    'ShortlistLog',
]


def recreate_committee_tables(apps, schema_editor):
    # Step 1: Drop all committee tables (CASCADE handles any leftover FK deps)
    with schema_editor.connection.cursor() as cursor:
        for table in COMMITTEE_TABLES:
            cursor.execute(f'DROP TABLE IF EXISTS "{table}" CASCADE;')
            print(f"  Dropped (if existed): {table}")

    # Step 2: Recreate using schema_editor — FKs resolved from real models
    for model_name in COMMITTEE_MODELS:
        model = apps.get_model('recruitment', model_name)
        schema_editor.create_model(model)
        print(f"  Created: {model._meta.db_table}")


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('recruitment', '0043_create_committee_tables'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[],   # models already in state from 0040
            database_operations=[
                migrations.RunPython(recreate_committee_tables, reverse_code=noop),
            ],
        ),
    ]
