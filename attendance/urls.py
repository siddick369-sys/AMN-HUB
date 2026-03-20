from django.urls import path
from attendance import views

app_name = 'attendance'

urlpatterns = [
    path('',               views.attendance_home,       name='home'),
    path('check-in/',      views.check_in_api,          name='check_in'),
    path('history/',       views.attendance_history,    name='history'),
    path('manager/',       views.manager_attendance_view, name='manager'),
]
