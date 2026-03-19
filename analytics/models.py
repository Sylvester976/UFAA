from django.db import models
from django.utils import timezone


class VacancyAnalyticsSnapshot(models.Model):
    """
    Per-vacancy analytics snapshot. Rebuilt automatically via Django signal
    whenever a vacancy moves to a meaningful pipeline stage.

    Never written to directly by views — only by analytics.utils.build_snapshot().
    """
    vacancy = models.OneToOneField(
        'recruitment.Vacancy',
        on_delete=models.CASCADE,
        related_name='analytics_snapshot',
    )
    snapped_at = models.DateTimeField(default=timezone.now)

    # ── Stage counts ──────────────────────────────────────────────────────────
    total_apps       = models.IntegerField(default=0)
    longlisted       = models.IntegerField(default=0)
    final_longlisted = models.IntegerField(default=0)
    shortlisted      = models.IntegerField(default=0)
    interviewed      = models.IntegerField(default=0)
    top_candidate    = models.IntegerField(default=0)
    appointed        = models.IntegerField(default=0)
    not_selected     = models.IntegerField(default=0)

    # ── Funnel rates (%) ──────────────────────────────────────────────────────
    longlist_rate    = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    shortlist_rate   = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    interview_rate   = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    appointment_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)

    # ── Cycle times (days) ────────────────────────────────────────────────────
    days_open         = models.IntegerField(null=True, blank=True)
    days_longlisting  = models.IntegerField(null=True, blank=True)
    days_shortlisting = models.IntegerField(null=True, blank=True)
    days_interviews   = models.IntegerField(null=True, blank=True)
    days_total        = models.IntegerField(null=True, blank=True)

    # ── Interview scoring ─────────────────────────────────────────────────────
    avg_interview_score = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    max_interview_score = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    min_interview_score = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    score_std_dev       = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    ceo_selected_rank   = models.IntegerField(null=True, blank=True)
    ceo_override        = models.BooleanField(default=False)

    # ── Committee ─────────────────────────────────────────────────────────────
    committee_size            = models.IntegerField(default=0)
    committee_coi_count       = models.IntegerField(default=0)
    shortlist_override_count  = models.IntegerField(default=0)

    # ── Demographics (from frozen snapshot_basic at application time) ─────────
    gender_breakdown    = models.JSONField(default=dict)
    county_breakdown    = models.JSONField(default=dict)
    edu_level_breakdown = models.JSONField(default=dict)
    pwd_count           = models.IntegerField(default=0)

    class Meta:
        verbose_name        = 'Vacancy Analytics Snapshot'
        verbose_name_plural = 'Vacancy Analytics Snapshots'
        ordering            = ['-snapped_at']

    def __str__(self):
        return f"Snapshot — {self.vacancy} @ {self.snapped_at:%Y-%m-%d %H:%M}"