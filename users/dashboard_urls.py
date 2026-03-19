"""
URLs — Dashboard principal, AMN Employee Hub.
Séparé de users/urls.py pour une architecture plus claire.
"""

from django.urls import path
from django.contrib.auth.decorators import login_required
from django.shortcuts import render

app_name = 'dashboard'


def home_view(request):
    """Vue temporaire du dashboard — sera remplacée par le vrai dashboard."""
    if not request.user.is_authenticated:
        from django.shortcuts import redirect
        return redirect('users:login')
    return render(request, 'dashboard/home.html', {
        'user': request.user,
        'app_name': 'AMN Employee Hub',
    })


urlpatterns = [
    path('', home_view, name='home'),
]
