import os
import django
from django.utils import timezone

# Configurer Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'amn_hub.settings')
django.setup()

from learning.models import (
    LearningPath, Course, Lesson, ContentType,
    Quiz, Question, Choice, OnboardingStep, OnboardingTask, TaskType,
    OnboardingJourney, PathEnrollment
)
from users.models import Employee, Department

def seed_data():
    print("--- Début du seeding AMN Learning ---")

    # 1. PARCOURS TECHNIQUE (TECH)
    tech_path, _ = LearningPath.objects.get_or_create(
        title="Expertise Infrastructure Rurale",
        target_department=Department.TECH,
        defaults={
            'description': "Maîtrisez le déploiement et la maintenance des sites AMN en zones reculées.",
            'estimated_hours': 10,
        }
    )

    # Cours 1
    c1, _ = Course.objects.get_or_create(
        path=tech_path,
        title="Introduction aux sites Ultra-Rural",
        defaults={'order': 1, 'description': "Les bases de l'architecture réseau AMN."}
    )

    # Leçons
    Lesson.objects.get_or_create(
        course=c1,
        title="L'architecture des sites VSAT et Solaire",
        defaults={
            'content_type': ContentType.VIDEO,
            'media_url': "https://www.youtube.com/watch?v=dQw4w9WgXcQ", # Placeholder
            'content_text': "Découvrez comment nous alimentons nos sites via l'énergie solaire et le backhaul satellite.",
            'order': 1
        }
    )
    Lesson.objects.get_or_create(
        course=c1,
        title="Sécurité et HSE sur site",
        defaults={
            'content_type': ContentType.TEXT,
            'content_text': "### Règles d'or de sécurité\n1. Port des EPI obligatoire.\n2. Vérification des batteries.\n3. Rapport d'incident immédiat.",
            'order': 2
        }
    )

    # Quiz
    quiz_tech, _ = Quiz.objects.get_or_create(
        course=c1,
        defaults={'title': "Validation des acquis - Infra", 'passing_score_percentage': 80}
    )

    q1, _ = Question.objects.get_or_create(
        quiz=quiz_tech,
        text="Quelle est la source d'énergie principale des sites ruraux AMN ?",
        defaults={'order': 1}
    )
    Choice.objects.get_or_create(question=q1, text="Solaire", defaults={'is_correct': True})
    Choice.objects.get_or_create(question=q1, text="Nucléaire", defaults={'is_correct': False})
    Choice.objects.get_or_create(question=q1, text="Groupe Électrogène", defaults={'is_correct': False})

    # 2. PARCOURS RH / CULTURE (Pour tous, on met HR par défaut dans le modèle mais on peut l'ajuster)
    hr_path, _ = LearningPath.objects.get_or_create(
        title="Culture & Valeurs AMN",
        target_department=Department.HR,
        defaults={
            'description': "Comprendre la mission sociale d'Africa Mobile Networks.",
            'estimated_hours': 2,
        }
    )

    c2, _ = Course.objects.get_or_create(
        path=hr_path,
        title="Notre Vision : Connecter l'Afrique",
        defaults={'order': 1}
    )

    Lesson.objects.get_or_create(
        course=c2,
        title="L'impact social de la connectivité",
        defaults={
            'content_type': ContentType.TEXT,
            'content_text': "AMN permet à des millions de personnes d'accéder aux services financiers et à l'éducation via le mobile.",
            'order': 1
        }
    )

    # 3. ÉTAPES D'ONBOARDING GÉNÉRIQUES
    # On crée les étapes dans un dictionnaire pour les réutiliser
    default_steps = [
        {"day": 0, "title": "Bienvenue chez AMN", "desc": "Vos premières heures avec nous."},
        {"day": 1, "title": "Outils & Accès", "desc": "Configuration de vos comptes."},
        {"day": 7, "title": "Culture & Valeurs", "desc": "Plongée dans l'ADN d'AMN."},
    ]

    # 4. TRAITEMENT DE TOUS LES UTILISATEURS EXISTANTS
    print("--- Attribution des parcours aux utilisateurs existants ---")
    all_users = Employee.objects.all()
    
    for user in all_users:
        # Créer le Journey s'il n'existe pas
        journey, created = OnboardingJourney.objects.get_or_create(employee=user)
        if created:
            print(f"  + Journey créé pour {user.username}")

        # Ajouter les étapes et tâches si le journey est vide
        if journey.journey_steps.count() == 0:
            for s_data in default_steps:
                step, _ = OnboardingStep.objects.get_or_create(
                    journey=journey,
                    day_number=s_data['day'],
                    defaults={'title': s_data['title'], 'description': s_data['desc']}
                )
                # Tâche par défaut pour le Jour 0
                if s_data['day'] == 0:
                    OnboardingTask.objects.get_or_create(
                        step=step,
                        title="Compléter mon profil",
                        defaults={'content': "Ajoutez votre photo et votre numéro de téléphone.", 'task_type': TaskType.ACTION, 'order': 1}
                    )
                    OnboardingTask.objects.get_or_create(
                        step=step,
                        title="Rencontrer mon Buddy",
                        defaults={'content': "Prenez 15 min pour discuter avec votre parrain assigné.", 'task_type': TaskType.MEET, 'order': 2}
                    )

        # Inscrire l'utilisateur aux parcours de son département
        from learning.models import PathEnrollment
        paths = LearningPath.objects.filter(target_department=user.department, is_active=True)
        # Si département OTHER, on lui donne celui de la RH pour test
        if user.department == Department.OTHER:
            paths = LearningPath.objects.filter(target_department='HR', is_active=True)
            
        for path in paths:
            PathEnrollment.objects.get_or_create(user=user, path=path)
            print(f"  + Inscription de {user.username} au parcours : {path.title}")

    print("--- Seeding terminé avec succès ! ---")

if __name__ == "__main__":
    seed_data()
