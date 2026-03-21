"""
Signaux Django — Module Inventory.
Déclenche les alertes Celery après chaque mouvement de stock ou nouveau ticket.
"""

from django.db.models.signals import post_save
from django.dispatch import receiver

from inventory.models import StockTransaction, Ticket, TicketStatus, TransactionType


@receiver(post_save, sender=StockTransaction)
def on_stock_transaction_saved(sender, instance, created, **kwargs):
    """Après chaque sortie de stock, vérifie si le seuil d'alerte est atteint."""
    if not created:
        return
    if instance.transaction_type == TransactionType.OUT:
        item = instance.item
        if item.is_low_stock:
            from inventory.tasks import send_low_stock_alert
            send_low_stock_alert.delay(item.pk)


@receiver(post_save, sender=Ticket)
def on_ticket_saved(sender, instance, created, **kwargs):
    """Après la création d'un ticket critique/SOS, alerte l'équipe IT."""
    if not created:
        return
    from inventory.models import TicketPriority
    if instance.priority in (TicketPriority.HIGH, TicketPriority.CRITICAL):
        from inventory.tasks import send_new_sos_ticket_alert
        send_new_sos_ticket_alert.delay(instance.pk)
