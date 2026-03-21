"""
Vues — Module Inventory (Gestion d'Actifs, Stock Global & Helpdesk).
Inclut la logique du tutoriel interactif (has_seen_inventory_tutorial).
"""

import json
import logging

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from inventory.forms import (
    AssetForm, AssetTransferForm, EmployeeAssetForm,
    StockItemForm, StockQuickUpdateForm,
    TicketForm, TicketUpdateForm,
)
from inventory.models import (
    Asset, AssetStatus, AssetTransfer,
    StockItem, StockTransaction, TransactionType,
    Ticket, TicketPriority, TicketStatus,
)

logger = logging.getLogger(__name__)
User = get_user_model()


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _is_manager(user) -> bool:
    return user.is_staff or user.is_superuser


# ─────────────────────────────────────────────────────────────────────────────
# VUE 1 : Tableau de bord principal (point d'entrée + tutoriel)
# ─────────────────────────────────────────────────────────────────────────────

@login_required
def inventory_dashboard(request):
    """
    Page d'accueil du module Inventory.
    - Affiche la boîte de dialogue tutoriel si l'employé ne l'a pas encore vu.
    - Vue bifurquée : Manager → Warehouse, Employé → Mon Bureau Digital.
    """
    user = request.user

    # Statistiques rapides communes
    my_assets = Asset.objects.filter(
        assigned_to=user,
        status=AssetStatus.ASSIGNED
    ).select_related().order_by('category', 'name')

    my_tickets = Ticket.objects.filter(
        submitted_by=user
    ).order_by('-created_at')[:5]

    context = {
        'my_assets': my_assets,
        'my_assets_count': my_assets.count(),
        'my_tickets': my_tickets,
        'show_tutorial': not user.has_seen_inventory_tutorial,
    }

    if _is_manager(user):
        # Données supplémentaires pour les managers
        all_items = StockItem.objects.all()
        low_stock_items = [i for i in all_items if i.is_low_stock]

        open_tickets = Ticket.objects.filter(
            status__in=[TicketStatus.OPEN, TicketStatus.IN_PROGRESS]
        ).select_related('submitted_by').order_by('-created_at')

        total_assets = Asset.objects.count()
        available_assets = Asset.objects.filter(status=AssetStatus.AVAILABLE).count()

        context.update({
            'is_manager': True,
            'low_stock_items': low_stock_items,
            'low_stock_count': len(low_stock_items),
            'open_tickets': open_tickets,
            'open_tickets_count': open_tickets.count(),
            'total_assets': total_assets,
            'available_assets': available_assets,
            'total_stock_items': StockItem.objects.count(),
        })

    return render(request, 'inventory/dashboard.html', context)


# ─────────────────────────────────────────────────────────────────────────────
# VUE 2 : Tutoriel — marquer comme vu (AJAX)
# ─────────────────────────────────────────────────────────────────────────────

@login_required
@require_POST
def mark_tutorial_seen(request):
    """Endpoint AJAX pour marquer le tutoriel dashboard comme vu."""
    user = request.user
    user.has_seen_inventory_tutorial = True
    user.save(update_fields=['has_seen_inventory_tutorial'])
    return JsonResponse({'success': True})


@login_required
@require_POST
def mark_warehouse_tutorial_seen(request):
    """Endpoint AJAX pour marquer le tutoriel entrepôt comme vu."""
    user = request.user
    user.has_seen_warehouse_tutorial = True
    user.save(update_fields=['has_seen_warehouse_tutorial'])
    return JsonResponse({'success': True})


# ─────────────────────────────────────────────────────────────────────────────
# VUE 3 : Warehouse Manager (onglets Stock Global + Actifs)
# ─────────────────────────────────────────────────────────────────────────────

@login_required
def warehouse_manager(request):
    """Vue réservée aux managers : gestion du stock et des actifs."""
    if not _is_manager(request.user):
        messages.error(request, _('Accès réservé aux responsables stock.'))
        return redirect('inventory:dashboard')

    tab = request.GET.get('tab', 'stock')

    context = {
        'tab': tab,
        'stock_items': stock_items,
        'stock_form': stock_form,
        'quick_form': quick_form,
        'show_tutorial': not request.user.has_seen_warehouse_tutorial,
    }

    # ── Onglet Actifs ──
    assets = (
        Asset.objects.all()
        .select_related('assigned_to')
        .order_by('category', 'status', 'name')
    )
    asset_form = AssetForm()

    # ── Transactions récentes ──
    recent_transactions = (
        StockTransaction.objects
        .select_related('item', 'performed_by')
        .order_by('-timestamp')[:20]
    )

    context = {
        'tab': tab,
        'stock_items': stock_items,
        'stock_form': stock_form,
        'quick_form': quick_form,
        'assets': assets,
        'asset_form': asset_form,
        'recent_transactions': recent_transactions,
        'low_stock_count': sum(1 for i in stock_items if i.is_low_stock),
    }
    return render(request, 'inventory/warehouse.html', context)


# ─────────────────────────────────────────────────────────────────────────────
# VUE 4 : Créer / Modifier un article de stock
# ─────────────────────────────────────────────────────────────────────────────

@login_required
def stock_item_create(request):
    if not _is_manager(request.user):
        return JsonResponse({'error': _('Accès refusé.')}, status=403)

    if request.method == 'POST':
        form = StockItemForm(request.POST)
        if form.is_valid():
            item = form.save()
            messages.success(
                request,
                _(f'Article « {item.name} » ajouté au stock.')
            )
            return redirect('inventory:warehouse')
        else:
            messages.error(request, _('Formulaire invalide. Vérifiez les champs.'))
            return redirect('inventory:warehouse')
    return redirect('inventory:warehouse')


@login_required
def stock_item_edit(request, pk):
    if not _is_manager(request.user):
        return JsonResponse({'error': _('Accès refusé.')}, status=403)

    item = get_object_or_404(StockItem, pk=pk)
    if request.method == 'POST':
        form = StockItemForm(request.POST, instance=item)
        if form.is_valid():
            form.save()
            messages.success(request, _(f'Article « {item.name} » mis à jour.'))
        else:
            messages.error(request, _('Formulaire invalide.'))
    return redirect('inventory:warehouse')


# ─────────────────────────────────────────────────────────────────────────────
# VUE 5 : Mise à jour rapide du stock (AJAX +/-)
# ─────────────────────────────────────────────────────────────────────────────

@login_required
@require_POST
def stock_quick_update(request):
    """
    Endpoint AJAX : incrémente ou décrémente la quantité d'un article de stock.
    Attend : { item_id, delta (positif = entrée, négatif = sortie), reason }
    """
    if not _is_manager(request.user):
        return JsonResponse({'error': _('Accès refusé.')}, status=403)

    try:
        data = json.loads(request.body)
        item_id = int(data['item_id'])
        delta = int(data['delta'])
        reason = str(data.get('reason', ''))[:200]
    except (json.JSONDecodeError, KeyError, ValueError):
        return JsonResponse({'error': _('Données invalides.')}, status=400)

    item = get_object_or_404(StockItem, pk=item_id)

    if delta == 0:
        return JsonResponse({'error': _('Delta ne peut pas être zéro.')}, status=400)

    new_qty = item.quantity + delta
    if new_qty < 0:
        return JsonResponse({
            'error': _(f'Quantité insuffisante. Stock actuel : {item.quantity} {item.unit}.')
        }, status=400)

    with transaction.atomic():
        qty_before = item.quantity
        item.quantity = new_qty
        item.save(update_fields=['quantity', 'updated_at'])

        StockTransaction.objects.create(
            item=item,
            transaction_type=TransactionType.IN if delta > 0 else TransactionType.OUT,
            quantity=abs(delta),
            quantity_before=qty_before,
            quantity_after=new_qty,
            performed_by=request.user,
            reason=reason,
        )

    return JsonResponse({
        'success': True,
        'new_quantity': item.quantity,
        'stock_level': item.stock_level,
        'stock_level_color': item.stock_level_color,
        'is_low_stock': item.is_low_stock,
        'stock_percentage': item.stock_percentage,
    })


# ─────────────────────────────────────────────────────────────────────────────
# VUE 6 : Mes Actifs (Vue employé)
# ─────────────────────────────────────────────────────────────────────────────

@login_required
def my_assets(request):
    """Vue employé : liste des actifs personnels et option de transfert P2P."""
    user = request.user

    assets = (
        Asset.objects.filter(assigned_to=user, status=AssetStatus.ASSIGNED)
        .order_by('category', 'name')
    )

    # Historique des transferts reçus/envoyés
    transfers = (
        AssetTransfer.objects.filter(
            Q(from_employee=user) | Q(to_employee=user)
        )
        .select_related('asset', 'from_employee', 'to_employee')
        .order_by('-transferred_at')[:10]
    )

    context = {
        'assets': assets,
        'assets_count': assets.count(),
        'transfers': transfers,
        'form': EmployeeAssetForm(),
    }
    return render(request, 'inventory/my_assets.html', context)


@login_required
def asset_detail(request, pk):
    """Détail d'un actif + formulaire de transfert P2P."""
    asset = get_object_or_404(Asset, pk=pk)
    user = request.user

    # Seul le propriétaire actuel ou un manager peut accéder
    if asset.assigned_to != user and not _is_manager(user):
        messages.error(request, _('Cet actif ne vous appartient pas.'))
        return redirect('inventory:my_assets')

    transfer_form = AssetTransferForm(exclude_user=user)

    if request.method == 'POST' and 'transfer' in request.POST:
        transfer_form = AssetTransferForm(request.POST, exclude_user=user)
        if transfer_form.is_valid():
            to_employee = transfer_form.cleaned_data['to_employee']
            notes = transfer_form.cleaned_data.get('notes', '')

            with transaction.atomic():
                AssetTransfer.objects.create(
                    asset=asset,
                    from_employee=asset.assigned_to,
                    to_employee=to_employee,
                    transferred_by=user,
                    notes=notes,
                )
                asset.assigned_to = to_employee
                asset.assigned_at = timezone.now()
                asset.save(update_fields=['assigned_to', 'assigned_at', 'updated_at'])

            messages.success(
                request,
                _(f'Actif transféré à {to_employee.get_full_name() or to_employee.username}.')
            )
            return redirect('inventory:my_assets')

    context = {
        'asset': asset,
        'transfer_form': transfer_form,
        'transfer_history': asset.transfers.select_related(
            'from_employee', 'to_employee', 'transferred_by'
        ).order_by('-transferred_at'),
    }
    return render(request, 'inventory/asset_detail.html', context)


@login_required
def asset_create(request):
    """Créer un nouvel actif (managers uniquement)."""
    if not _is_manager(request.user):
        messages.error(request, _('Accès réservé aux managers.'))
        return redirect('inventory:dashboard')

    if request.method == 'POST':
        form = AssetForm(request.POST)
        if form.is_valid():
            asset = form.save()
            messages.success(request, _(f'Actif {asset.tag_amn} créé.'))
            return redirect('inventory:warehouse')
        messages.error(request, _('Formulaire invalide.'))
    return redirect('inventory:warehouse')


@login_required
def asset_self_add(request):
    """Permet à un employé d'ajouter un équipement à son propre bureau digital."""
    if request.method == 'POST':
        form = EmployeeAssetForm(request.POST)
        if form.is_valid():
            asset = form.save(commit=False)
            asset.assigned_to = request.user
            asset.status = AssetStatus.ASSIGNED
            asset.assigned_at = timezone.now()
            asset.save()
            messages.success(
                request,
                _(f'Équipement « {asset.name} » ajouté à votre bureau digital.')
            )
            return redirect('inventory:my_assets')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
    return redirect('inventory:my_assets')


# ─────────────────────────────────────────────────────────────────────────────
# VUE 7 : Helpdesk / Tickets SOS
# ─────────────────────────────────────────────────────────────────────────────

@login_required
def helpdesk(request):
    """Liste des tickets de l'employé + formulaire de création."""
    user = request.user

    if _is_manager(user):
        # Les managers voient tous les tickets
        tickets = (
            Ticket.objects.all()
            .select_related('submitted_by', 'assigned_to', 'asset')
            .order_by('-created_at')
        )
    else:
        tickets = (
            Ticket.objects.filter(submitted_by=user)
            .select_related('asset')
            .order_by('-created_at')
        )

    form = TicketForm()

    # Stats pour les managers
    stats = {}
    if _is_manager(user):
        stats = {
            'open': tickets.filter(status=TicketStatus.OPEN).count(),
            'in_progress': tickets.filter(status=TicketStatus.IN_PROGRESS).count(),
            'resolved': tickets.filter(status=TicketStatus.RESOLVED).count(),
            'critical': tickets.filter(priority=TicketPriority.CRITICAL).count(),
        }

    context = {
        'tickets': tickets,
        'form': form,
        'is_manager': _is_manager(user),
        'stats': stats,
    }
    return render(request, 'inventory/helpdesk.html', context)


@login_required
@require_POST
def ticket_create(request):
    """Créer un nouveau ticket de support."""
    form = TicketForm(request.POST, request.FILES)
    if form.is_valid():
        ticket = form.save(commit=False)
        ticket.submitted_by = request.user
        ticket.save()

        priority_label = ticket.get_priority_display()
        messages.success(
            request,
            _(f'Ticket {ticket.ticket_number} créé avec priorité {priority_label}.')
        )
        return redirect('inventory:ticket_detail', pk=ticket.pk)

    # En cas d'erreur, redirige avec les erreurs dans le message
    for field, errors in form.errors.items():
        for error in errors:
            messages.error(request, f'{field}: {error}')
    return redirect('inventory:helpdesk')


@login_required
def ticket_detail(request, pk):
    """Détail d'un ticket + formulaire de mise à jour (managers)."""
    ticket = get_object_or_404(
        Ticket.objects.select_related('submitted_by', 'assigned_to', 'asset'),
        pk=pk
    )
    user = request.user

    # Seul le soumetteur ou un manager peut voir le ticket
    if ticket.submitted_by != user and not _is_manager(user):
        messages.error(request, _('Accès refusé à ce ticket.'))
        return redirect('inventory:helpdesk')

    update_form = None
    if _is_manager(user):
        update_form = TicketUpdateForm(instance=ticket)

        if request.method == 'POST':
            update_form = TicketUpdateForm(request.POST, instance=ticket)
            if update_form.is_valid():
                updated_ticket = update_form.save(commit=False)
                if (updated_ticket.status == TicketStatus.RESOLVED
                        and not updated_ticket.resolved_at):
                    updated_ticket.resolved_at = timezone.now()
                updated_ticket.save()
                messages.success(request, _('Ticket mis à jour.'))
                return redirect('inventory:ticket_detail', pk=pk)

    context = {
        'ticket': ticket,
        'update_form': update_form,
        'is_manager': _is_manager(user),
    }
    return render(request, 'inventory/ticket_detail.html', context)


# ─────────────────────────────────────────────────────────────────────────────
# VUE 8 : Scan QR Code (AJAX)
# ─────────────────────────────────────────────────────────────────────────────

@login_required
@require_POST
def qr_lookup(request):
    """
    Endpoint AJAX : reçoit un tag_amn scanné par QR code
    et retourne les infos de l'actif correspondant.
    """
    try:
        data = json.loads(request.body)
        tag = str(data.get('tag', '')).strip().upper()
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'error': _('Données invalides.')}, status=400)

    if not tag:
        return JsonResponse({'error': _('Tag vide.')}, status=400)

    try:
        asset = Asset.objects.select_related('assigned_to').get(tag_amn=tag)
        return JsonResponse({
            'success': True,
            'asset': {
                'id': asset.pk,
                'tag_amn': asset.tag_amn,
                'name': asset.name,
                'category': asset.get_category_display(),
                'status': asset.get_status_display(),
                'status_key': asset.status,
                'assigned_to': (
                    asset.assigned_to.get_full_name() or asset.assigned_to.username
                ) if asset.assigned_to else None,
                'brand': asset.brand,
                'model_name': asset.model_name,
            }
        })
    except Asset.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': _(f'Aucun actif trouvé avec le tag « {tag} ».')
        }, status=404)
