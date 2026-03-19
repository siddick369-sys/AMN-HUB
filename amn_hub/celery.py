"""
Configuration Celery pour AMN Employee Hub.
Toutes les tâches lourdes (mails, logs) passent par ici.
"""

import os
from celery import Celery

# Définir le module settings par défaut pour Celery
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'amn_hub.settings')

app = Celery('amn_hub')

# Charger la configuration depuis settings.py (préfixe CELERY_)
app.config_from_object('django.conf:settings', namespace='CELERY')

# Autodécouverte des tâches dans tous les modules tasks.py
app.autodiscover_tasks()


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    """Tâche de debug pour vérifier que Celery fonctionne."""
    print(f'[AMN Celery] Request: {self.request!r}')
