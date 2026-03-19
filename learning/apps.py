from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class LearningConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'learning'
    verbose_name = _('Formation & Onboarding')

    def ready(self):
        """Connecte les signaux au démarrage de Django."""
        import learning.signals  # noqa: F401
