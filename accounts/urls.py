from django.urls import path
from . import views
from .views import (UserListView, UserCreateView, UserUpdateView, UserDeleteView, assign_role, test_dashbord)

urlpatterns = [
    path('', views.landing, name='landing'),
    path('login/', views.index, name='index'),
    path('signup/', views.register, name='signup'),
    path('authregister/', views.save_user_account, name='authregister'),
    path('authlogin/', views.signin, name='authlogin'),
    path('logout/', views.logout, name='logout'),
    path('verify/<uuid:token>/', views.verify_email, name='verify_email'),
    
    path("super/login/", views.login_view, name="login"),
    
    path("users/", UserListView.as_view(), name="user_list"),
    path("users/create/", UserCreateView.as_view(), name="user_create"),
    path("users/<uuid:pk>/update/", UserUpdateView.as_view(), name="user_update"),
    path("users/<uuid:pk>/delete/", UserDeleteView.as_view(), name="user_delete"),
    
    # path("users/<int:user_id>/assign-role/", assign_role, name="assign_role"),
    path("users/<uuid:user_id>/assign-role/", assign_role, name="assign_role"),
    
    path("test/", views.test_dashbord, name="test_dashbord"),
]