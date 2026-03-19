"""
Utilitaires partagés — Module Users, AMN Employee Hub.
Protection Brute Force via Redis.
"""

import logging
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# PROTECTION BRUTE FORCE (Redis)
# ─────────────────────────────────────────────────────────────────────────────

MAX_ATTEMPTS = getattr(settings, 'BRUTE_FORCE_MAX_ATTEMPTS', 5)
LOCKOUT_DURATION = getattr(settings, 'BRUTE_FORCE_LOCKOUT_DURATION', 900)  # 15 min
REDIS_PREFIX = getattr(settings, 'BRUTE_FORCE_REDIS_PREFIX', 'amn:bf')


def _bf_key(identifier: str, action: str = 'login') -> str:
    """Construit la clé Redis pour un identifiant et une action donnée."""
    return f'{REDIS_PREFIX}:{action}:{identifier}'


def get_failed_attempts(identifier: str, action: str = 'login') -> int:
    """Retourne le nombre de tentatives échouées pour un identifiant."""
    return cache.get(_bf_key(identifier, action), 0)


def increment_failed_attempts(identifier: str, action: str = 'login') -> int:
    """
    Incrémente le compteur de tentatives échouées.
    Retourne le nombre total après incrémentation.
    """
    key = _bf_key(identifier, action)
    try:
        attempts = cache.get(key, 0) + 1
        cache.set(key, attempts, timeout=LOCKOUT_DURATION)
        logger.debug(f'[AMN BruteForce] {identifier} | {action} | tentative #{attempts}')
        return attempts
    except Exception as exc:
        # Si Redis est indisponible, on laisse passer (fail open)
        logger.error(f'[AMN BruteForce] Redis error : {exc}')
        return 0


def is_locked_out(identifier: str, action: str = 'login') -> bool:
    """Retourne True si l'identifiant est verrouillé (dépassé MAX_ATTEMPTS)."""
    return get_failed_attempts(identifier, action) >= MAX_ATTEMPTS


def reset_failed_attempts(identifier: str, action: str = 'login') -> None:
    """Remet à zéro le compteur après une authentification réussie."""
    cache.delete(_bf_key(identifier, action))
    logger.debug(f'[AMN BruteForce] Compteur réinitialisé : {identifier} | {action}')


def get_lockout_remaining_seconds(identifier: str, action: str = 'login') -> int:
    """
    Retourne le nombre de secondes restantes avant la fin du blocage.
    Utilise cache.ttl() si disponible (django-redis).
    """
    key = _bf_key(identifier, action)
    try:
        ttl = cache.ttl(key)  # Disponible avec django-redis
        return max(0, ttl) if ttl else 0
    except Exception:
        return LOCKOUT_DURATION


def get_client_ip(request) -> str:
    """
    Extrait l'adresse IP réelle du client depuis la requête HTTP.
    Gère les proxies via X-Forwarded-For.
    """
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '')
