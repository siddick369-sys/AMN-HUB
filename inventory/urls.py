"""
URLs — Module Inventory.
"""

from django.urls import path
from inventory import views

app_name = 'inventory'

urlpatterns = [
    # ── Dashboard principal ──────────────────────────────────────────────────
    path('', views.inventory_dashboard, name='dashboard'),

    # ── Tutoriel ─────────────────────────────────────────────────────────────
    path('tutorial/seen/', views.mark_tutorial_seen, name='tutorial_seen'),

    # ── Warehouse Manager ────────────────────────────────────────────────────
    path('warehouse/', views.warehouse_manager, name='warehouse'),
    path('warehouse/stock/create/', views.stock_item_create, name='stock_create'),
    path('warehouse/stock/<int:pk>/edit/', views.stock_item_edit, name='stock_edit'),
    path('warehouse/stock/quick-update/', views.stock_quick_update, name='stock_quick_update'),
    path('warehouse/assets/create/', views.asset_create, name='asset_create'),

    # ── Mes Actifs ───────────────────────────────────────────────────────────
    path('my-assets/', views.my_assets, name='my_assets'),
    path('my-assets/add/', views.asset_self_add, name='asset_self_add'),
    path('my-assets/<int:pk>/', views.asset_detail, name='asset_detail'),

    # ── Helpdesk ─────────────────────────────────────────────────────────────
    path('helpdesk/', views.helpdesk, name='helpdesk'),
    path('helpdesk/create/', views.ticket_create, name='ticket_create'),
    path('helpdesk/<int:pk>/', views.ticket_detail, name='ticket_detail'),

    # ── QR Code ──────────────────────────────────────────────────────────────
    path('qr-lookup/', views.qr_lookup, name='qr_lookup'),
]
