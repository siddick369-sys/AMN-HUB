"""
Django settings pour AMN Employee Hub.
Africa Mobile Networks — Plateforme interne employés.
"""

from pathlib import Path
from django.utils.translation import gettext_lazy as _
from decouple import config

BASE_DIR = Path(__file__).resolve().parent.parent

# ─────────────────────────────────────────────
# SÉCURITÉ
# ─────────────────────────────────────────────
SECRET_KEY = config('SECRET_KEY', default='amn-hub-dev-key-change-me')
DEBUG = config('DEBUG', default=True, cast=bool)
ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='127.0.0.1,localhost').split(',')

# ─────────────────────────────────────────────
# APPLICATIONS
# ─────────────────────────────────────────────
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',
    # Tâches planifiées Celery
    'django_celery_beat',
    # AMN Apps
    'users',
    'learning',
]

# ─────────────────────────────────────────────
# MIDDLEWARE
# ─────────────────────────────────────────────
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    # i18n : doit être avant CommonMiddleware
    'django.middleware.locale.LocaleMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    # Middleware AMN : tracking activité utilisateur
    'users.middleware.ActivityTrackingMiddleware',
]

ROOT_URLCONF = 'amn_hub.urls'
AUTH_USER_MODEL = 'users.Employee'
LOGIN_URL = '/auth/login/'
LOGIN_REDIRECT_URL = '/dashboard/'
LOGOUT_REDIRECT_URL = '/auth/login/'

# ─────────────────────────────────────────────
# TEMPLATES
# ─────────────────────────────────────────────
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'django.template.context_processors.i18n',
            ],
        },
    },
]

WSGI_APPLICATION = 'amn_hub.wsgi.application'

# ─────────────────────────────────────────────
# BASE DE DONNÉES (PostgreSQL)
# ─────────────────────────────────────────────
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': config('DB_NAME', default='amn_hub_db'),
        'USER': config('DB_USER', default='amn_hub_user'),
        'PASSWORD': config('DB_PASSWORD', default='amn_hub_secure_pass'),
        'HOST': config('DB_HOST', default='localhost'),
        'PORT': config('DB_PORT', default='5432'),
        'OPTIONS': {
            'connect_timeout': 10,
        },
    }
}

# ─────────────────────────────────────────────
# CACHE & SESSION (Redis)
# ─────────────────────────────────────────────
REDIS_URL = config('REDIS_URL', default='redis://localhost:6379/0')

CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': REDIS_URL,
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            'SOCKET_CONNECT_TIMEOUT': 5,
            'SOCKET_TIMEOUT': 5,
            'CONNECTION_POOL_KWARGS': {'max_connections': 100},
        },
        'KEY_PREFIX': 'amn_hub',
        'TIMEOUT': 300,
    }
}

# Sessions via Redis
SESSION_ENGINE = 'django.contrib.sessions.backends.cache'
SESSION_CACHE_ALIAS = 'default'
SESSION_COOKIE_AGE = 86400 * 7  # 7 jours

# ─────────────────────────────────────────────
# CELERY (Tâches asynchrones)
# ─────────────────────────────────────────────
CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = REDIS_URL
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'Africa/Douala'
CELERY_BEAT_SCHEDULER = 'django_celery_beat.schedulers:DatabaseScheduler'
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
CELERY_TASK_SOFT_TIME_LIMIT = 1800

# ─────────────────────────────────────────────
# EMAIL
# ─────────────────────────────────────────────
EMAIL_BACKEND = config(
    'EMAIL_BACKEND',
    default='django.core.mail.backends.console.EmailBackend'
)
EMAIL_HOST = config('EMAIL_HOST', default='smtp.gmail.com')
EMAIL_PORT = config('EMAIL_PORT', default=587, cast=int)
EMAIL_USE_TLS = config('EMAIL_USE_TLS', default=True, cast=bool)
EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')
DEFAULT_FROM_EMAIL = config(
    'DEFAULT_FROM_EMAIL',
    default='AMN Employee Hub <noreply@africamobilenetworks.com>'
)
FRONTEND_URL = config('FRONTEND_URL', default='http://localhost:8000')

# ─────────────────────────────────────────────
# VALIDATION DES MOTS DE PASSE
# ─────────────────────────────────────────────
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
     'OPTIONS': {'min_length': 8}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ─────────────────────────────────────────────
# INTERNATIONALISATION (Bilingue FR/EN)
# ─────────────────────────────────────────────
LANGUAGE_CODE = 'fr'
TIME_ZONE = 'Africa/Douala'
USE_I18N = True
USE_L10N = True
USE_TZ = True

LANGUAGES = [
    ('fr', _('Français')),
    ('en', _('English')),
]

LOCALE_PATHS = [BASE_DIR / 'locale']

# ─────────────────────────────────────────────
# FICHIERS STATIQUES & MÉDIAS
# ─────────────────────────────────────────────
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# ─────────────────────────────────────────────
# SÉCURITÉ BRUTE FORCE (via Redis)
# ─────────────────────────────────────────────
BRUTE_FORCE_MAX_ATTEMPTS = 5
BRUTE_FORCE_LOCKOUT_DURATION = 60 * 15   # 15 minutes
BRUTE_FORCE_REDIS_PREFIX = 'amn:bf'

# ─────────────────────────────────────────────
# SUPPRESSION DE COMPTE
# ─────────────────────────────────────────────
ACCOUNT_DELETION_DELAY_DAYS = 30

# ─────────────────────────────────────────────
# DIVERS
# ─────────────────────────────────────────────
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

if not DEBUG:
    SECURE_HSTS_SECONDS = 31536000
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
