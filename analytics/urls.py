"""
analytics/urls.py
=================
All analytics and report URLs.

In your main urls.py (UFAA/urls.py or project/urls.py), add:

    path('recruitment/analytics/', include('analytics.urls')),

or if your recruitment app already has a prefix:

    path('', include('analytics.urls')),

inside the recruitment include block.
"""

from django.urls import path
from analytics import views_analytics, views_reports

app_name = 'analytics'

urlpatterns = [

    # ── Analytics dashboards ──────────────────────────────────────────────────
    path('hr/',
         views_analytics.hr_analytics_dashboard,
         name='hr_analytics'),

    path('hr/vacancy/<int:vacancy_id>/',
         views_analytics.hr_vacancy_analytics,
         name='hr_vacancy_analytics'),

    path('hr/refresh/',
         views_analytics.hr_analytics_refresh,
         name='hr_analytics_refresh'),

    path('ceo/',
         views_analytics.ceo_analytics_dashboard,
         name='ceo_analytics'),

    path('committee/',
         views_analytics.committee_analytics_dashboard,
         name='committee_analytics'),

    path('panel/',
         views_analytics.panel_analytics_dashboard,
         name='panel_analytics'),

    path('auditor/',
         views_analytics.auditor_analytics_dashboard,
         name='auditor_analytics'),

    path('auditor/vacancy/<int:vacancy_id>/trail/',
         views_analytics.auditor_vacancy_trail,
         name='auditor_vacancy_trail'),

    path('admin/',
         views_analytics.admin_analytics_dashboard,
         name='admin_analytics'),

    # ── Chart.js JSON endpoints ───────────────────────────────────────────────
    path('hr/chart/funnel/',
         views_analytics.hr_chart_funnel,
         name='hr_chart_funnel'),

    path('hr/chart/cycle/',
         views_analytics.hr_chart_cycle,
         name='hr_chart_cycle'),

    path('hr/chart/gender/',
         views_analytics.hr_chart_gender,
         name='hr_chart_gender'),

    path('hr/chart/county/',
         views_analytics.hr_chart_county,
         name='hr_chart_county'),

    path('hr/chart/monthly/',
         views_analytics.hr_chart_monthly,
         name='hr_chart_monthly'),

    # ── Reports index pages ───────────────────────────────────────────────────
    path('reports/hr/',
         views_reports.hr_reports_index,
         name='hr_reports_index'),

    path('reports/ceo/',
         views_reports.ceo_reports_index,
         name='ceo_reports_index'),

    path('reports/auditor/',
         views_reports.auditor_reports_index,
         name='auditor_reports_index'),

    # ── HR Reports ────────────────────────────────────────────────────────────
    path('reports/r01/',
         views_reports.report_r01_vacancy_summary,
         name='report_r01'),

    path('reports/r02/<int:vacancy_id>/',
         views_reports.report_r02_applicant_register,
         name='report_r02'),

    path('reports/r03/<int:vacancy_id>/',
         views_reports.report_r03_longlist,
         name='report_r03'),

    path('reports/r04/<int:vacancy_id>/',
         views_reports.report_r04_shortlist,
         name='report_r04'),

    path('reports/r05/<int:vacancy_id>/',
         views_reports.report_r05_interview_scores,
         name='report_r05'),

    path('reports/r06/<int:vacancy_id>/',
         views_reports.report_r06_appointment,
         name='report_r06'),

    path('reports/r07/',
         views_reports.report_r07_diversity,
         name='report_r07'),

    path('reports/r08/',
         views_reports.report_r08_pipeline_status,
         name='report_r08'),

    path('reports/r09/',
         views_reports.report_r09_overrides,
         name='report_r09'),

    path('reports/r10/<int:vacancy_id>/',
         views_reports.report_r10_committee_activity,
         name='report_r10'),

    path('reports/r11/<int:vacancy_id>/',
         views_reports.report_r11_panel_activity,
         name='report_r11'),

    # ── CEO Reports ───────────────────────────────────────────────────────────
    path('reports/r12/',
         views_reports.report_r12_ceo_decisions,
         name='report_r12'),

    path('reports/r13/<int:vacancy_id>/',
         views_reports.report_r13_top_candidates,
         name='report_r13'),

    # ── Auditor Reports ───────────────────────────────────────────────────────
    path('reports/r14/<int:vacancy_id>/',
         views_reports.report_r14_full_audit_trail,
         name='report_r14'),

    path('reports/r15/',
         views_reports.report_r15_status_change_log,
         name='report_r15'),

    path('reports/r16/',
         views_reports.report_r16_override_audit,
         name='report_r16'),

    path('reports/r17/',
         views_reports.report_r17_coi_declarations,
         name='report_r17'),

    path('reports/r18/',
         views_reports.report_r18_user_activity,
         name='report_r18'),
]