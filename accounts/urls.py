from django.urls import path
from . import views

urlpatterns = [
    path('', views.landing, name='landing'),
    path('login/', views.index, name='index'),
    path('signup/', views.register, name='signup'),
    path('hr/dashboard/', views.dashboard, name='dashboard'),
    path('authregister/', views.save_user_account, name='authregister'),
    path('authlogin/', views.signin, name='authlogin'),
]