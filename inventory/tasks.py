"""
Tâches Celery — Module Inventory.
Alertes de stock bas, notifications SOS, audit trail.
"""

import logging

from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.translation import gettext as _

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_low_stock_alert(self, item_pk: int):
    """
    Envoie un email d'alerte aux managers quand un article de stock
    descend en-dessous du seuil d'alerte.
    """
    try:
        from inventory.models import StockItem
        from django.contrib.auth import get_user_model
        User = get_user_model()

        item = StockItem.objects.get(pk=item_pk)

        # Destinataires : staff et superusers
        admins = User.objects.filter(
            is_active=True,
            is_staff=True
        ).values_list('email', flat=True)
        recipients = [e for e in admins if e]

        if not recipients:
            logger.warning('send_low_stock_alert: aucun destinataire trouvé.')
            return

        subject = _(f'[AMN Hub] Alerte stock bas — {item.name}')
        context = {
            'item': item,
            'frontend_url': getattr(settings, 'FRONTEND_URL', 'http://localhost:8000'),
        }
        html_message = render_to_string('emails/inventory_low_stock.html', context)
        text_message = _(
            f'ALERTE STOCK BAS\n\n'
            f'Article : {item.name}\n'
            f'Quantité actuelle : {item.quantity} {item.unit}\n'
            f'Seuil d\'alerte : {item.alert_threshold} {item.unit}\n\n'
            f'Veuillez réapprovisionner cet article dès que possible.'
        )

        send_mail(
            subject=subject,
            message=text_message,
            html_message=html_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=recipients,
            fail_silently=False,
        )
        logger.info(
            'send_low_stock_alert: alerte envoyée pour %s à %d destinataire(s).',
            item.name, len(recipients)
        )

    except Exception as exc:
        logger.error('send_low_stock_alert error: %s', exc)
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_new_sos_ticket_alert(self, ticket_pk: int):
    """
    Envoie une alerte email aux managers/IT quand un ticket HIGH ou CRITICAL
    est ouvert.
    """
    try:
        from inventory.models import Ticket
        from django.contrib.auth import get_user_model
        User = get_user_model()

        ticket = Ticket.objects.select_related('submitted_by').get(pk=ticket_pk)

        admins = User.objects.filter(
            is_active=True,
            is_staff=True
        ).values_list('email', flat=True)
        recipients = [e for e in admins if e]

        if not recipients:
            logger.warning('send_new_sos_ticket_alert: aucun destinataire.')
            return

        label = ticket.get_priority_display()
        subject = _(f'[AMN Hub] 🆘 Nouveau ticket {label} — {ticket.ticket_number}')
        context = {
            'ticket': ticket,
            'frontend_url': getattr(settings, 'FRONTEND_URL', 'http://localhost:8000'),
        }
        html_message = render_to_string('emails/inventory_new_ticket.html', context)
        text_message = _(
            f'NOUVEAU TICKET SUPPORT\n\n'
            f'Ticket : {ticket.ticket_number}\n'
            f'Sujet : {ticket.title}\n'
            f'Priorité : {label}\n'
            f'Soumis par : {ticket.submitted_by.get_full_name() or ticket.submitted_by.username}\n\n'
            f'Description :\n{ticket.description}'
        )

        send_mail(
            subject=subject,
            message=text_message,
            html_message=html_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=recipients,
            fail_silently=False,
        )
        logger.info(
            'send_new_sos_ticket_alert: alerte envoyée pour %s.',
            ticket.ticket_number
        )

    except Exception as exc:
        logger.error('send_new_sos_ticket_alert error: %s', exc)
        raise self.retry(exc=exc)


@shared_task
def check_all_stock_levels():
    """
    Tâche planifiée (Celery Beat) : vérifie tous les articles de stock
    et envoie des alertes pour ceux dont le niveau est bas.
    Peut être planifiée quotidiennement.
    """
    from django.db.models import F
    from inventory.models import StockItem
    low_items = StockItem.objects.filter(quantity__lte=F('alert_threshold'))
    count = low_items.count()
    for item in low_items:
        send_low_stock_alert.delay(item.pk)
    logger.info('check_all_stock_levels: %d articles en alerte.', count)
