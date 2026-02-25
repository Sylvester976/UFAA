from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('signup/', views.register, name='signup'),
    path('hr/dashboard/', views.dashboard, name='dashboard'),
]