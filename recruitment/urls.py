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
    
    path(
        "panel/assignment/<int:assignment_id>/respond/",
        views.respond_panel_assignment,
        name="respond_panel_assignment",
    ),
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

    # Panel appointment
    path('hr/vacancy/<int:vacancy_id>/appoint-panel/',
         views.appoint_panelists,
         name='appoint_panelists'),

    # Applicant Area
    path('vacancy/<int:vacancy_id>/', views.vacancy_detail, name='vacancy_detail'),
    path('vacancy/<int:vacancy_id>/apply/', views.apply_for_vacancy, name='apply_for_vacancy'),
    path('vacancies/<int:vacancy_id>/panelists/', views.vacancy_panelists, name='vacancy_panelists'),
    # opening/closing vacancies
    path('vacancies/<int:vacancy_id>/open/', views.open_vacancy, name='open_vacancy'),
    path('vacancies/<int:vacancy_id>/close/', views.close_vacancy, name='close_vacancy'),

    # Panelist area
    path('panelist/dashboard/', views.panelist_dashboard, name='panelist_dashboard'),
    path('committee/dashboard/', views.shortlisting_dashboard, name='shortlisting_dashboard'),

    path('panelist/vacancy/<int:vacancy_id>/interviews/',
         views.panelist_interview_list,
         name='panelist_interview_list'),

    path('panelist/application/<int:application_id>/score/',
         views.panelist_score_candidate,
         name='panelist_score_candidate'),

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
    path('vacancies/shortlisting/', views.vacancy_shortlisting, name='vacancy_shortlisting'),
    path('vacancies/interviews/', views.vacancy_interviews, name='vacancy_interviews'),
    path('vacancies/list/', views.vacancy_list, name='vacancy_list'),
    path('hr/vacancy/<int:vacancy_id>/longlisting/', views.move_to_longlisting, name='move_to_longlisting'),
    path('vacancies/appointments/', views.vacancy_appointments, name='vacancy_appointments'),

    # Appoint panelists to a vacancy
    path('vacancies/<int:vacancy_id>/appoint-panelists/', views.appoint_panelists, name='appoint_panelists'),

    path(
        'hr/vacancy/<int:vacancy_id>/appoint-shortlisting/',
        views.appoint_shortlisting_committee,
        name='appoint_shortlisting_committee'
    ),

    # Panelist views shortlist page
    path(
        'panelist/vacancy/<int:vacancy_id>/shortlist/',
        views.submit_shortlist,
        name='submit_shortlist'
    ),

    # Templates
    path('interview-templates/', views.template_list, name='template_list'),
    path('interview-templates/create/', views.template_create, name='template_create'),
    path('interview-templates/<int:pk>/', views.template_detail, name='template_detail'),
    path('interview-templates/<int:pk>/edit/', views.template_edit, name='template_edit'),
    path('interview-templates/<int:pk>/delete/', views.template_delete, name='template_delete'),

    # Sections
    path('sections/create/<int:template_id>/', views.section_create, name='section_create'),
    path('sections/<int:pk>/edit/', views.section_edit, name='section_edit'),
    path('sections/<int:pk>/delete/', views.section_delete, name='section_delete'),

    path(
        "panelist/dashboard/",
        views.panelist_dashboard,
        name="panelist_dashboard"
    ),

    path(
        "panel/respond/<int:assignment_id>/",
        views.respond_panel_assignment,
        name="respond_panel_assignment"
    ),

    path(
        "panel/report/<int:vacancy_id>/",
        views.panelist_submit_report,
        name="panelist_submit_report"
    ),

    path(
        "panelist/reports/",
        views.panelist_reports,
        name="panelist_reports"
    ),
    path('hr/vacancy/<int:vacancy_id>/longlist/', views.hr_longlist_dashboard, name='hr_longlist_dashboard'),
    path('hr/vacancy/<int:vacancy_id>/longlist/<int:app_id>/', views.hr_longlist_dossier, name='hr_longlist_dossier'),
    path('hr/vacancy/<int:vacancy_id>/longlist/<int:app_id>/decision/', views.hr_longlist_decision,
         name='hr_longlist_decision'),
    path('hr/vacancy/<int:vacancy_id>/longlist/bulk/', views.hr_longlist_bulk, name='hr_longlist_bulk'),
    path('hr/vacancy/<int:vacancy_id>/longlist/<int:app_id>/recall/', views.hr_longlist_recall,
         name='hr_longlist_recall'),
    path('hr/vacancy/<int:vacancy_id>/longlist/finalise/', views.hr_longlist_finalise, name='hr_longlist_finalise'),
]
