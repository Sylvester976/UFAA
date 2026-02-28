from django.urls import path
from . import views

urlpatterns = [
    path('dashboard/', views.dashboard, name='dashboard'),

    path("profile/", views.profile_view, name="profile"),
    path("profile/delete/", views.delete_profile, name="delete_profile"),
    path("academic/", views.academic_qualifications_view, name="academic_qualifications"),
    path("professional/", views.professional_qualifications_view, name="professional_qualifications"),
    path("work-history/", views.work_history_view, name="work_history"),

    # path("additional/", views.additional_details, name="additional_details"),
    # path("additional/delete-cv/", views.delete_cv, name="delete_cv"),
    
    # HR DASHBOARD
    path('hr/dashboard/', views.hr_dashboard, name='hr_dashboard'),

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
]