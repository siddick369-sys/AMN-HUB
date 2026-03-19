"""
URLs — Module Users (authentification), AMN Employee Hub.
"""

from django.urls import path
from . import views

app_name = 'users'

urlpatterns = [
    # ── Authentification ──────────────────────────────────────────────────
    path('register/',   views.register_view,  name='register'),
    path('login/',      views.login_view,     name='login'),
    path('logout/',     views.logout_view,    name='logout'),

    # ── Vérification email ────────────────────────────────────────────────
    path('verify-email/', views.verify_email_view, name='verify_email'),

    # ── Réinitialisation de mot de passe ──────────────────────────────────
    path('password-reset/',
         views.password_reset_request_view,
         name='password_reset_request'),
    path('reset-password/<uuid:token>/',
         views.password_reset_confirm_view,
         name='password_reset_confirm'),

    # ── Gestion du compte (gel / suppression) ─────────────────────────────
    path('delete-account/',
         views.request_account_deletion_view,
         name='request_deletion'),
    path('account-frozen/',
         views.account_frozen_confirmed_view,
         name='account_frozen_confirmed'),
    path('cancel-deletion/<uuid:token>/',
         views.cancel_deletion_view,
         name='cancel_deletion'),

    # ── Profil ────────────────────────────────────────────────────────────
    path('profile/', views.profile_view, name='profile'),
]
