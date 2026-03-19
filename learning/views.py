"""
Vues — Module Learning (Onboarding Navigator + Enterprise LMS).
Toutes les requêtes DB sont optimisées (select_related, prefetch_related, annotate).
"""

import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Count, Q, Prefetch
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_http_methods, require_POST

from .models import (
    BuddyAssignment, Certificate, Choice, Course, Lesson, LearningPath,
    OnboardingJourney, OnboardingStep, OnboardingTask, OnboardingTaskCompletion,
    PathEnrollment, Question, Quiz, QuizAttempt, UserProgress,
)

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _is_manager(user):
    return user.is_staff or user.is_superuser


def _get_low_data_mode(request):
    return request.session.get('low_data_mode', False)


# ─────────────────────────────────────────────────────────────────────────────
# VUE 1 : Dashboard Onboarding — Timeline verticale
# ─────────────────────────────────────────────────────────────────────────────

@login_required
@require_http_methods(['GET'])
def onboarding_dashboard(request):
    """
    Dashboard "My Journey" — Timeline verticale des étapes d'intégration.

    Optimisation N+1 :
      - select_related('employee') sur le journey
      - prefetch_related sur steps → tasks → meet_colleague
      - set des IDs complétés pour lookup O(1)

    Logique de déblocage :
      Une étape est débloquée si day_number <= jours depuis started_at.
    """
    user = request.user

    journey, _ = OnboardingJourney.objects.select_related('employee').get_or_create(
        employee=user
    )

    days_elapsed = journey.days_since_start

    # Toutes les complétions de cet utilisateur (1 requête)
    completed_task_ids = set(
        OnboardingTaskCompletion.objects.filter(
            employee=user, is_completed=True
        ).values_list('task_id', flat=True)
    )

    # Étapes + tâches + collègues (3 requêtes max grâce à prefetch)
    steps = (
        OnboardingStep.objects
        .filter(journey=journey)
        .order_by('day_number')
        .prefetch_related(
            Prefetch(
                'tasks',
                queryset=OnboardingTask.objects.order_by('order').select_related(
                    'meet_colleague'
                )
            )
        )
    )

    steps_data = []
    for step in steps:
        is_unlocked = step.day_number <= days_elapsed
        is_today    = step.day_number == days_elapsed
        tasks       = list(step.tasks.all())
        tasks_done  = sum(1 for t in tasks if t.pk in completed_task_ids)

        steps_data.append({
            'step':        step,
            'is_unlocked': is_unlocked,
            'is_today':    is_today,
            'is_future':   not is_unlocked,
            'tasks':       tasks,
            'tasks_total': len(tasks),
            'tasks_done':  tasks_done,
            'all_done':    tasks_done == len(tasks) and len(tasks) > 0,
        })

    buddy_assignment = None
    try:
        buddy_assignment = (
            BuddyAssignment.objects
            .select_related('buddy')
            .get(new_employee=user)
        )
    except BuddyAssignment.DoesNotExist:
        pass

    return render(request, 'learning/onboarding_dashboard.html', {
        'journey':          journey,
        'steps_data':       steps_data,
        'days_elapsed':     days_elapsed,
        'buddy_assignment': buddy_assignment,
        'completed_ids':    completed_task_ids,
        'progress':         journey.progress_percentage,
    })


# ─────────────────────────────────────────────────────────────────────────────
# VUE 2 : Marquer une tâche d'onboarding (AJAX)
# ─────────────────────────────────────────────────────────────────────────────

@login_required
@require_POST
def complete_onboarding_task(request, task_id):
    """Marque une tâche d'intégration comme complétée (POST/AJAX)."""
    task = get_object_or_404(OnboardingTask, pk=task_id)

    if task.step.journey.employee != request.user:
        return JsonResponse({'error': 'Forbidden'}, status=403)

    if not task.step.is_unlocked():
        return JsonResponse({'error': str(_('Étape non débloquée'))}, status=400)

    completion, _ = OnboardingTaskCompletion.objects.get_or_create(
        employee=request.user,
        task=task,
    )
    completion.mark_complete()

    return JsonResponse({
        'success':  True,
        'task_id':  task_id,
        'progress': task.step.journey.progress_percentage,
    })


# ─────────────────────────────────────────────────────────────────────────────
# VUE 3 : Dashboard LMS
# ─────────────────────────────────────────────────────────────────────────────

@login_required
@require_http_methods(['GET'])
def lms_dashboard(request):
    """
    Dashboard LMS — grille de parcours avec progression et mode Low-Data.

    Optimisation N+1 :
      - prefetch courses → lessons en une requête groupée
      - completed_lesson_ids : set pour lookup O(1) sans sous-requête par parcours
    """
    user     = request.user
    low_data = _get_low_data_mode(request)

    enrollments = (
        PathEnrollment.objects
        .filter(user=user, is_active=True)
        .select_related('path')
        .prefetch_related(
            Prefetch(
                'path__courses',
                queryset=Course.objects.filter(is_active=True).order_by('order')
                .prefetch_related(
                    Prefetch('lessons', queryset=Lesson.objects.order_by('order'))
                )
            )
        )
    )

    # IDs des leçons complétées (1 requête)
    completed_lesson_ids = set(
        UserProgress.objects.filter(user=user, is_completed=True)
        .values_list('lesson_id', flat=True)
    )

    paths_data = []
    for enrollment in enrollments:
        path = enrollment.path
        all_lessons = [
            lesson
            for course in path.courses.all()
            for lesson in course.lessons.all()
        ]
        total    = len(all_lessons)
        done     = sum(1 for l in all_lessons if l.pk in completed_lesson_ids)
        progress = int((done / total) * 100) if total > 0 else 0

        paths_data.append({
            'enrollment': enrollment,
            'path':       path,
            'progress':   progress,
            'total':      total,
            'done':       done,
            'courses':    list(path.courses.all()),
        })

    certificates = (
        Certificate.objects
        .filter(user=user)
        .select_related('path')
        .order_by('-issued_at')
    )

    return render(request, 'learning/lms_dashboard.html', {
        'paths_data':   paths_data,
        'certificates': certificates,
        'low_data':     low_data,
    })


# ─────────────────────────────────────────────────────────────────────────────
# VUE 4 : Toggle Mode Low-Data
# ─────────────────────────────────────────────────────────────────────────────

@login_required
@require_POST
def toggle_low_data_mode(request):
    """Bascule le mode Low-Data (économie de données) en session."""
    current = request.session.get('low_data_mode', False)
    request.session['low_data_mode'] = not current
    return JsonResponse({'low_data': not current})


# ─────────────────────────────────────────────────────────────────────────────
# VUE 5 : Détail d'un cours
# ─────────────────────────────────────────────────────────────────────────────

@login_required
@require_http_methods(['GET'])
def course_detail(request, course_id):
    """Leçons d'un cours avec état de complétion. Masquage VIDEO en Low-Data."""
    course = get_object_or_404(
        Course.objects.select_related('path').prefetch_related('lessons'),
        pk=course_id, is_active=True
    )

    is_enrolled = PathEnrollment.objects.filter(
        user=request.user, path=course.path, is_active=True
    ).exists()
    if not is_enrolled:
        messages.error(request, _('Vous n\'êtes pas inscrit à ce parcours.'))
        return redirect('learning:lms_dashboard')

    low_data = _get_low_data_mode(request)
    lessons  = course.lessons.order_by('order')

    completed_ids = set(
        UserProgress.objects.filter(
            user=request.user, lesson__in=lessons, is_completed=True
        ).values_list('lesson_id', flat=True)
    )

    lessons_data = [
        {
            'lesson':      lesson,
            'is_complete': lesson.pk in completed_ids,
            'is_hidden':   low_data and not lesson.is_low_data_friendly,
        }
        for lesson in lessons
    ]

    quiz = getattr(course, 'quiz', None)
    best_attempt = None
    if quiz:
        best_attempt = (
            QuizAttempt.objects
            .filter(user=request.user, quiz=quiz)
            .order_by('-score_percentage')
            .first()
        )

    return render(request, 'learning/course_detail.html', {
        'course':       course,
        'lessons_data': lessons_data,
        'low_data':     low_data,
        'quiz':         quiz,
        'best_attempt': best_attempt,
    })


# ─────────────────────────────────────────────────────────────────────────────
# VUE 6 : Détail d'une leçon
# ─────────────────────────────────────────────────────────────────────────────

@login_required
@require_http_methods(['GET', 'POST'])
def lesson_detail(request, lesson_id):
    """Affiche le contenu d'une leçon. POST → marque comme terminée."""
    lesson = get_object_or_404(
        Lesson.objects.select_related('course__path'),
        pk=lesson_id
    )

    is_enrolled = PathEnrollment.objects.filter(
        user=request.user, path=lesson.course.path, is_active=True
    ).exists()
    if not is_enrolled:
        messages.error(request, _('Accès non autorisé.'))
        return redirect('learning:lms_dashboard')

    progress, _ = UserProgress.objects.get_or_create(
        user=request.user, lesson=lesson
    )

    if request.method == 'POST':
        if not progress.is_completed:
            progress.mark_complete()
            messages.success(request, _('Leçon terminée !'))
            from learning.tasks import check_path_completion
            check_path_completion.delay(request.user.pk, lesson.course.path.pk)
        return redirect('learning:course_detail', course_id=lesson.course.pk)

    siblings = list(Lesson.objects.filter(course=lesson.course).order_by('order'))
    idx = next((i for i, l in enumerate(siblings) if l.pk == lesson.pk), 0)

    return render(request, 'learning/lesson_detail.html', {
        'lesson':      lesson,
        'progress':    progress,
        'prev_lesson': siblings[idx - 1] if idx > 0 else None,
        'next_lesson': siblings[idx + 1] if idx < len(siblings) - 1 else None,
        'low_data':    _get_low_data_mode(request),
    })


# ─────────────────────────────────────────────────────────────────────────────
# VUE 7 : Quiz gamifié
# ─────────────────────────────────────────────────────────────────────────────

@login_required
@require_http_methods(['GET', 'POST'])
def quiz_view(request, quiz_id):
    """
    Quiz plein écran avec retour visuel immédiat.
    GET  → affiche les questions.
    POST → évalue, crée QuizAttempt, déclenche check_path_completion si réussi.
    """
    quiz = get_object_or_404(
        Quiz.objects.select_related('course__path').prefetch_related(
            Prefetch(
                'questions',
                queryset=Question.objects.order_by('order').prefetch_related('choices')
            )
        ),
        pk=quiz_id
    )

    is_enrolled = PathEnrollment.objects.filter(
        user=request.user, path=quiz.course.path, is_active=True
    ).exists()
    if not is_enrolled:
        messages.error(request, _('Accès non autorisé.'))
        return redirect('learning:lms_dashboard')

    attempts_count = QuizAttempt.objects.filter(user=request.user, quiz=quiz).count()
    best_attempt   = (
        QuizAttempt.objects
        .filter(user=request.user, quiz=quiz)
        .order_by('-score_percentage')
        .first()
    )

    if attempts_count >= quiz.max_attempts and not (best_attempt and best_attempt.passed):
        messages.error(request, _(f'Nombre maximum de tentatives atteint.'))
        return redirect('learning:course_detail', course_id=quiz.course.pk)

    if request.method == 'POST':
        questions   = list(quiz.questions.prefetch_related('choices').all())
        correct     = 0
        answers_log = {}

        for question in questions:
            submitted     = request.POST.getlist(f'question_{question.pk}')
            submitted_ids = [int(x) for x in submitted if x.isdigit()]
            answers_log[str(question.pk)] = submitted_ids

            correct_ids = set(
                question.choices.filter(is_correct=True).values_list('id', flat=True)
            )
            if set(submitted_ids) == correct_ids:
                correct += 1

        total   = len(questions)
        score   = (correct / total * 100) if total > 0 else 0
        passed  = score >= quiz.passing_score_percentage

        attempt = QuizAttempt.objects.create(
            user=request.user, quiz=quiz,
            score_percentage=score, passed=passed, answers=answers_log,
        )

        if passed:
            from learning.tasks import check_path_completion
            check_path_completion.delay(request.user.pk, quiz.course.path.pk)

        return render(request, 'learning/quiz_result.html', {
            'quiz':      quiz,
            'attempt':   attempt,
            'score':     score,
            'passed':    passed,
            'correct':   correct,
            'total':     total,
            'threshold': quiz.passing_score_percentage,
        })

    return render(request, 'learning/quiz.html', {
        'quiz':          quiz,
        'attempts_done': attempts_count,
        'attempts_left': quiz.max_attempts - attempts_count,
        'best_attempt':  best_attempt,
    })


# ─────────────────────────────────────────────────────────────────────────────
# VUE 8 : Manager Dashboard
# ─────────────────────────────────────────────────────────────────────────────

@login_required
@user_passes_test(_is_manager, login_url='/auth/login/')
@require_http_methods(['GET'])
def manager_dashboard(request):
    """
    Tableau de bord managers — jauges de progression d'équipe.

    Optimisation N+1 :
      - annotate() pour calculer lessons_done, quiz_passed, certs_earned
        en une seule requête SQL avec GROUP BY.
      - Évite toute boucle Python pour calculer les agrégats.
    """
    from django.contrib.auth import get_user_model
    User = get_user_model()

    manager_dept = getattr(request.user, 'department', None)

    employees_qs = User.objects.filter(is_active=True).exclude(pk=request.user.pk)
    if manager_dept and not request.user.is_superuser:
        employees_qs = employees_qs.filter(department=manager_dept)

    # 1 requête SQL avec 3 agrégats via annotate (pas de N+1)
    employees = employees_qs.annotate(
        lessons_done=Count(
            'lesson_progress',
            filter=Q(lesson_progress__is_completed=True),
            distinct=True,
        ),
        quiz_passed=Count(
            'quiz_attempts',
            filter=Q(quiz_attempts__passed=True),
            distinct=True,
        ),
        certs_earned=Count('certificates', distinct=True),
    ).order_by('last_name', 'first_name')

    # Parcours actifs du département
    paths_filter = {'is_active': True}
    if manager_dept and not request.user.is_superuser:
        paths_filter['target_department'] = manager_dept

    paths = LearningPath.objects.filter(**paths_filter).annotate(
        total_enrollments=Count('enrollments', distinct=True),
        completed_certs=Count('certificates', distinct=True),
    )

    # Onboarding : récupérer les journeys de l'équipe
    onboarding_journeys = (
        OnboardingJourney.objects
        .filter(employee__in=employees_qs)
        .select_related('employee')
        .annotate(
            tasks_done=Count(
                'employee__task_completions',
                filter=Q(employee__task_completions__is_completed=True),
                distinct=True,
            )
        )
    )

    return render(request, 'learning/manager_dashboard.html', {
        'employees':          employees,
        'total_employees':    employees.count(),
        'paths':              paths,
        'onboarding_journeys': onboarding_journeys,
        'manager_dept':       manager_dept,
    })


# ─────────────────────────────────────────────────────────────────────────────
# VUE 9 : Certificat public
# ─────────────────────────────────────────────────────────────────────────────

@require_http_methods(['GET'])
def certificate_verify(request, unique_code):
    """Vérification publique d'un certificat via son code unique."""
    certificate = get_object_or_404(
        Certificate.objects.select_related('user', 'path'),
        unique_code=unique_code.upper()
    )
    return render(request, 'learning/certificate_verify.html', {
        'certificate': certificate,
    })
