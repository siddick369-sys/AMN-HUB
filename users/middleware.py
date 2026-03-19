"""
Middleware — Module Users, AMN Employee Hub.
ActivityTrackingMiddleware : journalise les pages visitées de manière asynchrone.
"""

import logging
from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger(__name__)

# Préfixes d'URL à ignorer pour le tracking (static, media, admin assets…)
IGNORED_PREFIXES = (
    '/static/', '/media/', '/favicon.ico',
    '/admin/jsi18n/', '/admin/autocomplete/',
)


class ActivityTrackingMiddleware(MiddlewareMixin):
    """
    Middleware léger qui enregistre les accès des utilisateurs connectés
    via une tâche Celery (non bloquant).

    Ne journalise que :
    - Les requêtes POST importantes (login, logout, changements de données)
    - La navigation des utilisateurs authentifiés (GET sur pages applicatives)

    Exclut les fichiers statiques, médias et assets admin.
    """

    def process_response(self, request, response):
        """
        Appelé après chaque réponse HTTP.
        Ne fait rien si l'utilisateur n'est pas authentifié ou si l'URL est ignorée.
        """
        # Ignorer les fichiers statiques / médias
        path = request.path
        if any(path.startswith(prefix) for prefix in IGNORED_PREFIXES):
            return response

        # Ne tracker que les utilisateurs authentifiés
        if not hasattr(request, 'user') or not request.user.is_authenticated:
            return response

        # Ne logger que les réponses 2xx et 3xx (ignorer les 404, 500…)
        if response.status_code >= 400:
            return response

        # Ne logger que les requêtes POST (actions significatives)
        # Les GET génèrent trop de bruit dans les logs
        if request.method != 'POST':
            return response

        try:
            from users.tasks import log_activity_async
            from users.utils import get_client_ip

            log_activity_async.delay(
                user_id=request.user.pk,
                action='page_action',
                ip_address=get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', '')[:500],
                extra_data={
                    'path': path,
                    'method': request.method,
                    'status_code': response.status_code,
                }
            )
        except Exception as exc:
            # Le middleware ne doit JAMAIS casser la réponse HTTP
            logger.error(f'[AMN Middleware] Erreur tracking : {exc}')

        return response
