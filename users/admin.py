"""
Administration Django — Module Users, AMN Employee Hub.
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.translation import gettext_lazy as _
from django.utils.html import format_html

from .models import ActivityLog, Employee


# ─────────────────────────────────────────────────────────────────────────────
# ADMIN : Employee
# ─────────────────────────────────────────────────────────────────────────────

@admin.register(Employee)
class EmployeeAdmin(UserAdmin):
    """Interface admin pour le modèle Employee."""

    list_display  = ('username', 'email', 'get_full_name', 'department',
                     'country', 'is_verified', 'is_frozen', 'is_active', 'date_joined')
    list_filter   = ('is_verified', 'is_frozen', 'is_active', 'department', 'country', 'preferred_language')
    search_fields = ('username', 'email', 'first_name', 'last_name', 'id_badge')
    ordering      = ('-date_joined',)
    readonly_fields = ('date_joined', 'updated_at', 'deletion_cancel_token',
                       'verification_code_created_at', 'password_reset_token_created_at')

    # Étendre les fieldsets de UserAdmin pour inclure les champs AMN
    fieldsets = UserAdmin.fieldsets + (
        (_('Informations AMN'), {
            'fields': ('id_badge', 'avatar', 'department', 'country',
                       'job_title', 'phone_number', 'hire_date', 'preferred_language')
        }),
        (_('Statut du compte'), {
            'fields': ('is_verified', 'is_frozen', 'deletion_scheduled_at',
                       'deletion_cancel_token', 'updated_at')
        }),
        (_('Vérification email'), {
            'fields': ('verification_code', 'verification_code_created_at'),
            'classes': ('collapse',),
        }),
        (_('Reset mot de passe'), {
            'fields': ('password_reset_token', 'password_reset_token_created_at'),
            'classes': ('collapse',),
        }),
    )

    add_fieldsets = UserAdmin.add_fieldsets + (
        (_('Informations AMN'), {
            'fields': ('email', 'first_name', 'last_name', 'id_badge',
                       'department', 'country', 'preferred_language')
        }),
    )

    actions = ['freeze_selected_accounts', 'restore_selected_accounts']

    @admin.action(description=_('Geler les comptes sélectionnés'))
    def freeze_selected_accounts(self, request, queryset):
        for emp in queryset.filter(is_frozen=False):
            emp.freeze_account()
        self.message_user(request, _(f'{queryset.count()} compte(s) gelé(s).'))

    @admin.action(description=_('Restaurer les comptes sélectionnés'))
    def restore_selected_accounts(self, request, queryset):
        for emp in queryset.filter(is_frozen=True):
            emp.restore_account()
        self.message_user(request, _(f'{queryset.count()} compte(s) restauré(s).'))


# ─────────────────────────────────────────────────────────────────────────────
# ADMIN : ActivityLog
# ─────────────────────────────────────────────────────────────────────────────

@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    """Interface admin en lecture seule pour le journal d'activité."""

    list_display  = ('timestamp', 'get_user', 'action', 'ip_address', 'get_user_agent_short')
    list_filter   = ('action', 'timestamp')
    search_fields = ('user__username', 'user__email', 'ip_address', 'action')
    ordering      = ('-timestamp',)
    readonly_fields = ('user', 'action', 'ip_address', 'user_agent', 'extra_data', 'timestamp')

    def has_add_permission(self, request):
        return False  # Les logs ne se créent pas manuellement

    def has_change_permission(self, request, obj=None):
        return False  # Les logs sont immuables

    @admin.display(description=_('Utilisateur'))
    def get_user(self, obj):
        if obj.user:
            return format_html('<strong>{}</strong>', obj.user.username)
        return format_html('<em style="color:#999">{}</em>', _('Supprimé'))

    @admin.display(description=_('User Agent'))
    def get_user_agent_short(self, obj):
        return obj.user_agent[:60] + '…' if len(obj.user_agent) > 60 else obj.user_agent
