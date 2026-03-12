from django.urls import path

from . import views

urlpatterns = [
    path('dashboard/', views.dashboard, name='dashboard'),

    path("profile/", views.profile_view, name="profile"),
    path("academic/", views.academic_qualifications_view, name="academic_qualifications"),
    path("professional/", views.professional_qualifications_view, name="professional_qualifications"),
    path("work-history/", views.work_history_view, name="work_history"),
    path('memberships/', views.memberships_view, name='memberships'),
    path('referees/', views.referee_view, name='referees'),
    path("additional/", views.additional_details_view, name="additional_details"),
    path("jobs/", views.view_jobs, name="view_jobs"),
    path("instrutions/", views.view_jobs, name="view_jobs"),
    path('apply-jobs/', views.apply_jobs_view, name='apply_jobs'),
    path('job-status/', views.job_status_view, name='job_status'),
    path('notifications/read/', views.mark_notification_read_view, name='mark_notification_read'),
    path('notifications/poll/', views.notification_poll_view, name='notification_poll'),
    # HR DASHBOARD
    path('hr/instructions/', views.instrutions_view, name='instrutions_view'),
    path('hr/dashboard/', views.hr_dashboard, name='hr_dashboard'),

    path("admin/dashboard/", views.admin_dashboard, name="admin_dashboard"),
    # Vacancy management
    path('hr/vacancy/create/', views.create_vacancy, name='create_vacancy'),
    path('hr/vacancy/<int:vacancy_id>/edit/', views.update_vacancy, name='update_vacancy'),
    path('hr/vacancy/<int:vacancy_id>/delete/', views.delete_vacancy, name='delete_vacancy'),
    path('hr/vacancy/<int:vacancy_id>/publish/', views.publish_vacancy, name='publish_vacancy'),
    path('vacancy/<int:vacancy_id>/download/', views.download_vacancy_pdf, name='download_vacancy_pdf'),

    # Applications review
    path('hr/vacancy/<int:vacancy_id>/applications/',
         views.hr_view_applications,
         name='hr_view_applications'),
    path('hr/vacancy/<int:vacancy_id>/applications/json/',
         views.hr_view_applications_json,
         name='hr_applications_json'),

    path('hr/vacancy/<int:vacancy_id>/committee/',
         views.committee_view_applications,
         name='committee_view_applications'),

    path('hr/vacancy/<int:vacancy_id>/start-longlisting/',
         views.start_longlisting,
         name='start_longlisting'),

    path('hr/vacancy/<int:vacancy_id>/shortlist/',
         views.shortlist_candidates,
         name='shortlist_candidates'),
    # Applicant Area
    path('vacancy/<int:vacancy_id>/', views.vacancy_detail, name='vacancy_detail'),
    path('vacancy/<int:vacancy_id>/apply/', views.apply_for_vacancy, name='apply_for_vacancy'),
    # opening/closing vacancies
    path('vacancies/<int:vacancy_id>/open/', views.open_vacancy, name='open_vacancy'),
    path('vacancies/<int:vacancy_id>/close/', views.close_vacancy, name='close_vacancy'),
    path('hr/vacancy/<int:vacancy_id>/ranking/',
         views.hr_ranking_view,
         name='hr_ranking_view'),

    path('hr/vacancy/<int:vacancy_id>/select-top-three/',
         views.select_top_three,
         name='select_top_three'),

    path('ceo/vacancy/<int:vacancy_id>/review/',
         views.ceo_review_view,
         name='ceo_review_view'),

    path('ceo/vacancy/<int:vacancy_id>/select/<int:application_id>/',
         views.ceo_select_candidate,
         name='ceo_select_candidate'),

    path('hr/vacancy/<int:vacancy_id>/finalize/',
         views.hr_finalize_appointment,
         name='hr_finalize_appointment'),

    path(
        'ceo/dashboard/',
        views.ceo_dashboard,
        name='ceo_dashboard'
    ),

    path(
        'ceo/vacancy/<int:vacancy_id>/review/',
        views.ceo_review_view,
        name='ceo_review'
    ),

    path(
        'ceo/vacancy/<int:vacancy_id>/approve/',
        views.ceo_approve,
        name='ceo_approve'
    ),

    path(
        'ceo/vacancy/<int:vacancy_id>/select/<int:application_id>/',
        views.ceo_select_candidate,
        name='ceo_select_candidate'
    ),

    path(
        "hr/application/<int:application_id>/",
        views.application_detail,
        name="application_detail"
    ),

    path('vacancies/longlisting/', views.vacancy_longlisting, name='vacancy_longlisting'),
    path('vacancies/list/', views.vacancy_list, name='vacancy_list'),
    path('hr/vacancy/<int:vacancy_id>/longlisting/', views.move_to_longlisting, name='move_to_longlisting'),
    path('vacancies/appointments/', views.vacancy_appointments, name='vacancy_appointments'),
    path('hr/vacancy/<int:vacancy_id>/longlist/',
         views.hr_longlist_dashboard, name='hr_longlist_dashboard'),
    path('hr/vacancy/<int:vacancy_id>/longlist/<int:app_id>/',
         views.hr_longlist_dossier, name='hr_longlist_dossier'),
    path('hr/vacancy/<int:vacancy_id>/longlist/<int:app_id>/decision/',
         views.hr_longlist_decision, name='hr_longlist_decision'),
    path('hr/vacancy/<int:vacancy_id>/longlist/bulk/',
         views.hr_longlist_bulk, name='hr_longlist_bulk'),
    path('hr/vacancy/<int:vacancy_id>/longlist/<int:app_id>/recall/',
         views.hr_longlist_recall, name='hr_longlist_recall'),
    path('hr/vacancy/<int:vacancy_id>/longlist/finalise/',
         views.hr_longlist_finalise, name='hr_longlist_finalise'),
    path('vacancies/shortlisting/',
         views.vacancy_shortlisting,
         name='vacancy_shortlisting'),

    path('hr/vacancy/<int:vacancy_id>/committee/appoint/',
         views.hr_appoint_committee,
         name='hr_appoint_committee'),

    path('hr/vacancy/<int:vacancy_id>/committee/appoint/add/',
         views.hr_committee_add,
         name='hr_committee_add'),

    path('hr/vacancy/<int:vacancy_id>/committee/appoint/remove/',
         views.hr_committee_remove,
         name='hr_committee_remove'),

    path('hr/vacancy/<int:vacancy_id>/committee/appoint/notify/',
         views.hr_committee_notify,
         name='hr_committee_notify'),

    path('hr/vacancy/<int:vacancy_id>/committee/staff-search/',
         views.hr_committee_staff_search,
         name='hr_committee_staff_search'),

    path('hr/vacancy/<int:vacancy_id>/committee/progress/',
         views.hr_committee_progress,
         name='hr_committee_progress'),
    path('hr/vacancy/<int:vacancy_id>/committee/shortlist/', views.hr_shortlist_review, name='hr_shortlist_review'),
    path('hr/vacancy/<int:vacancy_id>/committee/shortlist/override/', views.hr_shortlist_override,
         name='hr_shortlist_override'),
    path('hr/vacancy/<int:vacancy_id>/committee/shortlist/finalise/', views.hr_shortlist_finalise,
         name='hr_shortlist_finalise'),
    path('profile/document/<int:doc_id>/delete/', views.delete_document, name='delete_document'),

    # comitee urls
    path('committee/dashboard/', views.committee_dashboard, name='committee_dashboard'),
    path('committee/vacancy/<int:vacancy_id>/acknowledge/', views.committee_acknowledge, name='committee_acknowledge'),
    path('committee/vacancy/<int:vacancy_id>/review/', views.committee_review, name='committee_review'),
    path('committee/vacancy/<int:vacancy_id>/vote/', views.committee_vote_save, name='committee_vote_save'),
    path('committee/vacancy/<int:vacancy_id>/submit/', views.committee_submit_all, name='committee_submit_all'),
    path('committee/vacancy/<int:vacancy_id>/results/', views.committee_results, name='committee_results'),
    path('committee/vacancy/<int:vacancy_id>/coi/', views.committee_declare_coi, name='committee_declare_coi'),

    # ── HR interview URLs ──────────────────────────────────────────────────────────────────
    path('hr/vacancy/interviews/', views.vacancy_interviews, name='vacancy_interviews'),
    path('hr/vacancy/<int:vacancy_id>/interview/', views.hr_interview_setup, name='hr_interview_setup'),
    path('hr/vacancy/<int:vacancy_id>/interview/panel/add/', views.hr_panel_add, name='hr_panel_add'),
    path('hr/vacancy/<int:vacancy_id>/interview/panel/remove/', views.hr_panel_remove, name='hr_panel_remove'),
    path('hr/vacancy/<int:vacancy_id>/interview/panel/notify/', views.hr_panel_notify, name='hr_panel_notify'),
    path('hr/vacancy/<int:vacancy_id>/interview/panel/search/', views.hr_panel_staff_search,
         name='hr_panel_staff_search'),
    path('hr/vacancy/<int:vacancy_id>/interview/criteria/save/', views.hr_criteria_save, name='hr_criteria_save'),
    path('hr/vacancy/<int:vacancy_id>/interview/slots/save/', views.hr_slots_save, name='hr_slots_save'),
    path('hr/vacancy/<int:vacancy_id>/interview/notify/', views.hr_interview_notify, name='hr_interview_notify'),
    path('hr/vacancy/<int:vacancy_id>/interview/progress/', views.hr_interview_progress, name='hr_interview_progress'),
    path('hr/vacancy/<int:vacancy_id>/interview/results/', views.hr_interview_results, name='hr_interview_results'),

    # ── Panel member URLs ─────────────────────────────────────────────────────────
    path('panel/dashboard/', views.panel_dashboard, name='panel_dashboard'),
    path('panel/vacancy/<int:vacancy_id>/acknowledge/', views.panel_acknowledge, name='panel_acknowledge'),
    path('panel/vacancy/<int:vacancy_id>/coi/', views.panel_declare_coi, name='panel_declare_coi'),
    path('panel/vacancy/<int:vacancy_id>/score/', views.panel_score, name='panel_score'),
    path('panel/vacancy/<int:vacancy_id>/score/save/', views.panel_score_save, name='panel_score_save'),
    path('panel/vacancy/<int:vacancy_id>/score/submit-all/', views.panel_submit_all, name='panel_submit_all'),
    path('panel/vacancy/<int:vacancy_id>/results/', views.panel_results, name='panel_results'),
    # ─────────────────────────────────────────────────────────────────────────────

]
