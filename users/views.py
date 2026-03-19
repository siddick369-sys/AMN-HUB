"""
Vues — Module Users, AMN Employee Hub.
Gère l'intégralité des flux d'authentification et de gestion de compte.
Toutes les opérations lourdes sont déléguées à Celery.
"""

import logging
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_http_methods

from .forms import (
    LoginForm, PasswordResetConfirmForm, PasswordResetRequestForm,
    ProfileUpdateForm, RegistrationForm, VerificationCodeForm,
)
from .models import ActivityAction, Employee
from .utils import (
    get_client_ip, get_lockout_remaining_seconds,
    increment_failed_attempts, is_locked_out, reset_failed_attempts,
)

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# HELPER : Contexte de base pour toutes les vues auth
# ─────────────────────────────────────────────────────────────────────────────

def _auth_context(extra=None):
    """Retourne le contexte de base pour les pages d'authentification."""
    ctx = {'app_name': 'AMN Employee Hub'}
    if extra:
        ctx.update(extra)
    return ctx


# ─────────────────────────────────────────────────────────────────────────────
# VUE 1 : Inscription
# ─────────────────────────────────────────────────────────────────────────────

@require_http_methods(['GET', 'POST'])
def register_view(request):
    """
    Inscription d'un nouvel employé.
    Après création du compte → envoie un code OTP par email via Celery.
    """
    if request.user.is_authenticated:
        return redirect('dashboard:home')

    form = RegistrationForm(request.POST or None)

    if request.method == 'POST':
        if form.is_valid():
            user = form.save()
            logger.info(f'[AMN Register] Nouvel employé créé : {user.email}')

            # Envoi asynchrone du code de vérification
            from .tasks import send_verification_email
            send_verification_email.delay(user.pk)

            # Log d'activité asynchrone
            user.log_activity(
                action=ActivityAction.REGISTER,
                ip_address=get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
            )

            # Stocker l'ID en session pour la page de vérification
            request.session['pending_verification_user_id'] = user.pk

            messages.success(
                request,
                _('Compte créé ! Vérifiez votre boîte email pour confirmer votre adresse.')
            )
            return redirect('users:verify_email')

    return render(request, 'users/register.html', _auth_context({'form': form}))


# ─────────────────────────────────────────────────────────────────────────────
# VUE 2 : Connexion
# ─────────────────────────────────────────────────────────────────────────────

@require_http_methods(['GET', 'POST'])
def login_view(request):
    """
    Connexion avec protection brute force via Redis.
    Bloque après 5 tentatives échouées pendant 15 minutes.
    """
    if request.user.is_authenticated:
        return redirect('dashboard:home')

    form = LoginForm(request.POST or None)
    ip = get_client_ip(request)

    if request.method == 'POST':
        # Vérification brute force par IP
        if is_locked_out(ip, 'login'):
            remaining = get_lockout_remaining_seconds(ip, 'login')
            minutes   = max(1, remaining // 60)
            messages.error(
                request,
                _(f'Trop de tentatives. Réessayez dans {minutes} minute(s).')
            )
            return render(request, 'users/login.html', _auth_context({
                'form': form, 'is_locked': True, 'lockout_minutes': minutes,
            }))

        if form.is_valid():
            raw_username = form.cleaned_data['username'].strip()
            password     = form.cleaned_data['password']
            remember_me  = form.cleaned_data.get('remember_me', False)

            # Résoudre email → username si nécessaire
            if '@' in raw_username:
                try:
                    emp = Employee.objects.get(email__iexact=raw_username)
                    username = emp.username
                except Employee.DoesNotExist:
                    username = raw_username
            else:
                username = raw_username

            # Vérification brute force par username
            if is_locked_out(username, 'login'):
                remaining = get_lockout_remaining_seconds(username, 'login')
                messages.error(
                    request,
                    _(f'Ce compte est temporairement verrouillé. Réessayez dans {max(1, remaining // 60)} minute(s).')
                )
                return render(request, 'users/login.html', _auth_context({'form': form, 'is_locked': True}))

            user = authenticate(request, username=username, password=password)

            if user is not None:
                # Compte gelé → refuser la connexion
                if user.is_frozen:
                    messages.error(
                        request,
                        _('Ce compte est suspendu et en attente de suppression. '
                          'Vérifiez votre email pour l\'annuler.')
                    )
                    return render(request, 'users/login.html', _auth_context({'form': form}))

                # Réinitialiser les compteurs de brute force
                reset_failed_attempts(ip, 'login')
                reset_failed_attempts(username, 'login')

                # Durée de session selon "Se souvenir de moi"
                if not remember_me:
                    request.session.set_expiry(0)  # Expire à la fermeture du navigateur

                login(request, user)

                # Log d'activité asynchrone
                user.log_activity(
                    action=ActivityAction.LOGIN,
                    ip_address=ip,
                    user_agent=request.META.get('HTTP_USER_AGENT', ''),
                )

                # Rediriger vers l'URL demandée ou le dashboard
                next_url = request.GET.get('next', '')
                if next_url and next_url.startswith('/'):
                    return redirect(next_url)

                # Email non vérifié → rediriger vers la vérification
                if not user.is_verified:
                    request.session['pending_verification_user_id'] = user.pk
                    messages.warning(
                        request,
                        _('Votre email n\'est pas encore vérifié. Veuillez entrer votre code.')
                    )
                    return redirect('users:verify_email')

                messages.success(request, _(f'Bienvenue, {user.first_name or user.username} !'))
                return redirect('dashboard:home')

            else:
                # Authentification échouée → incrémenter brute force
                attempts_ip      = increment_failed_attempts(ip, 'login')
                attempts_user    = increment_failed_attempts(username, 'login')
                remaining_before = max(0, 5 - max(attempts_ip, attempts_user))

                # Log de l'échec
                from .tasks import log_activity_async
                log_activity_async.delay(
                    user_id=None,
                    action=ActivityAction.FAILED_LOGIN,
                    ip_address=ip,
                    user_agent=request.META.get('HTTP_USER_AGENT', ''),
                    extra_data={'attempted_username': username},
                )

                if remaining_before <= 0:
                    messages.error(request, _('Compte verrouillé après trop de tentatives.'))
                else:
                    messages.error(
                        request,
                        _(f'Identifiants incorrects. {remaining_before} tentative(s) restante(s).')
                    )

    return render(request, 'users/login.html', _auth_context({'form': form}))


# ─────────────────────────────────────────────────────────────────────────────
# VUE 3 : Déconnexion
# ─────────────────────────────────────────────────────────────────────────────

@require_http_methods(['GET', 'POST'])
def logout_view(request):
    """Déconnexion propre avec journalisation asynchrone."""
    if request.user.is_authenticated:
        request.user.log_activity(
            action=ActivityAction.LOGOUT,
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
        )
        logout(request)

    messages.info(request, _('Vous avez été déconnecté avec succès.'))
    return redirect('users:login')


# ─────────────────────────────────────────────────────────────────────────────
# VUE 4 : Vérification de l'email (saisie du code OTP)
# ─────────────────────────────────────────────────────────────────────────────

@require_http_methods(['GET', 'POST'])
def verify_email_view(request):
    """
    Saisie du code OTP reçu par email.
    Protégée contre le brute force (5 tentatives max par IP).
    """
    # Récupérer l'utilisateur depuis la session
    user_id = request.session.get('pending_verification_user_id')
    if not user_id:
        # Si déjà connecté et non vérifié
        if request.user.is_authenticated and not request.user.is_verified:
            user_id = request.user.pk
        else:
            messages.error(request, _('Session expirée. Veuillez vous reconnecter.'))
            return redirect('users:login')

    try:
        user = Employee.objects.get(pk=user_id)
    except Employee.DoesNotExist:
        messages.error(request, _('Utilisateur introuvable.'))
        return redirect('users:login')

    if user.is_verified:
        messages.info(request, _('Votre email est déjà vérifié.'))
        return redirect('dashboard:home')

    ip    = get_client_ip(request)
    form  = VerificationCodeForm(request.POST or None)

    if request.method == 'POST':
        # Protection brute force sur la vérification
        if is_locked_out(ip, 'verify'):
            remaining = get_lockout_remaining_seconds(ip, 'verify')
            messages.error(
                request,
                _(f'Trop de tentatives de vérification. Réessayez dans {max(1, remaining // 60)} minute(s).')
            )
            return render(request, 'users/verify_email.html', _auth_context({
                'form': form, 'user': user, 'is_locked': True,
            }))

        # Action : renvoyer le code
        if 'resend' in request.POST:
            from .tasks import send_verification_email
            send_verification_email.delay(user.pk)
            messages.success(request, _('Un nouveau code a été envoyé à votre adresse email.'))
            return redirect('users:verify_email')

        if form.is_valid():
            submitted_code = form.cleaned_data['code']

            if not user.is_verification_code_valid:
                messages.error(request, _('Le code a expiré. Demandez-en un nouveau.'))
            elif user.verification_code != submitted_code:
                attempts = increment_failed_attempts(ip, 'verify')
                remaining_before = max(0, 5 - attempts)
                if remaining_before <= 0:
                    messages.error(request, _('Trop de tentatives incorrectes. Compte temporairement bloqué.'))
                else:
                    messages.error(
                        request,
                        _(f'Code incorrect. {remaining_before} tentative(s) restante(s).')
                    )
            else:
                # Code valide ✓
                reset_failed_attempts(ip, 'verify')
                user.is_verified = True
                user.verification_code = ''
                user.save(update_fields=['is_verified', 'verification_code'])

                # Log d'activité asynchrone
                user.log_activity(
                    action=ActivityAction.EMAIL_VERIFIED,
                    ip_address=ip,
                    user_agent=request.META.get('HTTP_USER_AGENT', ''),
                )

                # Nettoyer la session
                request.session.pop('pending_verification_user_id', None)

                # Connecter l'utilisateur si ce n'est pas déjà fait
                if not request.user.is_authenticated:
                    login(request, user)

                messages.success(request, _('Votre email a été vérifié avec succès. Bienvenue !'))
                return redirect('dashboard:home')

    return render(request, 'users/verify_email.html', _auth_context({
        'form': form,
        'user': user,
        'email_masked': _mask_email(user.email),
    }))


# ─────────────────────────────────────────────────────────────────────────────
# VUE 5 : Demande de réinitialisation de mot de passe
# ─────────────────────────────────────────────────────────────────────────────

@require_http_methods(['GET', 'POST'])
def password_reset_request_view(request):
    """
    Demande d'envoi d'un lien de reset par email.
    Délègue l'envoi à Celery. Répond toujours avec un message générique
    pour éviter l'énumération d'emails (sécurité).
    """
    if request.user.is_authenticated:
        return redirect('dashboard:home')

    ip   = get_client_ip(request)
    form = PasswordResetRequestForm(request.POST or None)

    if request.method == 'POST':
        if is_locked_out(ip, 'reset_request'):
            remaining = get_lockout_remaining_seconds(ip, 'reset_request')
            messages.error(request, _(f'Trop de demandes. Réessayez dans {max(1, remaining // 60)} min.'))
            return render(request, 'users/password_reset_request.html', _auth_context({'form': form}))

        if form.is_valid():
            email = form.cleaned_data['email'].lower()

            try:
                user = Employee.objects.get(email__iexact=email, is_active=True)
                from .tasks import send_password_reset_email
                send_password_reset_email.delay(user.pk)

                user.log_activity(
                    action=ActivityAction.PASSWORD_RESET_REQ,
                    ip_address=ip,
                    user_agent=request.META.get('HTTP_USER_AGENT', ''),
                )
            except Employee.DoesNotExist:
                # Délai artificiel pour éviter le timing attack
                import time; time.sleep(0.2)
                increment_failed_attempts(ip, 'reset_request')

            # Toujours afficher le même message (anti-énumération)
            messages.success(
                request,
                _('Si cette adresse email est associée à un compte, '
                  'vous recevrez un lien de réinitialisation sous peu.')
            )
            return redirect('users:password_reset_request')

    return render(request, 'users/password_reset_request.html', _auth_context({'form': form}))


# ─────────────────────────────────────────────────────────────────────────────
# VUE 6 : Saisie du nouveau mot de passe
# ─────────────────────────────────────────────────────────────────────────────

@require_http_methods(['GET', 'POST'])
def password_reset_confirm_view(request, token):
    """
    Permet de saisir un nouveau mot de passe via le token reçu par email.
    Invalide le token après utilisation.
    """
    import uuid as uuid_module

    # Valider le format UUID du token
    try:
        token_uuid = uuid_module.UUID(str(token))
    except (ValueError, AttributeError):
        messages.error(request, _('Lien de réinitialisation invalide.'))
        return redirect('users:password_reset_request')

    # Trouver l'utilisateur correspondant au token
    try:
        user = Employee.objects.get(password_reset_token=token_uuid, is_active=True)
    except Employee.DoesNotExist:
        messages.error(request, _('Ce lien est invalide ou a déjà été utilisé.'))
        return redirect('users:password_reset_request')

    # Vérifier l'expiration du token (1 heure)
    if not user.is_reset_token_valid:
        messages.error(request, _('Ce lien a expiré. Veuillez faire une nouvelle demande.'))
        return redirect('users:password_reset_request')

    form = PasswordResetConfirmForm(request.POST or None)

    if request.method == 'POST' and form.is_valid():
        user.set_password(form.cleaned_data['password1'])
        # Invalider le token après utilisation
        user.password_reset_token = None
        user.password_reset_token_created_at = None
        user.save(update_fields=['password', 'password_reset_token', 'password_reset_token_created_at'])

        user.log_activity(
            action=ActivityAction.PASSWORD_CHANGED,
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
        )

        messages.success(request, _('Mot de passe modifié avec succès. Vous pouvez vous connecter.'))
        return redirect('users:login')

    return render(request, 'users/password_reset_confirm.html', _auth_context({
        'form': form,
        'token': token,
    }))


# ─────────────────────────────────────────────────────────────────────────────
# VUE 7 : Demande de gel / suppression de compte
# ─────────────────────────────────────────────────────────────────────────────

@login_required
@require_http_methods(['GET', 'POST'])
def request_account_deletion_view(request):
    """
    L'employé demande la suppression de son compte.
    Le compte passe en is_frozen=True avec suppression définitive à J+30.
    Un email de confirmation avec lien d'annulation est envoyé via Celery.
    """
    user = request.user

    if user.is_frozen:
        messages.info(
            request,
            _(f'Votre compte est déjà en cours de suppression. '
              f'Suppression prévue le {user.deletion_scheduled_at:%d/%m/%Y}.')
        )
        return redirect('dashboard:home')

    if request.method == 'POST':
        # Confirmation explicite requise
        if request.POST.get('confirm') == 'DELETE':
            user.freeze_account()

            # Envoi du mail avec lien d'annulation (Celery)
            from .tasks import send_account_frozen_email
            send_account_frozen_email.delay(user.pk)

            # Log d'activité
            user.log_activity(
                action=ActivityAction.ACCOUNT_FROZEN,
                ip_address=get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
            )

            # Déconnecter l'utilisateur
            logout(request)

            messages.warning(
                request,
                _('Votre compte a été gelé. Vous recevrez un email avec un lien pour annuler '
                  'la suppression sous 30 jours.')
            )
            return redirect('users:account_frozen_confirmed')

        else:
            messages.error(request, _('Veuillez confirmer la suppression en saisissant "DELETE".'))

    return render(request, 'users/request_deletion.html', _auth_context({'user': user}))


@require_http_methods(['GET'])
def account_frozen_confirmed_view(request):
    """Page de confirmation du gel de compte."""
    return render(request, 'users/account_frozen_confirmed.html', _auth_context())


# ─────────────────────────────────────────────────────────────────────────────
# VUE 8 : Annulation de la suppression de compte (via lien email)
# ─────────────────────────────────────────────────────────────────────────────

@require_http_methods(['GET', 'POST'])
def cancel_deletion_view(request, token):
    """
    Restaure un compte gelé via le token unique envoyé par email.
    Accessible sans être connecté (l'utilisateur est gelé/déconnecté).
    """
    import uuid as uuid_module

    try:
        token_uuid = uuid_module.UUID(str(token))
    except (ValueError, AttributeError):
        messages.error(request, _('Lien d\'annulation invalide.'))
        return redirect('users:login')

    try:
        user = Employee.objects.get(
            deletion_cancel_token=token_uuid,
            is_frozen=True,
            is_active=True
        )
    except Employee.DoesNotExist:
        messages.error(request, _('Ce lien est invalide ou a déjà été utilisé.'))
        return redirect('users:login')

    if request.method == 'POST':
        user.restore_account()

        # Envoi du mail de confirmation de restauration (Celery)
        from .tasks import send_account_restored_email
        send_account_restored_email.delay(user.pk)

        # Log d'activité
        user.log_activity(
            action=ActivityAction.ACCOUNT_RESTORED,
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
        )

        messages.success(request, _('Votre compte a été restauré avec succès ! Connectez-vous.'))
        return redirect('users:login')

    return render(request, 'users/cancel_deletion.html', _auth_context({
        'user': user,
        'token': token,
        'deletion_date': user.deletion_scheduled_at,
    }))


# ─────────────────────────────────────────────────────────────────────────────
# VUE 9 : Profil utilisateur
# ─────────────────────────────────────────────────────────────────────────────

@login_required
@require_http_methods(['GET', 'POST'])
def profile_view(request):
    """Affichage et mise à jour du profil de l'employé connecté."""
    user = request.user
    form = ProfileUpdateForm(request.POST or None, request.FILES or None, instance=user)

    if request.method == 'POST' and form.is_valid():
        form.save()

        user.log_activity(
            action=ActivityAction.PROFILE_UPDATED,
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
        )

        messages.success(request, _('Profil mis à jour avec succès.'))
        return redirect('users:profile')

    recent_activity = user.activity_logs.select_related('user').order_by('-timestamp')[:10]

    return render(request, 'users/profile.html', _auth_context({
        'form': form,
        'recent_activity': recent_activity,
    }))


# ─────────────────────────────────────────────────────────────────────────────
# HELPER INTERNE
# ─────────────────────────────────────────────────────────────────────────────

def _mask_email(email: str) -> str:
    """Masque partiellement l'email pour l'affichage : j***@amn.com"""
    try:
        local, domain = email.split('@')
        masked_local = local[0] + '***' if len(local) > 1 else '***'
        return f'{masked_local}@{domain}'
    except Exception:
        return '***@***.***'
