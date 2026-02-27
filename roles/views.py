from django.shortcuts import render
from django.shortcuts import redirect

from .models import Permission, Role

from roles.models import Role
from accounts.models import User

from django.views.generic import CreateView, ListView
from django.urls import reverse_lazy
from core.mixins import SuperAdminRequiredMixin
from .models import Role, Permission

from .services import create_permission

from django.views.generic import UpdateView, ListView
from django.urls import reverse_lazy
from core.mixins import SuperAdminRequiredMixin

from accounts.models import User



from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from .models import Role, Permission
from core.decorators import superadmin_required

from django.shortcuts import render, redirect, get_object_or_404

@superadmin_required
def create_role(request):
    permissions = Permission.objects.all()

    if request.method == "POST":
        name = request.POST.get("name")
        description = request.POST.get("description")
        permission_ids = request.POST.getlist("permissions")

        role = Role.objects.create(
            name=name,
            description=description
        )

        role.permissions.set(permission_ids)
        return redirect("role_list")

    return render(request, "role_form.html", {
        "permissions": permissions
    })
    
    
@superadmin_required
def assign_role(request, user_id):
    user = User.objects.get(id=user_id)
    roles = Role.objects.all()

    if request.method == "POST":
        role_ids = request.POST.getlist("role")  # IMPORTANT: getlist()

        user.role.set(role_ids)  # replaces all existing roles
        user.save()

        return redirect("user_list")

    return render(request, "assign_role_form.html", {
        "user": user,
        "roles": roles
    })
    






def permission_list(request):
    permissions = Permission.objects.all()
    return render(request, "roles/permission_list.html", {
        "permissions": permissions
    })
    
@superadmin_required
def permission_create(request):
    if request.method == "POST":
        Permission.objects.create(
            name=request.POST.get("name"),
            code=request.POST.get("code"),
            description=request.POST.get("description"),
        )
        return redirect("permission_list")

    return render(request, "roles/permission_form.html")

@superadmin_required
def permission_update(request, pk):
    permission = get_object_or_404(Permission, pk=pk)

    if request.method == "POST":
        permission.name = request.POST.get("name")
        permission.code = request.POST.get("code")
        permission.description = request.POST.get("description")
        permission.save()
        return redirect("permission_list")

    return render(request, "roles/permission_form.html", {
        "permission": permission
    })
    
@superadmin_required  
def permission_delete(request, pk):
    permission = get_object_or_404(Permission, pk=pk)

    if request.method == "POST":
        permission.delete()
        return redirect("permission_list")

    return render(request, "roles/permission_confirm_delete.html", {
        "permission": permission
    })

@superadmin_required  
def role_list(request):
    roles = Role.objects.prefetch_related("permissions").all()
    return render(request, "roles/role_list.html", {
        "roles": roles
    })
    
@superadmin_required   
def role_create(request):
    permissions = Permission.objects.all()

    if request.method == "POST":
        role = Role.objects.create(
            name=request.POST.get("name"),
            description=request.POST.get("description"),
        )

        permission_ids = request.POST.getlist("permissions")
        role.permissions.set(permission_ids)

        return redirect("role_list")

    return render(request, "roles/role_form.html", {
        "permissions": permissions
    })

@superadmin_required
def role_update(request, pk):
    role = get_object_or_404(Role, pk=pk)
    permissions = Permission.objects.all()

    if request.method == "POST":
        role.name = request.POST.get("name")
        role.description = request.POST.get("description")
        role.save()

        permission_ids = request.POST.getlist("permissions")
        role.permissions.set(permission_ids)

        return redirect("role_list")

    return render(request, "roles/role_form.html", {
        "role": role,
        "permissions": permissions
    })

@superadmin_required  
def role_delete(request, pk):
    role = get_object_or_404(Role, pk=pk)

    if request.method == "POST":
        role.delete()
        return redirect("role_list")

    return render(request, "roles/role_confirm_delete.html", {
        "role": role
    })
    
