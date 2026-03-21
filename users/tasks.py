"""
Tâches Celery asynchrones — Module Users, AMN Employee Hub.

Toutes les opérations bloquantes (envoi de mails, journalisation,
suppression de comptes) sont exécutées ici hors du fil HTTP principal.
"""

import logging
from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.html import strip_tags
from django.utils.translation import gettext as _, activate

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# HELPER INTERNE
# ─────────────────────────────────────────────────────────────────────────────

def _get_user(user_id):
    """Récupère un Employee par son ID, retourne None si inexistant."""
    from users.models import Employee
    try:
        return Employee.objects.get(pk=user_id)
    except Employee.DoesNotExist:
        logger.warning(f'[AMN Task] Utilisateur introuvable : ID={user_id}')
        return None


def _activate_user_language(user):
    """Active la langue préférée de l'utilisateur pour les traductions."""
    lang = getattr(user, 'preferred_language', 'fr') or 'fr'
    activate(lang)


def _send_html_email(subject, template_name, context, recipient_email):
    """
    Envoi d'un email HTML avec version texte en fallback.
    Centralise la logique d'envoi pour tous les mails AMN.
    """
    html_content  = render_to_string(f'emails/{template_name}', context)
    text_content  = strip_tags(html_content)

    try:
        send_mail(
            subject=subject,
            message=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[recipient_email],
            html_message=html_content,
            fail_silently=False,
        )
        logger.info(f'[AMN Mail] Envoyé → {recipient_email} | Sujet: {subject}')
        return True
    except Exception as exc:
        logger.error(f'[AMN Mail] Échec envoi → {recipient_email} | Erreur: {exc}')
        raise


# ─────────────────────────────────────────────────────────────────────────────
# TÂCHE 1 : Enregistrement asynchrone d'une activité
# ─────────────────────────────────────────────────────────────────────────────

@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=10,
    name='users.log_activity_async'
)
def log_activity_async(self, user_id, action, ip_address='', user_agent='', extra_data=None):
    """
    Crée un enregistrement ActivityLog sans bloquer la vue HTTP.
    Appelée depuis Employee.log_activity() ou le middleware.

    Args:
        user_id     : PK de l'employé
        action      : code action (voir ActivityAction.choices)
        ip_address  : IP du client
        user_agent  : User-Agent du navigateur
        extra_data  : dict de données contextuelles optionnelles
    """
    from users.models import ActivityLog

    try:
        ActivityLog.objects.create(
            user_id=user_id,
            action=action,
            ip_address=ip_address or None,
            user_agent=user_agent or '',
            extra_data=extra_data or {},
        )
        logger.debug(f'[AMN Log] Activité enregistrée : user={user_id}, action={action}')
    except Exception as exc:
        logger.error(f'[AMN Log] Erreur enregistrement activité : {exc}')
        raise self.retry(exc=exc)


# ─────────────────────────────────────────────────────────────────────────────
# TÂCHE 2 : Envoi du code de vérification par email
# ─────────────────────────────────────────────────────────────────────────────

@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    name='users.send_verification_email'
)
def send_verification_email(self, user_id):
    """
    Génère un code OTP à 6 chiffres et l'envoie par email à l'utilisateur.
    Appelée juste après l'inscription.

    Args:
        user_id : PK de l'employé nouvellement inscrit
    """
    user = _get_user(user_id)
    if not user:
        return

    _activate_user_language(user)

    # Générer le code OTP (sauvegarde incluse dans la méthode)
    code = user.generate_verification_code()

    context = {
        'user': user,
        'code': code,
        'expiry_minutes': 15,
        'app_name': 'AMN Employee Hub',
        'frontend_url': settings.FRONTEND_URL,
    }

    try:
        _send_html_email(
            subject=_('AMN Hub — Vérification de votre adresse email'),
            template_name='verification_code.html',
            context=context,
            recipient_email=user.email,
        )
    except Exception as exc:
        logger.error(f'[AMN Mail] Échec vérification email user={user_id}: {exc}')
        raise self.retry(exc=exc)


# ─────────────────────────────────────────────────────────────────────────────
# TÂCHE 3 : Envoi du lien de réinitialisation de mot de passe
# ─────────────────────────────────────────────────────────────────────────────

@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    name='users.send_password_reset_email'
)
def send_password_reset_email(self, user_id):
    """
    Génère un token UUID unique et envoie un lien de reset par email.
    Le lien est valide 1 heure.

    Args:
        user_id : PK de l'employé demandant le reset
    """
    user = _get_user(user_id)
    if not user:
        return

    _activate_user_language(user)

    # Générer le token de reset (sauvegarde incluse)
    token = user.generate_reset_token()

    reset_url = f'{settings.FRONTEND_URL}/auth/reset-password/{token}/'

    context = {
        'user': user,
        'reset_url': reset_url,
        'expiry_hours': 1,
        'app_name': 'AMN Employee Hub',
        'frontend_url': settings.FRONTEND_URL,
    }

    try:
        _send_html_email(
            subject=_('AMN Hub — Réinitialisation de votre mot de passe'),
            template_name='password_reset.html',
            context=context,
            recipient_email=user.email,
        )
    except Exception as exc:
        logger.error(f'[AMN Mail] Échec reset MDP user={user_id}: {exc}')
        raise self.retry(exc=exc)


# ─────────────────────────────────────────────────────────────────────────────
# TÂCHE 4 : Envoi du mail de confirmation de gel + lien d'annulation
# ─────────────────────────────────────────────────────────────────────────────

@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    name='users.send_account_frozen_email'
)
def send_account_frozen_email(self, user_id):
    """
    Envoie un email de confirmation après le gel du compte.
    Contient un lien unique (token UUID) pour annuler la suppression dans J+30.

    Args:
        user_id : PK de l'employé dont le compte vient d'être gelé
    """
    user = _get_user(user_id)
    if not user:
        return

    _activate_user_language(user)

    cancel_url = (
        f'{settings.FRONTEND_URL}/auth/cancel-deletion/{user.deletion_cancel_token}/'
    )

    context = {
        'user': user,
        'cancel_url': cancel_url,
        'deletion_date': user.deletion_scheduled_at,
        'days_remaining': user.days_until_deletion,
        'app_name': 'AMN Employee Hub',
        'frontend_url': settings.FRONTEND_URL,
    }

    try:
        _send_html_email(
            subject=_('AMN Hub — Confirmation de suppression de compte'),
            template_name='account_frozen.html',
            context=context,
            recipient_email=user.email,
        )
    except Exception as exc:
        logger.error(f'[AMN Mail] Échec mail gel compte user={user_id}: {exc}')
        raise self.retry(exc=exc)


# ─────────────────────────────────────────────────────────────────────────────
# TÂCHE 5 : Envoi du mail de confirmation de restauration de compte
# ─────────────────────────────────────────────────────────────────────────────

@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    name='users.send_account_restored_email'
)
def send_account_restored_email(self, user_id):
    """
    Envoie un email de confirmation après la restauration du compte.

    Args:
        user_id : PK de l'employé dont le compte a été restauré
    """
    user = _get_user(user_id)
    if not user:
        return

    _activate_user_language(user)

    context = {
        'user': user,
        'login_url': f'{settings.FRONTEND_URL}/auth/login/',
        'app_name': 'AMN Employee Hub',
        'frontend_url': settings.FRONTEND_URL,
    }

    try:
        _send_html_email(
            subject=_('AMN Hub — Votre compte a été restauré'),
            template_name='account_restored.html',
            context=context,
            recipient_email=user.email,
        )
    except Exception as exc:
        logger.error(f'[AMN Mail] Échec mail restauration user={user_id}: {exc}')
        raise self.retry(exc=exc)


# ─────────────────────────────────────────────────────────────────────────────
# TÂCHE 6 : Suppression définitive des comptes expirés (tâche planifiée)
# ─────────────────────────────────────────────────────────────────────────────

@shared_task(name='users.purge_expired_frozen_accounts')
def purge_expired_frozen_accounts():
    """
    Supprime définitivement les comptes dont la date de suppression
    programmée est dépassée. À planifier quotidiennement via Celery Beat.

    Configurée dans l'interface Admin > Periodic Tasks.
    """
    from users.models import Employee

    now = timezone.now()
    expired_accounts = Employee.objects.filter(
        is_frozen=True,
        deletion_scheduled_at__lte=now
    )

    count = expired_accounts.count()
    if count == 0:
        logger.info('[AMN Purge] Aucun compte expiré à supprimer.')
        return

    # Journaliser avant suppression
    for emp in expired_accounts:
        logger.info(f'[AMN Purge] Suppression définitive : user={emp.pk} ({emp.email})')
        # Log d'activité final (synchrone ici car l'user va être supprimé)
        from users.models import ActivityLog
        ActivityLog.objects.create(
            user=None,  # L'user sera supprimé, on ne garde que l'IP
            action='account_deleted',
            extra_data={
                'deleted_user_email': emp.email,
                'deleted_user_id_badge': emp.id_badge,
                'deletion_reason': 'scheduled_auto_deletion',
            }
        )

    expired_accounts.delete()
    logger.info(f'[AMN Purge] {count} compte(s) supprimé(s) définitivement.')
    return count


@shared_task(name='users.mark_learning_tour_seen_async')
def mark_learning_tour_seen_async(user_id):
    """
    Marque le tutoriel Learning comme vu de manière asynchrone.
    """
    user = _get_user(user_id)
    if user and not user.has_seen_learning_tour:
        user.has_seen_learning_tour = True
        user.save(update_fields=['has_seen_learning_tour'])
        logger.info(f'[AMN Task] Tour Learning marqué comme vu pour user={user_id}')
