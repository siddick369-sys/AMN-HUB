"""
Admin Django — Module Inventory.
"""

from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from inventory.models import (
    Asset, AssetTransfer, AssetStatus,
    StockItem, StockTransaction,
    Ticket, TicketStatus, TicketPriority,
)


# ─────────────────────────────────────────────────────────────────────────────
# ASSET
# ─────────────────────────────────────────────────────────────────────────────

class AssetTransferInline(admin.TabularInline):
    model = AssetTransfer
    extra = 0
    readonly_fields = ['transferred_at', 'transferred_by']
    fields = ['from_employee', 'to_employee', 'transferred_by', 'transferred_at', 'notes']


@admin.register(Asset)
class AssetAdmin(admin.ModelAdmin):
    list_display  = ['tag_amn', 'name', 'category', 'brand', 'status_badge', 'assigned_to', 'created_at']
    list_filter   = ['status', 'category']
    search_fields = ['tag_amn', 'name', 'brand', 'serial_number']
    readonly_fields = ['created_at', 'updated_at', 'qr_code_data']
    inlines       = [AssetTransferInline]

    def status_badge(self, obj):
        colors = {
            AssetStatus.AVAILABLE: '#10b981',
            AssetStatus.ASSIGNED:  '#3b82f6',
            AssetStatus.IN_REPAIR: '#f59e0b',
            AssetStatus.RETIRED:   '#94a3b8',
            AssetStatus.LOST:      '#ef4444',
        }
        color = colors.get(obj.status, '#94a3b8')
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;border-radius:9999px;font-size:11px">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = _('Statut')


# ─────────────────────────────────────────────────────────────────────────────
# STOCK
# ─────────────────────────────────────────────────────────────────────────────

class StockTransactionInline(admin.TabularInline):
    model = StockTransaction
    extra = 0
    readonly_fields = ['timestamp', 'performed_by', 'quantity_before', 'quantity_after']
    fields = [
        'transaction_type', 'quantity', 'quantity_before', 'quantity_after',
        'performed_by', 'reason', 'reference', 'timestamp'
    ]

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(StockItem)
class StockItemAdmin(admin.ModelAdmin):
    list_display  = ['name', 'category', 'quantity_display', 'alert_threshold', 'unit', 'location']
    list_filter   = ['category']
    search_fields = ['name', 'sku', 'supplier']
    readonly_fields = ['created_at', 'updated_at']
    inlines       = [StockTransactionInline]

    def quantity_display(self, obj):
        color = '#ef4444' if obj.is_empty else ('#f59e0b' if obj.is_low_stock else '#10b981')
        return format_html(
            '<span style="color:{};font-weight:600">{} {}</span>',
            color, obj.quantity, obj.unit
        )
    quantity_display.short_description = _('Quantité')


@admin.register(StockTransaction)
class StockTransactionAdmin(admin.ModelAdmin):
    list_display  = ['item', 'transaction_type', 'quantity', 'quantity_before', 'quantity_after', 'performed_by', 'timestamp']
    list_filter   = ['transaction_type', 'timestamp']
    search_fields = ['item__name', 'performed_by__username']
    readonly_fields = list.__add__(
        ['timestamp', 'quantity_before', 'quantity_after'],
        []
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False  # Audit trail immuable


# ─────────────────────────────────────────────────────────────────────────────
# TICKET
# ─────────────────────────────────────────────────────────────────────────────

@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display  = [
        'ticket_number', 'title', 'priority_badge', 'status_badge',
        'submitted_by', 'assigned_to', 'created_at'
    ]
    list_filter   = ['status', 'priority', 'created_at']
    search_fields = ['ticket_number', 'title', 'submitted_by__username']
    readonly_fields = ['ticket_number', 'created_at', 'updated_at', 'resolved_at']
    actions = ['mark_resolved', 'mark_closed']

    def priority_badge(self, obj):
        colors = {
            TicketPriority.LOW:      '#94a3b8',
            TicketPriority.MEDIUM:   '#3b82f6',
            TicketPriority.HIGH:     '#f59e0b',
            TicketPriority.CRITICAL: '#ef4444',
        }
        color = colors.get(obj.priority, '#94a3b8')
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;border-radius:9999px;font-size:11px">{}</span>',
            color, obj.get_priority_display()
        )
    priority_badge.short_description = _('Priorité')

    def status_badge(self, obj):
        colors = {
            TicketStatus.OPEN:        '#3b82f6',
            TicketStatus.IN_PROGRESS: '#f59e0b',
            TicketStatus.RESOLVED:    '#10b981',
            TicketStatus.CLOSED:      '#94a3b8',
        }
        color = colors.get(obj.status, '#94a3b8')
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;border-radius:9999px;font-size:11px">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = _('Statut')

    @admin.action(description=_('Marquer comme résolu'))
    def mark_resolved(self, request, queryset):
        from django.utils import timezone
        queryset.update(status=TicketStatus.RESOLVED, resolved_at=timezone.now())

    @admin.action(description=_('Fermer les tickets'))
    def mark_closed(self, request, queryset):
        queryset.update(status=TicketStatus.CLOSED)
