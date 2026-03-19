"""
Tâches Celery asynchrones — Module Learning, AMN Employee Hub.

Tâches :
  1. unlock_daily_steps          — Drip content onboarding (planifiée quotidiennement)
  2. send_buddy_notification_email — Notifie le Buddy d'une nouvelle assignation
  3. generate_certificate_pdf    — Génère le PDF du certificat de réussite
  4. check_path_completion       — Vérifie si un parcours est terminé après chaque quiz
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
# HELPER : envoi email HTML
# ─────────────────────────────────────────────────────────────────────────────

def _send_html_email(subject, template_name, context, recipient_email):
    html_content = render_to_string(f'emails/{template_name}', context)
    text_content = strip_tags(html_content)
    try:
        send_mail(
            subject=subject,
            message=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[recipient_email],
            html_message=html_content,
            fail_silently=False,
        )
        logger.info(f'[AMN Mail] Envoyé → {recipient_email}')
        return True
    except Exception as exc:
        logger.error(f'[AMN Mail] Échec → {recipient_email} : {exc}')
        raise


# ─────────────────────────────────────────────────────────────────────────────
# TÂCHE 1 : Drip Content — Déblocage quotidien des étapes d'onboarding
# ─────────────────────────────────────────────────────────────────────────────

@shared_task(name='learning.unlock_daily_steps')
def unlock_daily_steps():
    """
    Tâche planifiée (Celery Beat) — à exécuter chaque jour à 08h00.

    Algorithme :
      Pour chaque OnboardingJourney actif (non terminé) :
        1. Calcule le nombre de jours depuis started_at.
        2. Trouve les étapes dont day_number == jours_écoulés (nouvelles du jour).
        3. Si de nouvelles étapes existent → envoie un email de notification.

    Note : on cible uniquement les étapes du JOUR EXACT pour éviter
    de renvoyer des notifications pour des étapes déjà débloquées.
    """
    from learning.models import OnboardingJourney, OnboardingStep

    now = timezone.now()
    # Sélectionner les parcours non terminés avec l'employé associé
    journeys = (
        OnboardingJourney.objects
        .filter(is_completed=False)
        .select_related('employee')
    )

    total_notified = 0

    for journey in journeys:
        days_elapsed = (now - journey.started_at).days

        # Étapes qui se débloquent exactement aujourd'hui
        new_steps = OnboardingStep.objects.filter(
            journey=journey,
            day_number=days_elapsed,
        ).prefetch_related('tasks')

        if not new_steps.exists():
            continue

        # Activer la langue de l'employé pour les traductions
        lang = getattr(journey.employee, 'preferred_language', 'fr') or 'fr'
        activate(lang)

        context = {
            'user': journey.employee,
            'new_steps': list(new_steps),
            'days_elapsed': days_elapsed,
            'journey_url': f'{settings.FRONTEND_URL}/learning/onboarding/',
            'app_name': 'AMN Employee Hub',
        }

        try:
            _send_html_email(
                subject=_('AMN Hub — Nouvelles étapes débloquées aujourd\'hui !'),
                template_name='onboarding_unlocked.html',
                context=context,
                recipient_email=journey.employee.email,
            )
            total_notified += 1
        except Exception as exc:
            logger.error(
                f'[AMN Onboarding] Échec mail unlock pour {journey.employee.email}: {exc}'
            )

    logger.info(f'[AMN Onboarding] Drip content exécuté : {total_notified} notification(s) envoyée(s).')
    return total_notified


# ─────────────────────────────────────────────────────────────────────────────
# TÂCHE 2 : Notification email au Buddy
# ─────────────────────────────────────────────────────────────────────────────

@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    name='learning.send_buddy_notification_email'
)
def send_buddy_notification_email(self, assignment_id):
    """
    Envoie un email au Buddy pour lui signaler sa nouvelle mission de mentorat.
    Déclenché via signal post_save sur BuddyAssignment.

    Args:
        assignment_id : PK du BuddyAssignment
    """
    from learning.models import BuddyAssignment

    try:
        assignment = (
            BuddyAssignment.objects
            .select_related('new_employee', 'buddy')
            .get(pk=assignment_id)
        )
    except BuddyAssignment.DoesNotExist:
        logger.error(f'[AMN Buddy] BuddyAssignment introuvable : ID={assignment_id}')
        return

    buddy = assignment.buddy
    lang = getattr(buddy, 'preferred_language', 'fr') or 'fr'
    activate(lang)

    context = {
        'buddy': buddy,
        'new_employee': assignment.new_employee,
        'assigned_date': assignment.assigned_date,
        'onboarding_url': f'{settings.FRONTEND_URL}/learning/onboarding/',
        'app_name': 'AMN Employee Hub',
    }

    try:
        _send_html_email(
            subject=_('AMN Hub — Vous avez un nouveau filleul à accompagner'),
            template_name='buddy_assigned.html',
            context=context,
            recipient_email=buddy.email,
        )
    except Exception as exc:
        logger.error(f'[AMN Buddy] Échec notification buddy : {exc}')
        raise self.retry(exc=exc)


# ─────────────────────────────────────────────────────────────────────────────
# TÂCHE 3 : Vérification de complétion d'un parcours après un quiz
# ─────────────────────────────────────────────────────────────────────────────

@shared_task(
    bind=True,
    max_retries=2,
    name='learning.check_path_completion'
)
def check_path_completion(self, user_id, path_id):
    """
    Vérifie si un utilisateur a terminé tous les cours d'un parcours.
    Si oui : génère le certificat PDF via generate_certificate_pdf.

    Un parcours est considéré terminé si :
      - Toutes les leçons sont complétées (UserProgress)
      - Tous les quiz sont réussis (QuizAttempt.passed=True)

    Args:
        user_id : PK de l'utilisateur
        path_id : PK du LearningPath
    """
    from django.contrib.auth import get_user_model
    from learning.models import (
        LearningPath, UserProgress, QuizAttempt, Certificate, Course
    )

    User = get_user_model()

    try:
        user = User.objects.get(pk=user_id)
        path = LearningPath.objects.prefetch_related(
            'courses__lessons', 'courses__quiz'
        ).get(pk=path_id)
    except (User.DoesNotExist, LearningPath.DoesNotExist) as exc:
        logger.error(f'[AMN Certificate] Objet introuvable : {exc}')
        return

    # ── Vérifier que toutes les leçons sont complétées ────────────────────
    total_lessons = sum(
        course.lessons.count() for course in path.courses.filter(is_active=True)
    )
    completed_lessons = UserProgress.objects.filter(
        user=user,
        lesson__course__path=path,
        is_completed=True
    ).count()

    if completed_lessons < total_lessons:
        logger.debug(
            f'[AMN Certificate] Parcours incomplet pour {user.email} : '
            f'{completed_lessons}/{total_lessons} leçons'
        )
        return

    # ── Vérifier que tous les quiz sont réussis ───────────────────────────
    courses_with_quiz = path.courses.filter(is_active=True, quiz__isnull=False)
    for course in courses_with_quiz:
        passed = QuizAttempt.objects.filter(
            user=user,
            quiz=course.quiz,
            passed=True
        ).exists()
        if not passed:
            logger.debug(
                f'[AMN Certificate] Quiz non réussi : {course.title} pour {user.email}'
            )
            return

    # ── Tous les critères sont remplis : délivrer le certificat ──────────
    _, cert_created = Certificate.objects.get_or_create(
        user=user,
        path=path,
    )

    if cert_created:
        logger.info(
            f'[AMN Certificate] Certificat créé pour {user.email} — {path.title}'
        )
        # Lancer la génération PDF asynchrone
        generate_certificate_pdf.delay(user_id, path_id)
    else:
        logger.debug(f'[AMN Certificate] Certificat déjà existant pour {user.email}')


# ─────────────────────────────────────────────────────────────────────────────
# TÂCHE 4 : Génération du certificat PDF
# ─────────────────────────────────────────────────────────────────────────────

@shared_task(
    bind=True,
    max_retries=2,
    default_retry_delay=60,
    name='learning.generate_certificate_pdf'
)
def generate_certificate_pdf(self, user_id, path_id):
    """
    Génère un certificat PDF et l'envoie par email à l'utilisateur.

    La génération PDF utilise une approche HTML→text (sans dépendance
    à WeasyPrint/reportlab) pour la compatibilité maximale.
    En production, remplacer par WeasyPrint ou reportlab.

    Args:
        user_id : PK de l'utilisateur
        path_id : PK du LearningPath
    """
    from django.contrib.auth import get_user_model
    from learning.models import Certificate, LearningPath

    User = get_user_model()

    try:
        user = User.objects.get(pk=user_id)
        path = LearningPath.objects.get(pk=path_id)
        certificate = Certificate.objects.get(user=user, path=path)
    except Exception as exc:
        logger.error(f'[AMN PDF] Objet introuvable : {exc}')
        return

    lang = getattr(user, 'preferred_language', 'fr') or 'fr'
    activate(lang)

    # ── Envoi de l'email de félicitations avec lien vers le certificat ────
    context = {
        'user': user,
        'path': path,
        'certificate': certificate,
        'certificate_url': (
            f'{settings.FRONTEND_URL}/learning/certificate/{certificate.unique_code}/'
        ),
        'app_name': 'AMN Employee Hub',
        'issued_at': certificate.issued_at,
    }

    try:
        _send_html_email(
            subject=_('AMN Hub — Félicitations, votre certificat est prêt !'),
            template_name='certificate_ready.html',
            context=context,
            recipient_email=user.email,
        )
        logger.info(f'[AMN PDF] Email certificat envoyé à {user.email}')
    except Exception as exc:
        logger.error(f'[AMN PDF] Échec envoi email certificat : {exc}')
        raise self.retry(exc=exc)
