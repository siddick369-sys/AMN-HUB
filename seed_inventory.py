import os
import django
from django.utils import timezone

# Configurer Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'amn_hub.settings')
django.setup()

from inventory.models import Asset, AssetCategory, AssetStatus, StockItem, TransactionType, StockTransaction
from users.models import Employee

def seed_inventory():
    print("--- Début du seeding AMN Inventory ---")

    # 1. UTILISATEURS
    siddick = Employee.objects.filter(username='siddick').first()
    iren = Employee.objects.filter(username='iren').first()

    # 2. ACTIFS (ASSETS)
    # PC Siddick
    Asset.objects.get_or_create(
        tag_amn="AMN-IT-2025-001",
        defaults={
            'name': "MacBook Pro 14 M3",
            'category': AssetCategory.LAPTOP,
            'brand': "Apple",
            'model_name': "M3 Pro",
            'serial_number': "SN-MBP-001",
            'status': AssetStatus.ASSIGNED,
            'assigned_to': siddick,
            'assigned_at': timezone.now(),
            'purchase_price': 1500000
        }
    )

    # Routeur Site Douala
    Asset.objects.get_or_create(
        tag_amn="AMN-NET-2025-050",
        defaults={
            'name': "Mikrotik Cloud Core Router",
            'category': AssetCategory.NETWORK,
            'brand': "Mikrotik",
            'model_name': "CCR2004",
            'serial_number': "SN-MK-050",
            'status': AssetStatus.AVAILABLE,
            'purchase_price': 350000
        }
    )

    # 3. STOCK (CONSUMABLES)
    cable, _ = StockItem.objects.get_or_create(
        name="Câble Ethernet RJ45 Cat6 (1m)",
        defaults={
            'category': "Réseau",
            'sku': "CB-RJ45-1M",
            'quantity': 50,
            'alert_threshold': 10,
            'unit': "mètres"
        }
    )

    batterie, _ = StockItem.objects.get_or_create(
        name="Batterie Solaire 12V 200Ah",
        defaults={
            'category': "Énergie",
            'sku': "BAT-SOL-200",
            'quantity': 4,
            'alert_threshold': 5,
            'unit': "unités"
        }
    )

    # 4. TRANSACTION DE TEST
    if siddick:
        StockTransaction.objects.get_or_create(
            item=cable,
            transaction_type=TransactionType.OUT,
            quantity=5,
            defaults={
                'performed_by': siddick,
                'reason': "Installation site Bastos",
                'quantity_before': 55,
                'quantity_after': 50
            }
        )

    print("--- Seeding terminé avec succès ! ---")

if __name__ == "__main__":
    seed_inventory()
