"""
Modèles du Module 2 — Learning (Onboarding Navigator + Enterprise LMS).
Architecture hybride : gestion du temps (Onboarding) + gestion de la connaissance (LMS).
"""

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

User = settings.AUTH_USER_MODEL


# ─────────────────────────────────────────────────────────────────────────────
# CHOICES PARTAGÉS
# ─────────────────────────────────────────────────────────────────────────────

class TaskType(models.TextChoices):
    READ   = 'READ',   _('Lecture')
    WATCH  = 'WATCH',  _('Vidéo')
    MEET   = 'MEET',   _('Rencontre')
    ACTION = 'ACTION', _('Action')


class ContentType(models.TextChoices):
    VIDEO = 'VIDEO', _('Vidéo')
    AUDIO = 'AUDIO', _('Audio')
    TEXT  = 'TEXT',  _('Texte')
    PDF   = 'PDF',   _('PDF')


# ═════════════════════════════════════════════════════════════════════════════
# PARTIE 1 — ONBOARDING (Le Temps)
# ═════════════════════════════════════════════════════════════════════════════

class OnboardingJourney(models.Model):
    """
    Parcours d'intégration global assigné à un employé.
    Créé automatiquement via signal post_save sur Employee.
    """
    employee = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='onboarding_journey',
        verbose_name=_('Employé')
    )
    started_at = models.DateTimeField(
        default=timezone.now,
        verbose_name=_('Démarré le')
    )
    completed_at = models.DateTimeField(
        null=True, blank=True,
        verbose_name=_('Terminé le')
    )
    is_completed = models.BooleanField(
        default=False,
        verbose_name=_('Terminé')
    )

    class Meta:
        verbose_name = _("Parcours d'intégration")
        verbose_name_plural = _("Parcours d'intégration")

    def __str__(self):
        return f'Onboarding — {self.employee}'

    @property
    def days_since_start(self):
        """Nombre de jours depuis le début de l'intégration."""
        return (timezone.now() - self.started_at).days

    @property
    def unlocked_steps(self):
        """
        Retourne les étapes débloquées selon l'ancienneté de l'employé.
        Une étape est débloquée si day_number <= jours écoulés depuis started_at.
        """
        return self.journey_steps.filter(day_number__lte=self.days_since_start)

    @property
    def progress_percentage(self):
        """Pourcentage de complétion des tâches débloquées."""
        total = OnboardingTask.objects.filter(
            step__journey=self
        ).count()
        if total == 0:
            return 0
        done = OnboardingTaskCompletion.objects.filter(
            task__step__journey=self,
            employee=self.employee,
            is_completed=True,
        ).count()
        return int((done / total) * 100)


class OnboardingStep(models.Model):
    """
    Étape temporelle d'un parcours d'intégration.
    day_number = nombre de jours depuis l'embauche avant déblocage.
    Exemple : day_number=0 → disponible dès le 1er jour.
              day_number=7 → débloqué après 7 jours.
    """
    journey = models.ForeignKey(
        OnboardingJourney,
        on_delete=models.CASCADE,
        related_name='journey_steps',
        verbose_name=_('Parcours')
    )
    day_number = models.PositiveIntegerField(
        verbose_name=_('Jour de déblocage'),
        help_text=_('Nombre de jours depuis le début de l\'intégration avant déblocage')
    )
    title = models.CharField(
        max_length=200,
        verbose_name=_('Titre de l\'étape')
    )
    description = models.TextField(
        blank=True,
        verbose_name=_('Description')
    )
    icon = models.CharField(
        max_length=10,
        default='📋',
        verbose_name=_('Icône emoji')
    )

    class Meta:
        verbose_name = _("Étape d'intégration")
        verbose_name_plural = _("Étapes d'intégration")
        ordering = ['day_number']
        unique_together = [('journey', 'day_number')]

    def __str__(self):
        return f'J+{self.day_number} — {self.title}'

    def is_unlocked(self, for_journey=None):
        """Vérifie si cette étape est débloquée pour un parcours donné."""
        journey = for_journey or self.journey
        return journey.days_since_start >= self.day_number


class OnboardingTask(models.Model):
    """
    Action concrète à accomplir dans une étape d'intégration.
    task_type détermine l'affichage (Profile Card pour MEET, etc.)
    """
    step = models.ForeignKey(
        OnboardingStep,
        on_delete=models.CASCADE,
        related_name='tasks',
        verbose_name=_('Étape')
    )
    task_type = models.CharField(
        max_length=10,
        choices=TaskType.choices,
        default=TaskType.READ,
        verbose_name=_('Type de tâche')
    )
    title = models.CharField(
        max_length=200,
        verbose_name=_('Titre')
    )
    content = models.TextField(
        verbose_name=_('Contenu / Instructions')
    )
    # Pour les tâches MEET : référence vers un collègue
    meet_colleague = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='meet_tasks',
        verbose_name=_('Collègue à rencontrer')
    )
    order = models.PositiveIntegerField(
        default=0,
        verbose_name=_('Ordre')
    )

    class Meta:
        verbose_name = _('Tâche d\'intégration')
        verbose_name_plural = _('Tâches d\'intégration')
        ordering = ['order']

    def __str__(self):
        return f'[{self.get_task_type_display()}] {self.title}'


class OnboardingTaskCompletion(models.Model):
    """Suivi individuel de complétion des tâches d'intégration."""
    employee = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='task_completions',
        verbose_name=_('Employé')
    )
    task = models.ForeignKey(
        OnboardingTask,
        on_delete=models.CASCADE,
        related_name='completions',
        verbose_name=_('Tâche')
    )
    is_completed = models.BooleanField(
        default=False,
        verbose_name=_('Complétée')
    )
    completed_at = models.DateTimeField(
        null=True, blank=True,
        verbose_name=_('Complétée le')
    )

    class Meta:
        verbose_name = _('Complétion de tâche')
        verbose_name_plural = _('Complétions de tâches')
        unique_together = [('employee', 'task')]

    def mark_complete(self):
        self.is_completed = True
        self.completed_at = timezone.now()
        self.save(update_fields=['is_completed', 'completed_at'])


class BuddyAssignment(models.Model):
    """
    Relation de mentorat entre un nouvel employé et son parrain (Buddy).
    Déclenche une notification email via signal Celery.
    """
    new_employee = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='buddy_assignment',
        verbose_name=_('Nouvel employé')
    )
    buddy = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='mentored_employees',
        verbose_name=_('Parrain / Buddy')
    )
    assigned_date = models.DateField(
        default=timezone.now,
        verbose_name=_('Date d\'assignation')
    )
    notes = models.TextField(
        blank=True,
        verbose_name=_('Notes')
    )

    class Meta:
        verbose_name = _('Assignation Buddy')
        verbose_name_plural = _('Assignations Buddy')

    def __str__(self):
        return f'{self.new_employee} ↔ {self.buddy}'


# ═════════════════════════════════════════════════════════════════════════════
# PARTIE 2 — LMS (La Connaissance)
# ═════════════════════════════════════════════════════════════════════════════

class LearningPath(models.Model):
    """
    Parcours de formation métier lié à un département.
    Auto-assigné à l'employé lors de son inscription (signal post_save).
    """
    title = models.CharField(
        max_length=200,
        verbose_name=_('Titre du parcours')
    )
    description = models.TextField(
        blank=True,
        verbose_name=_('Description')
    )
    target_department = models.CharField(
        max_length=10,
        verbose_name=_('Département cible'),
        help_text=_('Code département (ex: TECH, HR, FINANCE...)')
    )
    thumbnail = models.ImageField(
        upload_to='learning/paths/',
        null=True, blank=True,
        verbose_name=_('Miniature')
    )
    estimated_hours = models.PositiveIntegerField(
        default=0,
        verbose_name=_('Durée estimée (heures)')
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name=_('Actif')
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Parcours de formation')
        verbose_name_plural = _('Parcours de formation')
        ordering = ['title']

    def __str__(self):
        return f'{self.title} ({self.target_department})'

    def get_progress_for_user(self, user):
        """
        Retourne le % de complétion d'un utilisateur sur ce parcours.
        Optimisé : utilise les annotations en vue pour éviter N+1.
        """
        total = Lesson.objects.filter(course__path=self).count()
        if total == 0:
            return 0
        done = UserProgress.objects.filter(
            user=user,
            lesson__course__path=self,
            is_completed=True
        ).count()
        return int((done / total) * 100)


class Course(models.Model):
    """Unité d'enseignement regroupant plusieurs leçons."""
    path = models.ForeignKey(
        LearningPath,
        on_delete=models.CASCADE,
        related_name='courses',
        verbose_name=_('Parcours')
    )
    title = models.CharField(
        max_length=200,
        verbose_name=_('Titre du cours')
    )
    description = models.TextField(
        blank=True,
        verbose_name=_('Description')
    )
    order = models.PositiveIntegerField(
        default=0,
        verbose_name=_('Ordre')
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name=_('Actif')
    )

    class Meta:
        verbose_name = _('Cours')
        verbose_name_plural = _('Cours')
        ordering = ['order']

    def __str__(self):
        return f'{self.path.title} › {self.title}'


class Lesson(models.Model):
    """
    Contenu élémentaire d'un cours.
    content_type est CRUCIAL pour le Mode Low-Data :
    les leçons VIDEO sont masquées en mode économie de données.
    """
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name='lessons',
        verbose_name=_('Cours')
    )
    title = models.CharField(
        max_length=200,
        verbose_name=_('Titre de la leçon')
    )
    content_type = models.CharField(
        max_length=10,
        choices=ContentType.choices,
        default=ContentType.TEXT,
        verbose_name=_('Type de contenu'),
        help_text=_('VIDEO masqué en mode Low-Data')
    )
    media_url = models.URLField(
        blank=True,
        verbose_name=_('URL média'),
        help_text=_('URL YouTube/Vimeo pour VIDEO, URL audio pour AUDIO')
    )
    content_text = models.TextField(
        blank=True,
        verbose_name=_('Contenu texte'),
        help_text=_('Contenu texte riche (markdown supporté)')
    )
    pdf_file = models.FileField(
        upload_to='learning/pdfs/',
        null=True, blank=True,
        verbose_name=_('Fichier PDF')
    )
    duration_minutes = models.PositiveIntegerField(
        default=5,
        verbose_name=_('Durée estimée (minutes)')
    )
    order = models.PositiveIntegerField(
        default=0,
        verbose_name=_('Ordre')
    )

    class Meta:
        verbose_name = _('Leçon')
        verbose_name_plural = _('Leçons')
        ordering = ['order']

    def __str__(self):
        return f'{self.course.title} › {self.title}'

    @property
    def is_low_data_friendly(self):
        """Retourne True si cette leçon est accessible en mode Low-Data."""
        return self.content_type in (ContentType.TEXT, ContentType.AUDIO, ContentType.PDF)


class UserProgress(models.Model):
    """
    Suivi de progression individuelle par leçon.
    Une ligne = un utilisateur + une leçon.
    """
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='lesson_progress',
        verbose_name=_('Utilisateur')
    )
    lesson = models.ForeignKey(
        Lesson,
        on_delete=models.CASCADE,
        related_name='user_progress',
        verbose_name=_('Leçon')
    )
    is_completed = models.BooleanField(
        default=False,
        verbose_name=_('Complétée')
    )
    completed_at = models.DateTimeField(
        null=True, blank=True,
        verbose_name=_('Complétée le')
    )
    time_spent_seconds = models.PositiveIntegerField(
        default=0,
        verbose_name=_('Temps passé (secondes)')
    )

    class Meta:
        verbose_name = _('Progression')
        verbose_name_plural = _('Progressions')
        unique_together = [('user', 'lesson')]
        indexes = [
            models.Index(fields=['user', 'is_completed']),
        ]

    def __str__(self):
        status = '✓' if self.is_completed else '○'
        return f'{status} {self.user} — {self.lesson.title}'

    def mark_complete(self):
        if not self.is_completed:
            self.is_completed = True
            self.completed_at = timezone.now()
            self.save(update_fields=['is_completed', 'completed_at'])


class PathEnrollment(models.Model):
    """
    Inscription d'un utilisateur à un parcours.
    Créée automatiquement via signal lors de l'inscription de l'employé.
    """
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='enrollments',
        verbose_name=_('Utilisateur')
    )
    path = models.ForeignKey(
        LearningPath,
        on_delete=models.CASCADE,
        related_name='enrollments',
        verbose_name=_('Parcours')
    )
    enrolled_at = models.DateTimeField(
        default=timezone.now,
        verbose_name=_('Inscrit le')
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name=_('Actif')
    )

    class Meta:
        verbose_name = _('Inscription')
        verbose_name_plural = _('Inscriptions')
        unique_together = [('user', 'path')]

    def __str__(self):
        return f'{self.user} → {self.path.title}'


# ─────────────────────────────────────────────────────────────────────────────
# QUIZ & VALIDATION DES ACQUIS
# ─────────────────────────────────────────────────────────────────────────────

class Quiz(models.Model):
    """
    Quiz de validation attaché à un cours.
    passing_score_percentage = seuil de réussite pour déclencher la certification.
    """
    course = models.OneToOneField(
        Course,
        on_delete=models.CASCADE,
        related_name='quiz',
        verbose_name=_('Cours')
    )
    title = models.CharField(
        max_length=200,
        verbose_name=_('Titre du quiz')
    )
    passing_score_percentage = models.PositiveIntegerField(
        default=70,
        verbose_name=_('Score minimum (%)'),
        help_text=_('Pourcentage minimum pour réussir (0-100)')
    )
    max_attempts = models.PositiveIntegerField(
        default=3,
        verbose_name=_('Tentatives maximum')
    )

    class Meta:
        verbose_name = _('Quiz')
        verbose_name_plural = _('Quiz')

    def __str__(self):
        return f'Quiz — {self.course.title}'


class Question(models.Model):
    """Question d'un quiz avec support pour QCM et QCU."""
    quiz = models.ForeignKey(
        Quiz,
        on_delete=models.CASCADE,
        related_name='questions',
        verbose_name=_('Quiz')
    )
    text = models.TextField(
        verbose_name=_('Énoncé de la question')
    )
    order = models.PositiveIntegerField(
        default=0,
        verbose_name=_('Ordre')
    )
    is_multiple_choice = models.BooleanField(
        default=False,
        verbose_name=_('Choix multiple'),
        help_text=_('Si True, plusieurs réponses peuvent être correctes')
    )

    class Meta:
        verbose_name = _('Question')
        verbose_name_plural = _('Questions')
        ordering = ['order']

    def __str__(self):
        return f'Q{self.order} — {self.text[:60]}'


class Choice(models.Model):
    """Choix de réponse pour une question de quiz."""
    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        related_name='choices',
        verbose_name=_('Question')
    )
    text = models.CharField(
        max_length=500,
        verbose_name=_('Texte du choix')
    )
    is_correct = models.BooleanField(
        default=False,
        verbose_name=_('Réponse correcte')
    )

    class Meta:
        verbose_name = _('Choix')
        verbose_name_plural = _('Choix')

    def __str__(self):
        marker = '✓' if self.is_correct else '✗'
        return f'{marker} {self.text[:80]}'


class QuizAttempt(models.Model):
    """
    Tentative de quiz d'un utilisateur.
    Stocke le score et les réponses soumises.
    """
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='quiz_attempts',
        verbose_name=_('Utilisateur')
    )
    quiz = models.ForeignKey(
        Quiz,
        on_delete=models.CASCADE,
        related_name='attempts',
        verbose_name=_('Quiz')
    )
    score_percentage = models.FloatField(
        default=0,
        verbose_name=_('Score obtenu (%)')
    )
    passed = models.BooleanField(
        default=False,
        verbose_name=_('Réussi')
    )
    answers = models.JSONField(
        default=dict,
        verbose_name=_('Réponses soumises'),
        help_text=_('{"question_id": [choice_id, ...], ...}')
    )
    attempted_at = models.DateTimeField(
        default=timezone.now,
        verbose_name=_('Tentative le')
    )

    class Meta:
        verbose_name = _('Tentative de quiz')
        verbose_name_plural = _('Tentatives de quiz')
        ordering = ['-attempted_at']

    def __str__(self):
        status = '✓' if self.passed else '✗'
        return f'{status} {self.user} — {self.quiz} ({self.score_percentage:.0f}%)'


# ─────────────────────────────────────────────────────────────────────────────
# CERTIFICATS
# ─────────────────────────────────────────────────────────────────────────────

class Certificate(models.Model):
    """
    Certificat de réussite d'un parcours complet.
    Le PDF est généré de manière asynchrone via Celery.
    """
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='certificates',
        verbose_name=_('Utilisateur')
    )
    path = models.ForeignKey(
        LearningPath,
        on_delete=models.CASCADE,
        related_name='certificates',
        verbose_name=_('Parcours')
    )
    issued_at = models.DateTimeField(
        default=timezone.now,
        verbose_name=_('Délivré le')
    )
    pdf_file = models.FileField(
        upload_to='learning/certificates/',
        null=True, blank=True,
        verbose_name=_('Fichier PDF')
    )
    # Clé unique pour accès public au certificat (lien de partage)
    unique_code = models.CharField(
        max_length=20,
        unique=True,
        blank=True,
        verbose_name=_('Code unique')
    )

    class Meta:
        verbose_name = _('Certificat')
        verbose_name_plural = _('Certificats')
        unique_together = [('user', 'path')]

    def __str__(self):
        return f'Certificat — {self.user} · {self.path.title}'

    def save(self, *args, **kwargs):
        """Génère automatiquement un code unique à la création."""
        if not self.unique_code:
            import uuid
            self.unique_code = uuid.uuid4().hex[:12].upper()
        super().save(*args, **kwargs)
