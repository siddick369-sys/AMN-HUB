"""
Signaux Django — Module Learning.

Deux signaux principaux :
1. auto_enroll_employee   : inscrit automatiquement l'employé au LearningPath
                            de son département + crée son OnboardingJourney.
2. notify_buddy_assigned  : notifie le Buddy par email via Celery lors
                            d'une nouvelle assignation de mentorat.
"""

import logging

from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# SIGNAL 1 : Inscription automatique au parcours de formation
# ─────────────────────────────────────────────────────────────────────────────

@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def auto_enroll_employee(sender, instance, created, **kwargs):
    """
    Déclenché à chaque création d'un Employee.
    Actions :
      1. Inscrit l'employé au(x) LearningPath lié(s) à son département.
      2. Crée son OnboardingJourney (s'il n'en a pas encore).

    Note : on importe les modèles ici (import local) pour éviter les
    imports circulaires au démarrage de Django.
    """
    if not created:
        return  # Ne rien faire pour les mises à jour

    from learning.models import LearningPath, PathEnrollment, OnboardingJourney

    # ── 1. Création du parcours d'intégration ───────────────────────────────
    try:
        OnboardingJourney.objects.get_or_create(employee=instance)
        logger.info(f'[AMN Learning] OnboardingJourney créé pour {instance.email}')
    except Exception as exc:
        logger.error(f'[AMN Learning] Erreur création OnboardingJourney : {exc}')

    # ── 2. Inscription aux parcours LMS du département ──────────────────────
    department = getattr(instance, 'department', None)
    if not department:
        return

    try:
        paths = LearningPath.objects.filter(
            target_department=department,
            is_active=True
        )
        enrollments_created = 0
        for path in paths:
            _, was_created = PathEnrollment.objects.get_or_create(
                user=instance,
                path=path,
                defaults={'is_active': True}
            )
            if was_created:
                enrollments_created += 1

        if enrollments_created:
            logger.info(
                f'[AMN Learning] {enrollments_created} inscription(s) créée(s) '
                f'pour {instance.email} (dép. {department})'
            )
    except Exception as exc:
        logger.error(f'[AMN Learning] Erreur auto-enrollment : {exc}')


# ─────────────────────────────────────────────────────────────────────────────
# SIGNAL 2 : Notification Buddy lors d'une assignation
# ─────────────────────────────────────────────────────────────────────────────

@receiver(post_save, sender='learning.BuddyAssignment')
def notify_buddy_assigned(sender, instance, created, **kwargs):
    """
    Déclenché à chaque création d'un BuddyAssignment.
    Envoie un email au Buddy via Celery pour le prévenir de sa nouvelle
    mission de mentorat, avec les infos du nouvel employé.
    """
    if not created:
        return

    if not instance.buddy:
        logger.warning(f'[AMN Learning] BuddyAssignment #{instance.pk} sans buddy assigné.')
        return

    try:
        from learning.tasks import send_buddy_notification_email
        send_buddy_notification_email.delay(instance.pk)
        logger.info(
            f'[AMN Learning] Notification buddy planifiée : '
            f'{instance.buddy.email} → mentor de {instance.new_employee.email}'
        )
    except Exception as exc:
        logger.error(f'[AMN Learning] Erreur notification buddy : {exc}')
