"""
Vues — Module Attendance (Smart Pointage Sécurisé).
GPS Géofencing + Device Fingerprinting anti-fraude.
"""

import json
import logging

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from attendance.models import (
    Attendance, AttendanceStatus, DeviceRegistration, FailureReason, Office,
)

logger = logging.getLogger(__name__)
User = get_user_model()


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _find_nearest_office(lat: float, lon: float):
    """Retourne (office, distance_m) le plus proche, ou (None, None)."""
    offices = Office.objects.filter(is_active=True)
    nearest, min_dist = None, float('inf')
    for office in offices:
        dist = office.distance_from(lat, lon)
        if dist < min_dist:
            min_dist = dist
            nearest = office
    return (nearest, min_dist) if nearest else (None, None)


def _calculate_streak(user) -> int:
    """Calcule le nombre de jours consécutifs de présence (jusqu'à aujourd'hui)."""
    today = timezone.localdate()
    streak = 0
    day = today
    while True:
        exists = Attendance.objects.filter(
            user=user,
            date=day,
            status__in=[AttendanceStatus.PRESENT, AttendanceStatus.LATE],
        ).exists()
        if not exists:
            break
        streak += 1
        from datetime import timedelta
        day -= timedelta(days=1)
    return streak


def _async_log(user_id, status, failure_reason='', latitude=None, longitude=None,
               device_fingerprint='', ip_address='', office_id=None,
               distance_meters=None, is_suspicious=False):
    """Déclenche la tâche Celery d'enregistrement asynchrone."""
    from attendance.tasks import log_attendance_attempt_async
    log_attendance_attempt_async.delay(
        user_id=user_id,
        status=status,
        failure_reason=failure_reason,
        latitude=latitude,
        longitude=longitude,
        device_fingerprint=device_fingerprint,
        ip_address=ip_address,
        office_id=office_id,
        distance_meters=distance_meters,
        is_suspicious=is_suspicious,
    )


def _get_client_ip(request) -> str:
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if forwarded:
        return forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '')


# ─────────────────────────────────────────────────────────────────────────────
# VUE 1 : Page d'accueil pointage
# ─────────────────────────────────────────────────────────────────────────────

@login_required
def attendance_home(request):
    """
    Page principale du module pointage.
    Affiche le statut du jour, le bouton de pointage GPS, et l'historique 30j.
    """
    today = timezone.localdate()
    user = request.user

    # Statut d'aujourd'hui
    today_record = (
        Attendance.objects
        .filter(user=user, date=today,
                status__in=[AttendanceStatus.PRESENT, AttendanceStatus.LATE])
        .select_related('office')
        .first()
    )
    already_checked_in = today_record is not None

    # Historique 30 derniers jours
    from datetime import timedelta
    since = today - timedelta(days=30)
    history = (
        Attendance.objects
        .filter(user=user, date__gte=since)
        .select_related('office')
        .order_by('-date', '-check_in_time')
    )

    streak = _calculate_streak(user)

    # Sites actifs (pour debug/info — coords envoyées au JS)
    offices = list(
        Office.objects.filter(is_active=True).values(
            'id', 'name', 'latitude', 'longitude', 'allowed_radius_meters'
        )
    )

    context = {
        'today': today,
        'today_record': today_record,
        'already_checked_in': already_checked_in,
        'history': history,
        'streak': streak,
        'offices_json': json.dumps(offices),
    }
    return render(request, 'attendance/home.html', context)


# ─────────────────────────────────────────────────────────────────────────────
# VUE 2 : API AJAX — Pointage GPS
# ─────────────────────────────────────────────────────────────────────────────

@login_required
@require_POST
def check_in_api(request):
    """
    Endpoint AJAX (POST JSON) pour enregistrer un pointage.

    Pipeline anti-fraude en 6 étapes :
    1. Parse + validation des données GPS entrantes
    2. Vérification du doublon (déjà pointé aujourd'hui)
    3. Recherche du bureau le plus proche (Haversine)
    4. Vérification du rayon géofencing
    5. Vérification des horaires autorisés
    6. Vérification du device fingerprint (conflit multi-compte)
    """
    user = request.user
    ip = _get_client_ip(request)

    # ── Parse JSON ────────────────────────────────────────────────────────────
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'success': False, 'error': _('Données invalides.')}, status=400)

    try:
        lat = float(data['latitude'])
        lon = float(data['longitude'])
    except (KeyError, TypeError, ValueError):
        return JsonResponse({
            'success': False,
            'error': _('Coordonnées GPS manquantes ou invalides.'),
        }, status=400)

    device_fingerprint = str(data.get('device_fingerprint', ''))[:64]

    # ── Étape 1 : Déjà pointé ─────────────────────────────────────────────────
    if Attendance.has_checked_in_today(user):
        return JsonResponse({
            'success': False,
            'already_checked': True,
            'error': _('Vous avez déjà pointé aujourd\'hui.'),
        })

    # ── Étape 2 : Bureau le plus proche ───────────────────────────────────────
    office, distance_m = _find_nearest_office(lat, lon)
    if office is None:
        _async_log(user.id, AttendanceStatus.FAILED,
                   failure_reason=FailureReason.OUT_OF_RANGE,
                   latitude=lat, longitude=lon,
                   device_fingerprint=device_fingerprint, ip_address=ip)
        return JsonResponse({
            'success': False,
            'error': _('Aucun site de travail actif trouvé.'),
        })

    # ── Étape 3 : Géofencing ──────────────────────────────────────────────────
    if distance_m > office.allowed_radius_meters:
        _async_log(user.id, AttendanceStatus.FAILED,
                   failure_reason=FailureReason.OUT_OF_RANGE,
                   latitude=lat, longitude=lon,
                   device_fingerprint=device_fingerprint, ip_address=ip,
                   office_id=office.pk, distance_meters=distance_m)
        return JsonResponse({
            'success': False,
            'error': _(
                'Vous êtes trop loin du bureau %(name)s (%(dist)dm > %(max)dm autorisés).'
            ) % {
                'name': office.name,
                'dist': int(distance_m),
                'max': office.allowed_radius_meters,
            },
        })

    # ── Étape 4 : Horaires autorisés ──────────────────────────────────────────
    now_local = timezone.localtime(timezone.now())
    current_hour = now_local.hour

    if not (office.check_in_start_hour <= current_hour < office.check_in_end_hour):
        _async_log(user.id, AttendanceStatus.FAILED,
                   failure_reason=FailureReason.OUTSIDE_HOURS,
                   latitude=lat, longitude=lon,
                   device_fingerprint=device_fingerprint, ip_address=ip,
                   office_id=office.pk, distance_meters=distance_m)
        return JsonResponse({
            'success': False,
            'error': _(
                'Pointage autorisé entre %(start)dh00 et %(end)dh00.'
            ) % {'start': office.check_in_start_hour, 'end': office.check_in_end_hour},
        })

    # ── Étape 5 : Device Fingerprint (conflit multi-compte) ───────────────────
    is_suspicious = False
    if device_fingerprint:
        conflicting = (
            DeviceRegistration.objects
            .filter(device_fingerprint=device_fingerprint)
            .exclude(user=user)
            .select_related('user')
            .first()
        )
        if conflicting:
            is_suspicious = True
            # Enregistrer le pointage suspect puis alerter les admins
            _async_log(user.id, AttendanceStatus.SUSPICIOUS,
                       failure_reason=FailureReason.DEVICE_CONFLICT,
                       latitude=lat, longitude=lon,
                       device_fingerprint=device_fingerprint, ip_address=ip,
                       office_id=office.pk, distance_meters=distance_m,
                       is_suspicious=True)
            # Alerte email admin (Celery)
            from attendance.tasks import alert_suspicious_checkin
            # L'alerte sera déclenchée après la création de l'enregistrement
            # (tâche séparée via signal ou post-create — on utilise un délai)
            return JsonResponse({
                'success': False,
                'suspicious': True,
                'error': _(
                    'Appareil déjà utilisé par un autre compte. '
                    'Tentative signalée aux administrateurs.'
                ),
            })

        # Enregistrer / mettre à jour l'appareil de confiance
        DeviceRegistration.objects.update_or_create(
            user=user,
            device_fingerprint=device_fingerprint,
            defaults={
                'last_seen': timezone.now(),
                'device_name': request.META.get('HTTP_USER_AGENT', '')[:200],
            },
        )

    # ── Étape 6 : Statut PRESENT ou LATE ─────────────────────────────────────
    status = (
        AttendanceStatus.LATE
        if current_hour >= office.late_after_hour
        else AttendanceStatus.PRESENT
    )

    _async_log(
        user.id, status,
        latitude=lat, longitude=lon,
        device_fingerprint=device_fingerprint, ip_address=ip,
        office_id=office.pk, distance_meters=distance_m,
        is_suspicious=False,
    )

    return JsonResponse({
        'success': True,
        'status': status,
        'status_label': AttendanceStatus(status).label,
        'office_name': office.name,
        'distance_meters': int(distance_m),
        'is_late': status == AttendanceStatus.LATE,
    })


# ─────────────────────────────────────────────────────────────────────────────
# VUE 3 : Historique complet de l'employé
# ─────────────────────────────────────────────────────────────────────────────

@login_required
def attendance_history(request):
    """Historique complet de présence de l'employé connecté."""
    records = (
        Attendance.objects
        .filter(user=request.user)
        .select_related('office')
        .order_by('-date', '-check_in_time')
    )

    # Stats globales
    total = records.count()
    present_count = records.filter(status=AttendanceStatus.PRESENT).count()
    late_count = records.filter(status=AttendanceStatus.LATE).count()
    failed_count = records.filter(
        status__in=[AttendanceStatus.FAILED, AttendanceStatus.SUSPICIOUS]
    ).count()

    context = {
        'records': records[:90],   # 3 derniers mois
        'total': total,
        'present_count': present_count,
        'late_count': late_count,
        'failed_count': failed_count,
        'streak': _calculate_streak(request.user),
    }
    return render(request, 'attendance/history.html', context)


# ─────────────────────────────────────────────────────────────────────────────
# VUE 4 : Tableau de bord Manager — présences du jour
# ─────────────────────────────────────────────────────────────────────────────

@login_required
def manager_attendance_view(request):
    """
    Vue réservée aux managers/admins.
    Affiche :
    - Récapitulatif du jour (présents, retards, absents, suspects)
    - Liste des absents (employés actifs sans pointage valide)
    - Alertes de pointages suspects
    """
    if not (request.user.is_staff or request.user.is_superuser):
        messages.error(request, _('Accès réservé aux managers.'))
        return redirect('attendance:home')

    today = timezone.localdate()

    today_records = (
        Attendance.objects
        .filter(date=today)
        .select_related('user', 'office')
        .order_by('-check_in_time')
    )

    present_ids = set(
        today_records
        .filter(status=AttendanceStatus.PRESENT)
        .values_list('user_id', flat=True)
    )
    late_ids = set(
        today_records
        .filter(status=AttendanceStatus.LATE)
        .values_list('user_id', flat=True)
    )
    suspicious_records = today_records.filter(is_suspicious=True)
    checked_ids = present_ids | late_ids

    all_employees = User.objects.filter(is_active=True, is_staff=False)
    absent_employees = all_employees.exclude(pk__in=checked_ids)

    context = {
        'today': today,
        'today_records': today_records,
        'present_count': len(present_ids),
        'late_count': len(late_ids),
        'absent_count': absent_employees.count(),
        'suspicious_count': suspicious_records.count(),
        'absent_employees': absent_employees.order_by('last_name', 'first_name'),
        'suspicious_records': suspicious_records,
    }
    return render(request, 'attendance/manager.html', context)
