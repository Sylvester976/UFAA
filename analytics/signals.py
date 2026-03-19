"""
analytics/signals.py
====================
Watches for Vacancy status changes and rebuilds the snapshot
for that one vacancy automatically.

Wired up in analytics/apps.py via ready().
"""

import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)

# Stages that are meaningful enough to warrant a snapshot rebuild.
# Deliberately excludes 'draft' and 'open' — no applications yet,
# nothing to snapshot.
SNAPSHOT_TRIGGERS = {
    'closed',
    'longlisting',
    'committee_stage',
    'shortlisting',
    'interview_scheduling',
    'interviews',
    'ceo_review',
    'ceo_approved',
    'appointed',
}


@receiver(post_save, sender='recruitment.Vacancy')
def auto_refresh_vacancy_snapshot(sender, instance, created, **kwargs):
    """
    Rebuild analytics snapshot whenever a vacancy reaches a pipeline stage.

    - Only fires on UPDATE (not INSERT) — a newly created vacancy
      has no applications yet so there's nothing to snapshot.
    - Non-fatal: a snapshot failure never crashes the request.
    - Import is inside the function to avoid circular imports at startup.
    """
    if created:
        return

    if instance.status not in SNAPSHOT_TRIGGERS:
        return

    try:
        from analytics.utils import build_snapshot
        build_snapshot(instance)
    except Exception as e:
        # Log but never propagate — snapshot is supplementary, not critical
        logger.error(
            f"auto_refresh_vacancy_snapshot failed for vacancy "
            f"{instance.id} ({instance.reference_number}): {e}",
            exc_info=True,
        )