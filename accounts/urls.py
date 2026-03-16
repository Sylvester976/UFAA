from django.urls import path

from . import views
from .views import (UserListView, UserCreateView, UserUpdateView, UserDeleteView, assign_role)

urlpatterns = [
    path('', views.landing, name='landing'),
    path('login/', views.index, name='index'),
    path('signup/', views.register, name='signup'),
    path('authregister/', views.save_user_account, name='authregister'),
    path('authlogin/', views.signin, name='authlogin'),
    path('logout/', views.logout_view, name='logout'),

    path('verify-email/<uuid:token>/', views.verify_email, name='verify_email'),
    path('auth/resend-verification/', views.resend_verification, name='resend_verification'),
    path('forgot-password/', views.forgot_password, name='forgot_password'),
    path('auth/send-reset-link/', views.send_reset_link, name='send_reset_link'),
    path('reset-password/<uuid:token>/', views.reset_password, name='reset_password'),
    path('auth/reset-password/', views.do_reset_password, name='do_reset_password'),
    path('verify/<uuid:token>/', views.verify_email, name='verify_email'),

    path("staff/", views.login_view, name="login"),
    path('staff/logout/', views.dashboard_logout, name='dashboard_logout'),

    path("users/", UserListView.as_view(), name="user_list"),
    path("users/create/", UserCreateView.as_view(), name="user_create"),
    path("users/<uuid:pk>/update/", UserUpdateView.as_view(), name="user_update"),
    path("users/<uuid:pk>/delete/", UserDeleteView.as_view(), name="user_delete"),

    path("users/<uuid:user_id>/assign-role/", assign_role, name="assign_role"),

    path("test/", views.test_dashbord, name="test_dashbord"),

    path("dashboard/", views.redirect_dashboard, name="redirect_dashboard"),
    
    path( "staff/set-password/<uuid:token>/", views.staff_reset_password, name="staff_reset_password"),

    path("staff/set-password/", views.staff_do_reset_password, name="staff_do_reset_password"),
    
    path("staff/forgot-password/", views.staff_forgot_password, name="staff_forgot_password"),

    path("staff/send-reset-link/", views.staff_send_reset_link, name="staff_send_reset_link"),
    
    path("users/<uuid:user_id>/activate/", views.user_activate, name="user_activate"),
    
    path("users/<uuid:user_id>/deactivate/", views.user_deactivate, name="user_deactivate"),
]
