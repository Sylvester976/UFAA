from django.urls import path

from roles import views
from .views import *

urlpatterns = [
    # Permission URLs
    path("permissions/", views.permission_list, name="permission_list"),
    path("permissions/create/", views.permission_create, name="permission_create"),
    path("permissions/<uuid:pk>/edit/", views.permission_update, name="permission_update"),
    path("permissions/<uuid:pk>/delete/", views.permission_delete, name="permission_delete"),

    # Role URLs
    path("roles/", views.role_list, name="role_list"),
    path("roles/create/", views.role_create, name="role_create"),
    path("roles/<uuid:pk>/edit/", views.role_update, name="role_update"),
    path("roles/<uuid:pk>/delete/", views.role_delete, name="role_delete"),
]
