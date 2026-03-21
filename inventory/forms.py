"""
Formulaires — Module Inventory.
"""

from django import forms
from django.utils.translation import gettext_lazy as _

from inventory.models import Asset, StockItem, StockTransaction, Ticket, TransactionType


# ─────────────────────────────────────────────────────────────────────────────
# FORMULAIRE : Asset
# ─────────────────────────────────────────────────────────────────────────────

class AssetForm(forms.ModelForm):
    class Meta:
        model = Asset
        fields = [
            'tag_amn', 'name', 'category', 'brand', 'model_name',
            'serial_number', 'status', 'assigned_to',
            'purchase_date', 'purchase_price', 'notes',
        ]
        widgets = {
            'tag_amn': forms.TextInput(attrs={
                'class': 'w-full rounded-xl border border-slate-200 px-4 py-3 text-sm focus:ring-2 focus:ring-navy-500 focus:border-transparent',
                'placeholder': 'ex: AMN-IT-2025-001',
            }),
            'name': forms.TextInput(attrs={
                'class': 'w-full rounded-xl border border-slate-200 px-4 py-3 text-sm focus:ring-2 focus:ring-navy-500 focus:border-transparent',
                'placeholder': _('Désignation de l\'équipement'),
            }),
            'category': forms.Select(attrs={
                'class': 'w-full rounded-xl border border-slate-200 px-4 py-3 text-sm focus:ring-2 focus:ring-navy-500 focus:border-transparent',
            }),
            'brand': forms.TextInput(attrs={
                'class': 'w-full rounded-xl border border-slate-200 px-4 py-3 text-sm focus:ring-2 focus:ring-navy-500 focus:border-transparent',
                'placeholder': 'Dell, HP, Lenovo…',
            }),
            'model_name': forms.TextInput(attrs={
                'class': 'w-full rounded-xl border border-slate-200 px-4 py-3 text-sm focus:ring-2 focus:ring-navy-500 focus:border-transparent',
            }),
            'serial_number': forms.TextInput(attrs={
                'class': 'w-full rounded-xl border border-slate-200 px-4 py-3 text-sm focus:ring-2 focus:ring-navy-500 focus:border-transparent',
            }),
            'status': forms.Select(attrs={
                'class': 'w-full rounded-xl border border-slate-200 px-4 py-3 text-sm focus:ring-2 focus:ring-navy-500 focus:border-transparent',
            }),
            'assigned_to': forms.Select(attrs={
                'class': 'w-full rounded-xl border border-slate-200 px-4 py-3 text-sm focus:ring-2 focus:ring-navy-500 focus:border-transparent',
            }),
            'purchase_date': forms.DateInput(attrs={
                'class': 'w-full rounded-xl border border-slate-200 px-4 py-3 text-sm focus:ring-2 focus:ring-navy-500 focus:border-transparent',
                'type': 'date',
            }),
            'purchase_price': forms.NumberInput(attrs={
                'class': 'w-full rounded-xl border border-slate-200 px-4 py-3 text-sm focus:ring-2 focus:ring-navy-500 focus:border-transparent',
                'placeholder': '0',
            }),
            'notes': forms.Textarea(attrs={
                'class': 'w-full rounded-xl border border-slate-200 px-4 py-3 text-sm focus:ring-2 focus:ring-navy-500 focus:border-transparent',
                'rows': 3,
            }),
        }


class AssetTransferForm(forms.Form):
    """Formulaire de transfert P2P d'un actif."""
    to_employee = forms.ModelChoiceField(
        queryset=None,
        label=_('Transférer à'),
        widget=forms.Select(attrs={
            'class': 'w-full rounded-xl border border-slate-200 px-4 py-3 text-sm focus:ring-2 focus:ring-navy-500 focus:border-transparent',
        })
    )
    notes = forms.CharField(
        required=False,
        label=_('Notes'),
        widget=forms.Textarea(attrs={
            'class': 'w-full rounded-xl border border-slate-200 px-4 py-3 text-sm focus:ring-2 focus:ring-navy-500 focus:border-transparent',
            'rows': 2,
        })
    )

    def __init__(self, *args, exclude_user=None, **kwargs):
        super().__init__(*args, **kwargs)
        from django.contrib.auth import get_user_model
        User = get_user_model()
        qs = User.objects.filter(is_active=True)
        if exclude_user:
            qs = qs.exclude(pk=exclude_user.pk)
        self.fields['to_employee'].queryset = qs


# ─────────────────────────────────────────────────────────────────────────────
# FORMULAIRE : StockItem
# ─────────────────────────────────────────────────────────────────────────────

class StockItemForm(forms.ModelForm):
    class Meta:
        model = StockItem
        fields = [
            'name', 'description', 'category', 'sku',
            'quantity', 'alert_threshold', 'unit', 'location', 'supplier',
        ]
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'w-full rounded-xl border border-slate-200 px-4 py-3 text-sm focus:ring-2 focus:ring-navy-500 focus:border-transparent',
                'placeholder': _('Nom de l\'article'),
            }),
            'description': forms.Textarea(attrs={
                'class': 'w-full rounded-xl border border-slate-200 px-4 py-3 text-sm focus:ring-2 focus:ring-navy-500 focus:border-transparent',
                'rows': 2,
            }),
            'category': forms.TextInput(attrs={
                'class': 'w-full rounded-xl border border-slate-200 px-4 py-3 text-sm focus:ring-2 focus:ring-navy-500 focus:border-transparent',
                'placeholder': 'Papeterie, Informatique…',
            }),
            'sku': forms.TextInput(attrs={
                'class': 'w-full rounded-xl border border-slate-200 px-4 py-3 text-sm focus:ring-2 focus:ring-navy-500 focus:border-transparent',
            }),
            'quantity': forms.NumberInput(attrs={
                'class': 'w-full rounded-xl border border-slate-200 px-4 py-3 text-sm focus:ring-2 focus:ring-navy-500 focus:border-transparent',
                'min': '0',
            }),
            'alert_threshold': forms.NumberInput(attrs={
                'class': 'w-full rounded-xl border border-slate-200 px-4 py-3 text-sm focus:ring-2 focus:ring-navy-500 focus:border-transparent',
                'min': '0',
            }),
            'unit': forms.TextInput(attrs={
                'class': 'w-full rounded-xl border border-slate-200 px-4 py-3 text-sm focus:ring-2 focus:ring-navy-500 focus:border-transparent',
                'placeholder': 'unité, boîte, rame…',
            }),
            'location': forms.TextInput(attrs={
                'class': 'w-full rounded-xl border border-slate-200 px-4 py-3 text-sm focus:ring-2 focus:ring-navy-500 focus:border-transparent',
                'placeholder': 'Étagère A3, Bureau IT…',
            }),
            'supplier': forms.TextInput(attrs={
                'class': 'w-full rounded-xl border border-slate-200 px-4 py-3 text-sm focus:ring-2 focus:ring-navy-500 focus:border-transparent',
            }),
        }


class StockQuickUpdateForm(forms.Form):
    """Formulaire rapide +/- pour la mise à jour instantanée du stock."""
    item_id = forms.IntegerField(widget=forms.HiddenInput())
    delta = forms.IntegerField(
        label=_('Quantité'),
        widget=forms.NumberInput(attrs={
            'class': 'w-24 rounded-xl border border-slate-200 px-3 py-2 text-sm text-center focus:ring-2 focus:ring-navy-500',
            'min': '1',
        })
    )
    reason = forms.CharField(
        required=False,
        label=_('Motif'),
        widget=forms.TextInput(attrs={
            'class': 'w-full rounded-xl border border-slate-200 px-4 py-3 text-sm focus:ring-2 focus:ring-navy-500 focus:border-transparent',
            'placeholder': _('Motif du mouvement (optionnel)'),
        })
    )


# ─────────────────────────────────────────────────────────────────────────────
# FORMULAIRE : Ticket
# ─────────────────────────────────────────────────────────────────────────────

class TicketForm(forms.ModelForm):
    class Meta:
        model = Ticket
        fields = ['title', 'description', 'photo', 'priority', 'asset']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'w-full rounded-xl border border-slate-200 px-4 py-3 text-sm focus:ring-2 focus:ring-navy-500 focus:border-transparent',
                'placeholder': _('Décrivez le problème en une phrase'),
            }),
            'description': forms.Textarea(attrs={
                'class': 'w-full rounded-xl border border-slate-200 px-4 py-3 text-sm focus:ring-2 focus:ring-navy-500 focus:border-transparent',
                'rows': 4,
                'placeholder': _('Détaillez le problème, les étapes pour le reproduire, etc.'),
            }),
            'photo': forms.FileInput(attrs={
                'class': 'w-full rounded-xl border border-slate-200 px-4 py-3 text-sm focus:ring-2 focus:ring-navy-500',
                'accept': 'image/*',
            }),
            'priority': forms.Select(attrs={
                'class': 'w-full rounded-xl border border-slate-200 px-4 py-3 text-sm focus:ring-2 focus:ring-navy-500 focus:border-transparent',
            }),
            'asset': forms.Select(attrs={
                'class': 'w-full rounded-xl border border-slate-200 px-4 py-3 text-sm focus:ring-2 focus:ring-navy-500 focus:border-transparent',
            }),
        }


class TicketUpdateForm(forms.ModelForm):
    """Formulaire de mise à jour du ticket (admin/manager)."""
    class Meta:
        model = Ticket
        fields = ['status', 'assigned_to', 'admin_note']
        widgets = {
            'status': forms.Select(attrs={
                'class': 'w-full rounded-xl border border-slate-200 px-4 py-3 text-sm focus:ring-2 focus:ring-navy-500',
            }),
            'assigned_to': forms.Select(attrs={
                'class': 'w-full rounded-xl border border-slate-200 px-4 py-3 text-sm focus:ring-2 focus:ring-navy-500',
            }),
            'admin_note': forms.Textarea(attrs={
                'class': 'w-full rounded-xl border border-slate-200 px-4 py-3 text-sm focus:ring-2 focus:ring-navy-500',
                'rows': 3,
            }),
        }
