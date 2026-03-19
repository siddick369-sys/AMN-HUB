"""
Administration Django — Module Learning, AMN Employee Hub.
Interfaces riches avec inlines pour une gestion complète sans quitter l'admin.
"""

from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from .models import (
    BuddyAssignment, Certificate, Choice, Course, Lesson, LearningPath,
    OnboardingJourney, OnboardingStep, OnboardingTask, OnboardingTaskCompletion,
    PathEnrollment, Question, Quiz, QuizAttempt, UserProgress,
)


# ═════════════════════════════════════════════════════════════════════════════
# INLINES
# ═════════════════════════════════════════════════════════════════════════════

class OnboardingTaskInline(admin.TabularInline):
    model   = OnboardingTask
    extra   = 1
    fields  = ('order', 'task_type', 'title', 'meet_colleague')
    ordering = ('order',)


class OnboardingStepInline(admin.StackedInline):
    model        = OnboardingStep
    extra        = 1
    fields       = ('day_number', 'title', 'icon', 'description')
    ordering     = ('day_number',)
    show_change_link = True


class CourseInline(admin.TabularInline):
    model  = Course
    extra  = 1
    fields = ('order', 'title', 'is_active')
    ordering = ('order',)
    show_change_link = True


class LessonInline(admin.TabularInline):
    model  = Lesson
    extra  = 1
    fields = ('order', 'title', 'content_type', 'duration_minutes')
    ordering = ('order',)


class ChoiceInline(admin.TabularInline):
    model  = Choice
    extra  = 2
    fields = ('text', 'is_correct')


class QuestionInline(admin.StackedInline):
    model        = Question
    extra        = 1
    fields       = ('order', 'text', 'is_multiple_choice')
    ordering     = ('order',)
    show_change_link = True


class PathEnrollmentInline(admin.TabularInline):
    model     = PathEnrollment
    extra     = 0
    fields    = ('path', 'enrolled_at', 'is_active')
    readonly_fields = ('enrolled_at',)


# ═════════════════════════════════════════════════════════════════════════════
# ONBOARDING
# ═════════════════════════════════════════════════════════════════════════════

@admin.register(OnboardingJourney)
class OnboardingJourneyAdmin(admin.ModelAdmin):
    list_display    = ('employee', 'started_at', 'get_days_elapsed', 'get_progress', 'is_completed')
    list_filter     = ('is_completed',)
    search_fields   = ('employee__username', 'employee__email')
    readonly_fields = ('started_at', 'completed_at')
    inlines         = [OnboardingStepInline]

    @admin.display(description=_('Jours écoulés'))
    def get_days_elapsed(self, obj):
        return f'J+{obj.days_since_start}'

    @admin.display(description=_('Progression'))
    def get_progress(self, obj):
        pct = obj.progress_percentage
        color = '#22c55e' if pct >= 80 else '#f59e0b' if pct >= 40 else '#ef4444'
        return format_html(
            '<div style="background:#e5e7eb;border-radius:4px;width:100px;height:8px;">'
            '<div style="background:{};width:{}px;height:8px;border-radius:4px;"></div>'
            '</div> <small>{}%</small>',
            color, pct, pct
        )


@admin.register(OnboardingStep)
class OnboardingStepAdmin(admin.ModelAdmin):
    list_display  = ('journey', 'day_number', 'title', 'icon', 'get_tasks_count')
    list_filter   = ('day_number',)
    search_fields = ('title', 'journey__employee__username')
    ordering      = ('journey', 'day_number')
    inlines       = [OnboardingTaskInline]

    @admin.display(description=_('Tâches'))
    def get_tasks_count(self, obj):
        return obj.tasks.count()


@admin.register(BuddyAssignment)
class BuddyAssignmentAdmin(admin.ModelAdmin):
    list_display  = ('new_employee', 'buddy', 'assigned_date')
    search_fields = ('new_employee__username', 'buddy__username')
    autocomplete_fields = ['new_employee', 'buddy']


# ═════════════════════════════════════════════════════════════════════════════
# LMS
# ═════════════════════════════════════════════════════════════════════════════

@admin.register(LearningPath)
class LearningPathAdmin(admin.ModelAdmin):
    list_display    = ('title', 'target_department', 'estimated_hours',
                       'get_courses_count', 'get_enrollments_count', 'is_active')
    list_filter     = ('target_department', 'is_active')
    search_fields   = ('title', 'description')
    list_editable   = ('is_active',)
    inlines         = [CourseInline]
    readonly_fields = ('created_at', 'updated_at')

    @admin.display(description=_('Cours'))
    def get_courses_count(self, obj):
        return obj.courses.count()

    @admin.display(description=_('Inscrits'))
    def get_enrollments_count(self, obj):
        return obj.enrollments.count()


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display  = ('title', 'path', 'order', 'get_lessons_count', 'is_active')
    list_filter   = ('is_active', 'path__target_department')
    search_fields = ('title', 'path__title')
    list_editable = ('order', 'is_active')
    inlines       = [LessonInline]

    @admin.display(description=_('Leçons'))
    def get_lessons_count(self, obj):
        return obj.lessons.count()


@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    list_display  = ('title', 'course', 'content_type', 'duration_minutes', 'order', 'get_low_data_badge')
    list_filter   = ('content_type',)
    search_fields = ('title', 'course__title')
    list_editable = ('order',)

    @admin.display(description=_('Low-Data'))
    def get_low_data_badge(self, obj):
        if obj.is_low_data_friendly:
            return format_html('<span style="color:#22c55e;font-weight:bold;">✓</span>')
        return format_html('<span style="color:#ef4444;">✗ Vidéo</span>')


@admin.register(Quiz)
class QuizAdmin(admin.ModelAdmin):
    list_display = ('title', 'course', 'passing_score_percentage', 'max_attempts',
                    'get_questions_count', 'get_attempts_count')
    inlines      = [QuestionInline]

    @admin.display(description=_('Questions'))
    def get_questions_count(self, obj):
        return obj.questions.count()

    @admin.display(description=_('Tentatives'))
    def get_attempts_count(self, obj):
        return obj.attempts.count()


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ('text_short', 'quiz', 'order', 'is_multiple_choice')
    list_filter  = ('is_multiple_choice',)
    inlines      = [ChoiceInline]

    @admin.display(description=_('Question'))
    def text_short(self, obj):
        return obj.text[:80] + '…' if len(obj.text) > 80 else obj.text


@admin.register(Certificate)
class CertificateAdmin(admin.ModelAdmin):
    list_display    = ('user', 'path', 'issued_at', 'unique_code', 'has_pdf')
    list_filter     = ('path',)
    search_fields   = ('user__username', 'user__email', 'unique_code')
    readonly_fields = ('issued_at', 'unique_code')

    def has_add_permission(self, request):
        return False

    @admin.display(description='PDF')
    def has_pdf(self, obj):
        if obj.pdf_file:
            return format_html('<a href="{}" target="_blank">📄 PDF</a>', obj.pdf_file.url)
        return '—'


@admin.register(UserProgress)
class UserProgressAdmin(admin.ModelAdmin):
    list_display  = ('user', 'lesson', 'is_completed', 'completed_at')
    list_filter   = ('is_completed',)
    search_fields = ('user__username', 'lesson__title')
    readonly_fields = ('completed_at',)

    def has_add_permission(self, request):
        return False


@admin.register(QuizAttempt)
class QuizAttemptAdmin(admin.ModelAdmin):
    list_display    = ('user', 'quiz', 'get_score_badge', 'passed', 'attempted_at')
    list_filter     = ('passed',)
    search_fields   = ('user__username', 'quiz__title')
    readonly_fields = ('answers', 'attempted_at')

    def has_add_permission(self, request):
        return False

    @admin.display(description=_('Score'))
    def get_score_badge(self, obj):
        color = '#22c55e' if obj.passed else '#ef4444'
        return format_html(
            '<strong style="color:{};">{:.0f}%</strong>',
            color, obj.score_percentage
        )


@admin.register(PathEnrollment)
class PathEnrollmentAdmin(admin.ModelAdmin):
    list_display  = ('user', 'path', 'enrolled_at', 'is_active')
    list_filter   = ('is_active', 'path')
    search_fields = ('user__username', 'path__title')
    readonly_fields = ('enrolled_at',)
