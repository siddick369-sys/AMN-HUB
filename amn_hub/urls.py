"""
URLs principales — AMN Employee Hub.
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.conf.urls.i18n import i18n_patterns

admin.site.site_header = 'AMN Employee Hub — Admin'
admin.site.site_title = 'AMN Hub'
admin.site.index_title = 'Tableau de bord administrateur'

# URLs non-traduites (API, i18n switch)
urlpatterns = [
    path('i18n/', include('django.conf.urls.i18n')),
]

# URLs traduites (préfixées par la langue : /fr/, /en/)
urlpatterns += i18n_patterns(
    path('admin/', admin.site.urls),
    path('auth/', include('users.urls', namespace='users')),
    path('dashboard/', include('users.dashboard_urls', namespace='dashboard')),
    path('learning/', include('learning.urls', namespace='learning')),
    path('attendance/', include('attendance.urls', namespace='attendance')),
    path('inventory/', include('inventory.urls', namespace='inventory')),
    prefix_default_language=False,
)

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATICFILES_DIRS[0])
