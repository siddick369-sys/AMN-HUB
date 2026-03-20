"""
Modèles — Module Attendance (Smart Pointage Sécurisé).
Géofencing GPS + Device Fingerprinting anti-fraude.
"""

import math
from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

User = settings.AUTH_USER_MODEL


class AttendanceStatus(models.TextChoices):
    PRESENT    = 'PRESENT',    _('Présent')
    LATE       = 'LATE',       _('En retard')
    SUSPICIOUS = 'SUSPICIOUS', _('Suspect')
    FAILED     = 'FAILED',     _('Échoué')
    ABSENT     = 'ABSENT',     _('Absent')


class FailureReason(models.TextChoices):
    OUT_OF_RANGE      = 'OUT_OF_RANGE',      _('Hors zone autorisée')
    DEVICE_MISMATCH   = 'DEVICE_MISMATCH',   _('Appareil non reconnu')
    DEVICE_CONFLICT   = 'DEVICE_CONFLICT',   _('Appareil utilisé par un autre compte')
    ALREADY_CHECKED   = 'ALREADY_CHECKED',   _('Déjà pointé aujourd\'hui')
    GPS_UNAVAILABLE   = 'GPS_UNAVAILABLE',   _('GPS indisponible')
    OUTSIDE_HOURS     = 'OUTSIDE_HOURS',     _('Hors horaires autorisés')


# ─────────────────────────────────────────────────────────────────────────────
# MODÈLE 1 : Office (Site de travail AMN)
# ─────────────────────────────────────────────────────────────────────────────

class Office(models.Model):
    """
    Site de travail AMN avec coordonnées GPS et rayon géofencing.
    Les employés ne peuvent pointer que s'ils se trouvent dans le rayon autorisé.
    """
    name = models.CharField(
        max_length=150,
        verbose_name=_('Nom du site')
    )
    address = models.CharField(
        max_length=300,
        blank=True,
        verbose_name=_('Adresse')
    )
    country = models.CharField(
        max_length=2,
        default='CM',
        verbose_name=_('Pays')
    )
    latitude = models.FloatField(
        verbose_name=_('Latitude GPS'),
        help_text=_('ex: 3.8480 pour Yaoundé')
    )
    longitude = models.FloatField(
        verbose_name=_('Longitude GPS'),
        help_text=_('ex: 11.5021 pour Yaoundé')
    )
    # Rayon en mètres dans lequel le pointage est autorisé
    allowed_radius_meters = models.PositiveIntegerField(
        default=200,
        verbose_name=_('Rayon autorisé (mètres)'),
        help_text=_('Distance maximale depuis le bureau pour pointer (défaut : 200m)')
    )
    # Horaires autorisés pour le pointage
    check_in_start_hour = models.PositiveIntegerField(
        default=6,
        verbose_name=_('Heure d\'ouverture pointage'),
        help_text=_('Heure à partir de laquelle le pointage est autorisé (ex: 6 → 06:00)')
    )
    check_in_end_hour = models.PositiveIntegerField(
        default=12,
        verbose_name=_('Heure de fermeture pointage'),
        help_text=_('Heure limite pour pointer (ex: 12 → 12:00)')
    )
    late_after_hour = models.PositiveIntegerField(
        default=9,
        verbose_name=_('Retard après (heure)'),
        help_text=_('Un pointage après cette heure est marqué EN RETARD')
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name=_('Actif')
    )

    class Meta:
        verbose_name = _('Site AMN')
        verbose_name_plural = _('Sites AMN')
        ordering = ['name']

    def __str__(self):
        return f'{self.name} ({self.country})'

    def distance_from(self, lat: float, lon: float) -> float:
        """
        Calcule la distance en mètres entre deux points GPS
        via la formule de Haversine.

        Args:
            lat : latitude de l'employé
            lon : longitude de l'employé

        Returns:
            Distance en mètres (float)
        """
        R = 6_371_000  # Rayon de la Terre en mètres

        lat1, lon1 = math.radians(self.latitude), math.radians(self.longitude)
        lat2, lon2 = math.radians(lat), math.radians(lon)

        dlat = lat2 - lat1
        dlon = lon2 - lon1

        a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

        return R * c

    def is_within_range(self, lat: float, lon: float) -> bool:
        """Retourne True si les coordonnées sont dans le rayon autorisé."""
        return self.distance_from(lat, lon) <= self.allowed_radius_meters


# ─────────────────────────────────────────────────────────────────────────────
# MODÈLE 2 : DeviceRegistration (Empreinte appareil)
# ─────────────────────────────────────────────────────────────────────────────

class DeviceRegistration(models.Model):
    """
    Enregistrement de l'empreinte numérique d'un appareil pour un employé.
    Permet d'éviter le partage de compte (anti-fraude).

    L'empreinte est calculée côté client (JS) à partir de :
    - User-Agent, résolution écran, timezone, langue, hardware concurrency.
    """
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='registered_devices',
        verbose_name=_('Employé')
    )
    device_fingerprint = models.CharField(
        max_length=64,
        verbose_name=_('Empreinte appareil'),
        help_text=_('Hash SHA-256 des caractéristiques de l\'appareil')
    )
    device_name = models.CharField(
        max_length=200,
        blank=True,
        verbose_name=_('Nom de l\'appareil'),
        help_text=_('User-Agent abrégé pour identification visuelle')
    )
    first_seen = models.DateTimeField(
        default=timezone.now,
        verbose_name=_('Premier pointage')
    )
    last_seen = models.DateTimeField(
        default=timezone.now,
        verbose_name=_('Dernier pointage')
    )
    is_trusted = models.BooleanField(
        default=True,
        verbose_name=_('Approuvé')
    )

    class Meta:
        verbose_name = _('Appareil enregistré')
        verbose_name_plural = _('Appareils enregistrés')
        unique_together = [('user', 'device_fingerprint')]

    def __str__(self):
        return f'{self.user.username} — {self.device_name[:50]}'


# ─────────────────────────────────────────────────────────────────────────────
# MODÈLE 3 : Attendance (Pointage quotidien)
# ─────────────────────────────────────────────────────────────────────────────

class Attendance(models.Model):
    """
    Enregistrement d'un pointage avec toutes les données anti-fraude.

    Chaque ligne = une tentative de pointage (réussie ou non).
    Une seule entrée PRESENT/LATE est autorisée par employé par jour.
    """
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='attendances',
        verbose_name=_('Employé')
    )
    office = models.ForeignKey(
        Office,
        on_delete=models.SET_NULL,
        null=True,
        related_name='attendances',
        verbose_name=_('Site')
    )

    # ── Temporel ──────────────────────────────────────────────────────────
    date = models.DateField(
        default=timezone.now,
        db_index=True,
        verbose_name=_('Date')
    )
    check_in_time = models.DateTimeField(
        default=timezone.now,
        verbose_name=_('Heure de pointage')
    )

    # ── Localisation GPS ──────────────────────────────────────────────────
    latitude = models.FloatField(
        null=True, blank=True,
        verbose_name=_('Latitude réelle')
    )
    longitude = models.FloatField(
        null=True, blank=True,
        verbose_name=_('Longitude réelle')
    )
    distance_meters = models.FloatField(
        null=True, blank=True,
        verbose_name=_('Distance du bureau (mètres)')
    )

    # ── Anti-fraude ───────────────────────────────────────────────────────
    device_fingerprint = models.CharField(
        max_length=64,
        blank=True,
        verbose_name=_('Empreinte appareil')
    )
    ip_address = models.GenericIPAddressField(
        null=True, blank=True,
        verbose_name=_('Adresse IP')
    )

    # ── Statut ────────────────────────────────────────────────────────────
    status = models.CharField(
        max_length=15,
        choices=AttendanceStatus.choices,
        default=AttendanceStatus.PRESENT,
        verbose_name=_('Statut')
    )
    failure_reason = models.CharField(
        max_length=25,
        choices=FailureReason.choices,
        blank=True,
        verbose_name=_('Raison d\'échec')
    )
    is_suspicious = models.BooleanField(
        default=False,
        verbose_name=_('Suspect'),
        help_text=_('Signalé automatiquement si le device fingerprint est partagé')
    )
    admin_note = models.TextField(
        blank=True,
        verbose_name=_('Note admin')
    )

    class Meta:
        verbose_name = _('Pointage')
        verbose_name_plural = _('Pointages')
        ordering = ['-check_in_time']
        indexes = [
            models.Index(fields=['user', 'date']),
            models.Index(fields=['date', 'status']),
            models.Index(fields=['device_fingerprint']),
        ]

    def __str__(self):
        return f'{self.user} — {self.date} [{self.get_status_display()}]'

    @classmethod
    def has_checked_in_today(cls, user) -> bool:
        """Vérifie si l'employé a déjà pointé aujourd'hui (statut valide)."""
        today = timezone.localdate()
        return cls.objects.filter(
            user=user,
            date=today,
            status__in=[AttendanceStatus.PRESENT, AttendanceStatus.LATE]
        ).exists()


# ─────────────────────────────────────────────────────────────────────────────
# MODÈLE 4 : AttendanceReport (Rapport RH quotidien)
# ─────────────────────────────────────────────────────────────────────────────

class AttendanceReport(models.Model):
    """
    Rapport de présence quotidien généré automatiquement par Celery.
    Stocke un résumé JSON pour consultation rapide par les RH.
    """
    date = models.DateField(
        unique=True,
        verbose_name=_('Date')
    )
    total_employees = models.PositiveIntegerField(default=0)
    present_count   = models.PositiveIntegerField(default=0)
    late_count      = models.PositiveIntegerField(default=0)
    absent_count    = models.PositiveIntegerField(default=0)
    suspicious_count = models.PositiveIntegerField(default=0)
    report_data     = models.JSONField(
        default=dict,
        verbose_name=_('Données détaillées')
    )
    generated_at    = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Rapport de présence')
        verbose_name_plural = _('Rapports de présence')
        ordering = ['-date']

    def __str__(self):
        return f'Rapport {self.date} — {self.present_count}/{self.total_employees} présents'
