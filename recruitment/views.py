from django.shortcuts import render

def dashboard(request):
    return render(request, 'recruitment/dashboard.html')

def profile(request):
    return render(request, 'recruitment/dashboard.html')

def qualifications(request):
    return render(request, 'recruitment/dashboard.html')

def applications(request):
    return render(request, 'recruitment/dashboard.html')

def status(request):
    return render(request, 'recruitment/dashboard.html')

def base(request):
    return render(request, 'layout/base.html')