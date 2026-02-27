from django.urls import path
from . import views

urlpatterns = [
    path('', views.landing, name='landing'),
    path('login/', views.index, name='index'),
    path('signup/', views.register, name='signup'),
    path('authregister/', views.save_user_account, name='authregister'),
    path('authlogin/', views.signin, name='authlogin'),
    path('logout/', views.logout, name='logout'),
    
]