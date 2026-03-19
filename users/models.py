"""
Modèles du module Users — AMN Employee Hub.
Contient : Employee (utilisateur étendu) et ActivityLog (journal d'actions).
"""

import uuid
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


# ─────────────────────────────────────────────────────────────────────────────
# CHOIX (Choices)
# ─────────────────────────────────────────────────────────────────────────────

class Department(models.TextChoices):
    """Départements AMN disponibles."""
    TECH        = 'TECH',        _('Technology & IT')
    FINANCE     = 'FINANCE',     _('Finance & Accounting')
    HR          = 'HR',          _('Human Resources')
    OPERATIONS  = 'OPS',         _('Operations')
    MARKETING   = 'MKT',         _('Marketing & Communications')
    LEGAL       = 'LEGAL',       _('Legal & Compliance')
    SALES       = 'SALES',       _('Sales & Business Development')
    OTHER       = 'OTHER',       _('Other')


class Country(models.TextChoices):
    """Pays de déploiement AMN."""
    CAMEROON          = 'CM', _('Cameroon')
    NIGERIA           = 'NG', _('Nigeria')
    GHANA             = 'GH', _('Ghana')
    SENEGAL           = 'SN', _('Senegal')
    IVORY_COAST       = 'CI', _("Côte d'Ivoire")
    DEMOCRATIC_CONGO  = 'CD', _('DR Congo')
    MOZAMBIQUE        = 'MZ', _('Mozambique')
    MADAGASCAR        = 'MG', _('Madagascar')
    OTHER             = 'XX', _('Other')


class PreferredLanguage(models.TextChoices):
    """Langues préférées disponibles."""
    FRENCH  = 'fr', _('Français')
    ENGLISH = 'en', _('English')


class ActivityAction(models.TextChoices):
    """Actions traçables dans le journal d'activité."""
    LOGIN               = 'login',               _('Connexion')
    LOGOUT              = 'logout',              _('Déconnexion')
    REGISTER            = 'register',            _('Inscription')
    EMAIL_VERIFIED      = 'email_verified',      _('Email vérifié')
    PASSWORD_CHANGED    = 'password_changed',    _('Mot de passe modifié')
    PASSWORD_RESET_REQ  = 'password_reset_req',  _('Demande réinitialisation MDP')
    ACCOUNT_FROZEN      = 'account_frozen',      _('Compte gelé')
    ACCOUNT_RESTORED    = 'account_restored',    _('Compte restauré')
    ACCOUNT_DELETED     = 'account_deleted',     _('Compte supprimé')
    PROFILE_UPDATED     = 'profile_updated',     _('Profil mis à jour')
    FAILED_LOGIN        = 'failed_login',        _('Tentative de connexion échouée')


# ─────────────────────────────────────────────────────────────────────────────
# MODÈLE PRINCIPAL : Employee
# ─────────────────────────────────────────────────────────────────────────────

class Employee(AbstractUser):
    """
    Utilisateur étendu pour AMN Employee Hub.
    Hérite de AbstractUser (username, email, password, first_name, last_name…)
    et ajoute les champs spécifiques à l'entreprise AMN.
    """

    # ── Identifiant badge entreprise ──
    id_badge = models.CharField(
        max_length=20,
        unique=True,
        blank=True,
        null=True,
        verbose_name=_('ID Badge'),
        help_text=_('Identifiant unique du badge employé (ex: AMN-2025-001)')
    )

    # ── Photo de profil ──
    avatar = models.ImageField(
        upload_to='avatars/%Y/%m/',
        blank=True,
        null=True,
        verbose_name=_('Photo de profil')
    )

    # ── Informations professionnelles ──
    department = models.CharField(
        max_length=10,
        choices=Department.choices,
        default=Department.OTHER,
        verbose_name=_('Département')
    )

    country = models.CharField(
        max_length=2,
        choices=Country.choices,
        default=Country.CAMEROON,
        verbose_name=_('Pays')
    )

    job_title = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_('Poste / Titre')
    )

    phone_number = models.CharField(
        max_length=20,
        blank=True,
        verbose_name=_('Numéro de téléphone')
    )

    hire_date = models.DateField(
        null=True,
        blank=True,
        verbose_name=_("Date d'embauche")
    )

    # ── Préférence de langue ──
    preferred_language = models.CharField(
        max_length=5,
        choices=PreferredLanguage.choices,
        default=PreferredLanguage.FRENCH,
        verbose_name=_('Langue préférée')
    )

    # ── Statut de vérification du compte ──
    is_verified = models.BooleanField(
        default=False,
        verbose_name=_('Email vérifié'),
        help_text=_('True si l\'adresse email a été confirmée')
    )

    # ── Code de vérification (OTP 6 chiffres) ──
    verification_code = models.CharField(
        max_length=6,
        blank=True,
        verbose_name=_('Code de vérification')
    )

    verification_code_created_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Code créé le')
    )

    # ── Gel de compte ──
    is_frozen = models.BooleanField(
        default=False,
        verbose_name=_('Compte gelé'),
        help_text=_('Compte en attente de suppression définitive')
    )

    deletion_scheduled_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Suppression programmée le'),
        help_text=_('Date de suppression définitive (J+30 après demande)')
    )

    # ── Token unique pour annuler la suppression ──
    deletion_cancel_token = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        verbose_name=_('Token annulation suppression')
    )

    # ── Token de reset de mot de passe ──
    password_reset_token = models.UUIDField(
        null=True,
        blank=True,
        verbose_name=_('Token réinitialisation MDP')
    )

    password_reset_token_created_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Token MDP créé le')
    )

    # ── Métadonnées ──
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_('Dernière modification')
    )

    class Meta:
        verbose_name = _('Employé')
        verbose_name_plural = _('Employés')
        ordering = ['-date_joined']
        indexes = [
            models.Index(fields=['id_badge']),
            models.Index(fields=['department', 'country']),
            models.Index(fields=['is_frozen', 'deletion_scheduled_at']),
        ]

    def __str__(self):
        full_name = self.get_full_name()
        return full_name if full_name.strip() else self.username

    # ── Propriétés utiles ──

    @property
    def initials(self):
        """Retourne les initiales pour l'avatar par défaut (ex: 'JD')."""
        first = self.first_name[0].upper() if self.first_name else ''
        last  = self.last_name[0].upper() if self.last_name else ''
        return f'{first}{last}' or self.username[:2].upper()

    @property
    def is_verification_code_valid(self):
        """Vérifie que le code OTP n'a pas expiré (validité : 15 minutes)."""
        if not self.verification_code_created_at:
            return False
        expiry = self.verification_code_created_at + timezone.timedelta(minutes=15)
        return timezone.now() <= expiry

    @property
    def is_reset_token_valid(self):
        """Vérifie que le token de reset n'a pas expiré (validité : 1 heure)."""
        if not self.password_reset_token_created_at:
            return False
        expiry = self.password_reset_token_created_at + timezone.timedelta(hours=1)
        return timezone.now() <= expiry

    @property
    def days_until_deletion(self):
        """Retourne le nombre de jours restants avant suppression définitive."""
        if not self.deletion_scheduled_at:
            return None
        delta = self.deletion_scheduled_at - timezone.now()
        return max(0, delta.days)

    # ── Méthodes métier ──

    def generate_verification_code(self):
        """Génère un nouveau code OTP à 6 chiffres et met à jour le timestamp."""
        import random
        self.verification_code = str(random.randint(100000, 999999))
        self.verification_code_created_at = timezone.now()
        self.save(update_fields=['verification_code', 'verification_code_created_at'])
        return self.verification_code

    def generate_reset_token(self):
        """Génère un token UUID pour la réinitialisation du mot de passe."""
        self.password_reset_token = uuid.uuid4()
        self.password_reset_token_created_at = timezone.now()
        self.save(update_fields=['password_reset_token', 'password_reset_token_created_at'])
        return self.password_reset_token

    def freeze_account(self):
        """
        Gèle le compte et programme sa suppression dans ACCOUNT_DELETION_DELAY_DAYS jours.
        Régénère également un token d'annulation unique.
        """
        from django.conf import settings
        days = getattr(settings, 'ACCOUNT_DELETION_DELAY_DAYS', 30)
        self.is_frozen = True
        self.deletion_scheduled_at = timezone.now() + timezone.timedelta(days=days)
        self.deletion_cancel_token = uuid.uuid4()
        self.save(update_fields=['is_frozen', 'deletion_scheduled_at', 'deletion_cancel_token'])

    def restore_account(self):
        """Annule le gel et supprime la date de suppression programmée."""
        self.is_frozen = False
        self.deletion_scheduled_at = None
        self.deletion_cancel_token = uuid.uuid4()  # Invalide l'ancien token
        self.save(update_fields=['is_frozen', 'deletion_scheduled_at', 'deletion_cancel_token'])

    def log_activity(self, action, ip_address='', user_agent=''):
        """
        Délègue l'enregistrement d'une activité à Celery.
        N'importe quelle vue peut appeler ceci sans bloquer la réponse HTTP.
        """
        from users.tasks import log_activity_async
        log_activity_async.delay(
            user_id=self.pk,
            action=action,
            ip_address=ip_address,
            user_agent=user_agent
        )


# ─────────────────────────────────────────────────────────────────────────────
# MODÈLE : ActivityLog (Journal d'activité)
# ─────────────────────────────────────────────────────────────────────────────

class ActivityLog(models.Model):
    """
    Journal de toutes les actions significatives des utilisateurs.
    Enregistrements toujours créés via une tâche Celery (log_activity_async).
    """

    user = models.ForeignKey(
        'users.Employee',
        on_delete=models.SET_NULL,
        null=True,
        related_name='activity_logs',
        verbose_name=_('Employé')
    )

    action = models.CharField(
        max_length=30,
        choices=ActivityAction.choices,
        verbose_name=_('Action')
    )

    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        verbose_name=_('Adresse IP')
    )

    user_agent = models.TextField(
        blank=True,
        verbose_name=_('User Agent')
    )

    extra_data = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_('Données supplémentaires'),
        help_text=_('Informations contextuelles au format JSON')
    )

    timestamp = models.DateTimeField(
        default=timezone.now,
        db_index=True,
        verbose_name=_('Horodatage')
    )

    class Meta:
        verbose_name = _("Journal d'activité")
        verbose_name_plural = _("Journaux d'activité")
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['user', 'action']),
            models.Index(fields=['timestamp']),
            models.Index(fields=['ip_address']),
        ]

    def __str__(self):
        username = self.user.username if self.user else _('Utilisateur supprimé')
        return f'[{self.timestamp:%Y-%m-%d %H:%M}] {username} — {self.get_action_display()}'
