from django.urls import path
from . import views

urlpatterns = [
    path('dashboard/', views.dashboard, name='dashboard'),
    path('profile/', views.profile, name='profile'),
    path('qualifications/', views.qualifications, name='qualifications'),
    path('applications/', views.applications, name='applications'),
    path('status/', views.status, name='status'),
    path('base', views.base, name='base'),
]