"""
URLs — Module Learning (Onboarding + LMS), AMN Employee Hub.
"""

from django.urls import path
from . import views

app_name = 'learning'

urlpatterns = [
    # ── Onboarding ────────────────────────────────────────────────────────
    path('onboarding/',
         views.onboarding_dashboard,
         name='onboarding_dashboard'),
    path('onboarding/task/<int:task_id>/complete/',
         views.complete_onboarding_task,
         name='complete_onboarding_task'),

    # ── LMS ───────────────────────────────────────────────────────────────
    path('lms/',
         views.lms_dashboard,
         name='lms_dashboard'),
    path('lms/low-data-toggle/',
         views.toggle_low_data_mode,
         name='toggle_low_data_mode'),
    path('lms/course/<int:course_id>/',
         views.course_detail,
         name='course_detail'),
    path('lms/lesson/<int:lesson_id>/',
         views.lesson_detail,
         name='lesson_detail'),

    # ── Quiz ──────────────────────────────────────────────────────────────
    path('lms/quiz/<int:quiz_id>/',
         views.quiz_view,
         name='quiz'),

    # ── Manager ───────────────────────────────────────────────────────────
    path('manager/',
         views.manager_dashboard,
         name='manager_dashboard'),

    # ── Certificat public ─────────────────────────────────────────────────
    path('certificate/<str:unique_code>/',
         views.certificate_verify,
         name='certificate_verify'),
]
