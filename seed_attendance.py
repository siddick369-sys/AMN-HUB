import os
import django

# Configurer Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'amn_hub.settings')
django.setup()

from attendance.models import Office

def seed_attendance():
    print("--- Début du seeding AMN Attendance ---")

    # Siège Yaoundé
    Office.objects.get_or_create(
        name="Siège Social AMN - Yaoundé",
        defaults={
            'address': "Bastos, Yaoundé",
            'latitude': 3.8480,
            'longitude': 11.5021,
            'allowed_radius_meters': 500,
            'country': 'CM'
        }
    )

    # Agence Douala
    Office.objects.get_or_create(
        name="Agence Douala",
        defaults={
            'address': "Akwa, Douala",
            'latitude': 4.0511,
            'longitude': 9.7679,
            'allowed_radius_meters': 300,
            'country': 'CM'
        }
    )

    # Hub Lagos
    Office.objects.get_or_create(
        name="AMN Nigeria Hub - Lagos",
        defaults={
            'address': "Ikeja, Lagos",
            'latitude': 6.5244,
            'longitude': 3.3792,
            'allowed_radius_meters': 1000,
            'country': 'NG'
        }
    )

    print("--- Seeding terminé avec succès ! ---")

if __name__ == "__main__":
    seed_attendance()
