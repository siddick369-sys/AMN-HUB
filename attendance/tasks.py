"""
Tâches Celery — Module Attendance, AMN Employee Hub.

1. log_attendance_attempt_async  : log asynchrone chaque tentative
2. generate_daily_attendance_report : rapport RH quotidien (Celery Beat)
3. alert_suspicious_checkin     : alerte admin en cas de fraude détectée
"""

import logging
from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.html import strip_tags
from django.utils.translation import gettext as _

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# TÂCHE 1 : Log asynchrone d'une tentative de pointage
# ─────────────────────────────────────────────────────────────────────────────

@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=10,
    name='attendance.log_attendance_attempt_async'
)
def log_attendance_attempt_async(self, user_id, status, failure_reason='',
                                  latitude=None, longitude=None,
                                  device_fingerprint='', ip_address='',
                                  office_id=None, distance_meters=None,
                                  is_suspicious=False):
    """
    Crée un enregistrement Attendance de manière asynchrone.
    Appelé après chaque tentative de pointage (réussie ou non).
    """
    from attendance.models import Attendance, Office

    try:
        office = Office.objects.get(pk=office_id) if office_id else None

        Attendance.objects.create(
            user_id=user_id,
            office=office,
            date=timezone.localdate(),
            check_in_time=timezone.now(),
            latitude=latitude,
            longitude=longitude,
            distance_meters=distance_meters,
            device_fingerprint=device_fingerprint,
            ip_address=ip_address or None,
            status=status,
            failure_reason=failure_reason,
            is_suspicious=is_suspicious,
        )
        logger.info(f'[AMN Attendance] Pointage enregistré : user={user_id}, status={status}')
    except Exception as exc:
        logger.error(f'[AMN Attendance] Erreur enregistrement : {exc}')
        raise self.retry(exc=exc)


# ─────────────────────────────────────────────────────────────────────────────
# TÂCHE 2 : Alerte admin — pointage suspect
# ─────────────────────────────────────────────────────────────────────────────

@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    name='attendance.alert_suspicious_checkin'
)
def alert_suspicious_checkin(self, attendance_id):
    """
    Envoie une alerte email aux admins quand un pointage suspect est détecté
    (device fingerprint partagé entre plusieurs comptes).
    """
    from attendance.models import Attendance

    try:
        record = Attendance.objects.select_related('user', 'office').get(pk=attendance_id)
    except Attendance.DoesNotExist:
        return

    admin_emails = getattr(settings, 'ADMIN_EMAILS', [settings.DEFAULT_FROM_EMAIL])
    if isinstance(admin_emails, str):
        admin_emails = [e.strip() for e in admin_emails.split(',')]

    context = {
        'record': record,
        'user': record.user,
        'app_name': 'AMN Employee Hub',
        'admin_url': f'{settings.FRONTEND_URL}/admin/attendance/attendance/{record.pk}/change/',
    }

    html = render_to_string('emails/suspicious_checkin.html', context)
    text = strip_tags(html)

    try:
        send_mail(
            subject=f'[AMN ALERT] Pointage suspect — {record.user.username}',
            message=text,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=admin_emails,
            html_message=html,
            fail_silently=False,
        )
        logger.warning(f'[AMN Attendance] Alerte fraude envoyée pour user={record.user_id}')
    except Exception as exc:
        logger.error(f'[AMN Attendance] Échec envoi alerte : {exc}')
        raise self.retry(exc=exc)


# ─────────────────────────────────────────────────────────────────────────────
# TÂCHE 3 : Rapport de présence quotidien (Celery Beat — 18h00)
# ─────────────────────────────────────────────────────────────────────────────

@shared_task(name='attendance.generate_daily_attendance_report')
def generate_daily_attendance_report():
    """
    Tâche planifiée (Celery Beat) — exécutée chaque soir à 18h00.

    Génère un rapport de présence pour la journée :
    - Compte les présents, retards, absents, suspects
    - Crée/met à jour un AttendanceReport
    - Envoie un résumé par email aux RH

    Les absents sont identifiés comme les employés actifs sans pointage valide.
    """
    from django.contrib.auth import get_user_model
    from attendance.models import Attendance, AttendanceReport, AttendanceStatus

    User = get_user_model()
    today = timezone.localdate()

    # Récupérer tous les employés actifs
    all_employees = User.objects.filter(is_active=True, is_staff=False)
    total = all_employees.count()

    # Pointages d'aujourd'hui
    today_records = (
        Attendance.objects
        .filter(date=today)
        .select_related('user', 'office')
    )

    # Compter par statut
    present_ids    = set(today_records.filter(status=AttendanceStatus.PRESENT).values_list('user_id', flat=True))
    late_ids       = set(today_records.filter(status=AttendanceStatus.LATE).values_list('user_id', flat=True))
    suspicious_ids = set(today_records.filter(is_suspicious=True).values_list('user_id', flat=True))
    checked_ids    = present_ids | late_ids

    absent_employees = all_employees.exclude(pk__in=checked_ids)

    # Données détaillées
    report_data = {
        'present':    [{'id': uid, 'name': str(User.objects.get(pk=uid))} for uid in present_ids],
        'late':       [{'id': uid, 'name': str(User.objects.get(pk=uid))} for uid in late_ids],
        'absent':     [{'id': e.pk, 'name': str(e)} for e in absent_employees],
        'suspicious': [{'id': uid} for uid in suspicious_ids],
    }

    # Créer / mettre à jour le rapport
    report, _ = AttendanceReport.objects.update_or_create(
        date=today,
        defaults={
            'total_employees':  total,
            'present_count':    len(present_ids),
            'late_count':       len(late_ids),
            'absent_count':     absent_employees.count(),
            'suspicious_count': len(suspicious_ids),
            'report_data':      report_data,
        }
    )

    # Envoyer le rapport aux RH par email
    _send_report_email(report, absent_employees, today)

    logger.info(
        f'[AMN Rapport] {today} — {len(present_ids)} présents, '
        f'{len(late_ids)} retards, {absent_employees.count()} absents'
    )
    return report.pk


def _send_report_email(report, absent_employees, date):
    """Envoie le rapport quotidien par email aux RH et admins."""
    hr_emails = getattr(settings, 'ADMIN_EMAILS', [settings.DEFAULT_FROM_EMAIL])
    if isinstance(hr_emails, str):
        hr_emails = [e.strip() for e in hr_emails.split(',')]

    context = {
        'report': report,
        'absent_employees': absent_employees[:20],  # Limiter pour l'email
        'date': date,
        'app_name': 'AMN Employee Hub',
    }

    html = render_to_string('emails/attendance_report.html', context)
    text = strip_tags(html)

    try:
        send_mail(
            subject=f'[AMN RH] Rapport de présence du {date.strftime("%d/%m/%Y")}',
            message=text,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=hr_emails,
            html_message=html,
            fail_silently=True,
        )
    except Exception as exc:
        logger.error(f'[AMN Rapport] Échec envoi rapport RH : {exc}')
