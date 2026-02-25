from django.shortcuts import render

def index(request):
    return render(request, 'auth/login.html')

def register(request):
    return render(request, 'auth/register.html')

def hr_dashboard(request):
    return render(request, 'hr/dashboard.html')
