"""
Modèles du module Inventory — AMN Employee Hub.
Contient : Asset, StockItem, StockTransaction, Ticket, StockAuditLog.
"""

import uuid
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


# ─────────────────────────────────────────────────────────────────────────────
# CHOIX (Choices)
# ─────────────────────────────────────────────────────────────────────────────

class AssetCategory(models.TextChoices):
    LAPTOP      = 'LAPTOP',    _('Ordinateur portable')
    DESKTOP     = 'DESKTOP',   _('Ordinateur fixe')
    PHONE       = 'PHONE',     _('Téléphone')
    TABLET      = 'TABLET',    _('Tablette')
    MONITOR     = 'MONITOR',   _('Écran')
    PRINTER     = 'PRINTER',   _('Imprimante')
    VEHICLE     = 'VEHICLE',   _('Véhicule')
    NETWORK     = 'NETWORK',   _('Équipement réseau')
    FURNITURE   = 'FURNITURE', _('Mobilier')
    OTHER       = 'OTHER',     _('Autre')


class AssetStatus(models.TextChoices):
    AVAILABLE   = 'AVAILABLE',   _('Disponible')
    ASSIGNED    = 'ASSIGNED',    _('Attribué')
    IN_REPAIR   = 'IN_REPAIR',   _('En réparation')
    RETIRED     = 'RETIRED',     _('Retraité')
    LOST        = 'LOST',        _('Perdu / Volé')


class TransactionType(models.TextChoices):
    IN  = 'IN',  _('Entrée stock')
    OUT = 'OUT', _('Sortie stock')


class TicketPriority(models.TextChoices):
    LOW      = 'LOW',      _('Basse')
    MEDIUM   = 'MEDIUM',   _('Moyenne')
    HIGH     = 'HIGH',     _('Haute')
    CRITICAL = 'CRITICAL', _('Critique / SOS')


class TicketStatus(models.TextChoices):
    OPEN        = 'OPEN',        _('Ouvert')
    IN_PROGRESS = 'IN_PROGRESS', _('En cours')
    RESOLVED    = 'RESOLVED',    _('Résolu')
    CLOSED      = 'CLOSED',      _('Fermé')


# ─────────────────────────────────────────────────────────────────────────────
# MODÈLE : Asset (Actif individuel)
# ─────────────────────────────────────────────────────────────────────────────

class Asset(models.Model):
    """Équipement individuel traçable par tag AMN."""

    tag_amn = models.CharField(
        max_length=30,
        unique=True,
        verbose_name=_('Tag AMN'),
        help_text=_('Identifiant unique du matériel (ex: AMN-IT-2025-001)')
    )
    name = models.CharField(
        max_length=150,
        verbose_name=_('Désignation')
    )
    category = models.CharField(
        max_length=20,
        choices=AssetCategory.choices,
        default=AssetCategory.OTHER,
        verbose_name=_('Catégorie')
    )
    brand = models.CharField(
        max_length=80,
        blank=True,
        verbose_name=_('Marque')
    )
    model_name = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_('Modèle')
    )
    serial_number = models.CharField(
        max_length=100,
        blank=True,
        unique=True,
        null=True,
        verbose_name=_('Numéro de série')
    )
    status = models.CharField(
        max_length=15,
        choices=AssetStatus.choices,
        default=AssetStatus.AVAILABLE,
        verbose_name=_('Statut')
    )
    assigned_to = models.ForeignKey(
        'users.Employee',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_assets',
        verbose_name=_('Attribué à')
    )
    assigned_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Date d'attribution")
    )
    purchase_date = models.DateField(
        null=True,
        blank=True,
        verbose_name=_("Date d'achat")
    )
    purchase_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name=_("Prix d'achat (FCFA)")
    )
    notes = models.TextField(
        blank=True,
        verbose_name=_('Notes')
    )
    qr_code_data = models.CharField(
        max_length=200,
        blank=True,
        verbose_name=_('Données QR Code')
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_('Créé le'))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_('Modifié le'))

    class Meta:
        verbose_name = _('Actif')
        verbose_name_plural = _('Actifs')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['tag_amn']),
            models.Index(fields=['status', 'category']),
            models.Index(fields=['assigned_to']),
        ]

    def __str__(self):
        return f'[{self.tag_amn}] {self.name}'

    def save(self, *args, **kwargs):
        if not self.qr_code_data:
            self.qr_code_data = self.tag_amn
        super().save(*args, **kwargs)

    @property
    def status_color(self):
        return {
            AssetStatus.AVAILABLE: 'emerald',
            AssetStatus.ASSIGNED:  'blue',
            AssetStatus.IN_REPAIR: 'amber',
            AssetStatus.RETIRED:   'slate',
            AssetStatus.LOST:      'red',
        }.get(self.status, 'slate')


# ─────────────────────────────────────────────────────────────────────────────
# MODÈLE : AssetTransfer (Transfert P2P)
# ─────────────────────────────────────────────────────────────────────────────

class AssetTransfer(models.Model):
    """Historique des transferts d'actifs entre employés."""

    asset = models.ForeignKey(
        Asset,
        on_delete=models.CASCADE,
        related_name='transfers',
        verbose_name=_('Actif')
    )
    from_employee = models.ForeignKey(
        'users.Employee',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='transfers_out',
        verbose_name=_('De')
    )
    to_employee = models.ForeignKey(
        'users.Employee',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='transfers_in',
        verbose_name=_('Vers')
    )
    transferred_by = models.ForeignKey(
        'users.Employee',
        on_delete=models.SET_NULL,
        null=True,
        related_name='transfers_managed',
        verbose_name=_('Effectué par')
    )
    transferred_at = models.DateTimeField(
        default=timezone.now,
        verbose_name=_('Date du transfert')
    )
    notes = models.TextField(blank=True, verbose_name=_('Notes'))

    class Meta:
        verbose_name = _('Transfert d\'actif')
        verbose_name_plural = _('Transferts d\'actifs')
        ordering = ['-transferred_at']

    def __str__(self):
        return f'{self.asset.tag_amn} → {self.to_employee} ({self.transferred_at:%Y-%m-%d})'


# ─────────────────────────────────────────────────────────────────────────────
# MODÈLE : StockItem (Consommable/Stock global)
# ─────────────────────────────────────────────────────────────────────────────

class StockItem(models.Model):
    """Article de stock consommable (câbles, papier, cartouches, etc.)."""

    name = models.CharField(
        max_length=150,
        verbose_name=_('Désignation')
    )
    description = models.TextField(
        blank=True,
        verbose_name=_('Description')
    )
    category = models.CharField(
        max_length=80,
        blank=True,
        verbose_name=_('Catégorie')
    )
    sku = models.CharField(
        max_length=60,
        blank=True,
        verbose_name=_('Référence / SKU')
    )
    quantity = models.PositiveIntegerField(
        default=0,
        verbose_name=_('Quantité en stock')
    )
    alert_threshold = models.PositiveIntegerField(
        default=10,
        verbose_name=_("Seuil d'alerte"),
        help_text=_('Notification envoyée quand la quantité atteint ce seuil')
    )
    unit = models.CharField(
        max_length=20,
        default='unité',
        verbose_name=_('Unité')
    )
    location = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_('Emplacement')
    )
    supplier = models.CharField(
        max_length=150,
        blank=True,
        verbose_name=_('Fournisseur')
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_('Créé le'))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_('Modifié le'))

    class Meta:
        verbose_name = _('Article de stock')
        verbose_name_plural = _('Articles de stock')
        ordering = ['name']
        indexes = [
            models.Index(fields=['category']),
            models.Index(fields=['quantity', 'alert_threshold']),
        ]

    def __str__(self):
        return f'{self.name} ({self.quantity} {self.unit})'

    @property
    def is_low_stock(self):
        return self.quantity <= self.alert_threshold

    @property
    def is_empty(self):
        return self.quantity == 0

    @property
    def stock_level(self):
        if self.quantity == 0:
            return 'empty'
        if self.quantity <= self.alert_threshold:
            return 'low'
        if self.quantity <= self.alert_threshold * 2:
            return 'medium'
        return 'ok'

    @property
    def stock_level_color(self):
        return {
            'empty':  'red',
            'low':    'orange',
            'medium': 'amber',
            'ok':     'emerald',
        }.get(self.stock_level, 'slate')

    @property
    def stock_percentage(self):
        """Pourcentage de remplissage pour la barre de progression (max = 3× seuil)."""
        if self.alert_threshold == 0:
            return 100
        max_ref = self.alert_threshold * 3
        return min(100, int((self.quantity / max_ref) * 100))


# ─────────────────────────────────────────────────────────────────────────────
# MODÈLE : StockTransaction (Mouvement de stock)
# ─────────────────────────────────────────────────────────────────────────────

class StockTransaction(models.Model):
    """
    Enregistrement immuable de chaque mouvement de stock.
    Audit trail complet.
    """

    item = models.ForeignKey(
        StockItem,
        on_delete=models.CASCADE,
        related_name='transactions',
        verbose_name=_('Article')
    )
    transaction_type = models.CharField(
        max_length=3,
        choices=TransactionType.choices,
        verbose_name=_('Type')
    )
    quantity = models.PositiveIntegerField(
        verbose_name=_('Quantité')
    )
    quantity_before = models.PositiveIntegerField(
        default=0,
        verbose_name=_('Quantité avant')
    )
    quantity_after = models.PositiveIntegerField(
        default=0,
        verbose_name=_('Quantité après')
    )
    performed_by = models.ForeignKey(
        'users.Employee',
        on_delete=models.SET_NULL,
        null=True,
        related_name='stock_transactions',
        verbose_name=_('Effectué par')
    )
    reason = models.TextField(
        blank=True,
        verbose_name=_('Motif')
    )
    reference = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_('Référence (bon de commande, facture…)')
    )
    timestamp = models.DateTimeField(
        default=timezone.now,
        db_index=True,
        verbose_name=_('Horodatage')
    )

    class Meta:
        verbose_name = _('Mouvement de stock')
        verbose_name_plural = _('Mouvements de stock')
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['item', 'timestamp']),
            models.Index(fields=['transaction_type', 'timestamp']),
        ]

    def __str__(self):
        arrow = '↑' if self.transaction_type == TransactionType.IN else '↓'
        return (
            f'{arrow} {self.quantity} × {self.item.name} '
            f'({self.timestamp:%Y-%m-%d %H:%M})'
        )


# ─────────────────────────────────────────────────────────────────────────────
# MODÈLE : Ticket (Helpdesk / SOS)
# ─────────────────────────────────────────────────────────────────────────────

class Ticket(models.Model):
    """Ticket de support IT / helpdesk ouvert par un employé."""

    ticket_number = models.CharField(
        max_length=20,
        unique=True,
        blank=True,
        verbose_name=_('Numéro de ticket')
    )
    title = models.CharField(
        max_length=200,
        verbose_name=_('Sujet')
    )
    description = models.TextField(
        verbose_name=_('Description du problème')
    )
    photo = models.ImageField(
        upload_to='tickets/%Y/%m/',
        blank=True,
        null=True,
        verbose_name=_('Photo de la panne')
    )
    priority = models.CharField(
        max_length=10,
        choices=TicketPriority.choices,
        default=TicketPriority.MEDIUM,
        verbose_name=_('Priorité')
    )
    status = models.CharField(
        max_length=15,
        choices=TicketStatus.choices,
        default=TicketStatus.OPEN,
        verbose_name=_('Statut')
    )
    submitted_by = models.ForeignKey(
        'users.Employee',
        on_delete=models.CASCADE,
        related_name='tickets_submitted',
        verbose_name=_('Soumis par')
    )
    assigned_to = models.ForeignKey(
        'users.Employee',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='tickets_assigned',
        verbose_name=_('Assigné à')
    )
    asset = models.ForeignKey(
        Asset,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='tickets',
        verbose_name=_('Actif concerné')
    )
    admin_note = models.TextField(
        blank=True,
        verbose_name=_('Note interne')
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_('Créé le'))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_('Modifié le'))
    resolved_at = models.DateTimeField(
        null=True, blank=True, verbose_name=_('Résolu le')
    )

    class Meta:
        verbose_name = _('Ticket support')
        verbose_name_plural = _('Tickets support')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'priority']),
            models.Index(fields=['submitted_by', 'created_at']),
        ]

    def __str__(self):
        return f'[{self.ticket_number}] {self.title}'

    def save(self, *args, **kwargs):
        if not self.ticket_number:
            year = timezone.now().year
            last = (
                Ticket.objects.filter(ticket_number__startswith=f'TKT-{year}-')
                .order_by('-ticket_number')
                .first()
            )
            if last and last.ticket_number:
                try:
                    seq = int(last.ticket_number.split('-')[-1]) + 1
                except (ValueError, IndexError):
                    seq = 1
            else:
                seq = 1
            self.ticket_number = f'TKT-{year}-{seq:04d}'
        super().save(*args, **kwargs)

    @property
    def priority_color(self):
        return {
            TicketPriority.LOW:      'slate',
            TicketPriority.MEDIUM:   'blue',
            TicketPriority.HIGH:     'amber',
            TicketPriority.CRITICAL: 'red',
        }.get(self.priority, 'slate')

    @property
    def status_color(self):
        return {
            TicketStatus.OPEN:        'blue',
            TicketStatus.IN_PROGRESS: 'amber',
            TicketStatus.RESOLVED:    'emerald',
            TicketStatus.CLOSED:      'slate',
        }.get(self.status, 'slate')

    def resolve(self):
        self.status = TicketStatus.RESOLVED
        self.resolved_at = timezone.now()
        self.save(update_fields=['status', 'resolved_at', 'updated_at'])
