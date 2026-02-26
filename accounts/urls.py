from django.urls import path
from . import views

urlpatterns = [
    path('', views.landing, name='landing'),
    path('login/', views.index, name='index'),
    path('signup/', views.register, name='signup'),
    path('authregister/', views.save_user_account, name='authregister'),
    path('authlogin/', views.signin, name='authlogin'),
    path('logout/', views.logout, name='logout'),
    
    path("profile/", views.profile_view, name="profile"),
    path("profile/delete/", views.delete_profile, name="delete_profile"),
    
    path("academic/", views.academic_qualifications, name="academic_qualifications"),
    path("academic/edit/<int:pk>/", views.edit_academic, name="edit_academic"),
    path("academic/delete/<int:pk>/", views.delete_academic, name="delete_academic"),
    
    path("professional/", views.professional_qualifications, name="professional_qualifications"),
    path("professional/edit/<int:pk>/", views.edit_professional, name="edit_professional"),
    path("professional/delete/<int:pk>/", views.delete_professional, name="delete_professional"),  
    
    path("work-history/", views.work_history, name="work_history"),
    path("work-history/edit/<int:pk>/", views.edit_work_history, name="edit_work_history"),
    path("work-history/delete/<int:pk>/", views.delete_work_history, name="delete_work_history"),
    
    path("additional/", views.additional_details, name="additional_details"),
    path("additional/delete-cv/", views.delete_cv, name="delete_cv"),
]