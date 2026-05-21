#!/usr/bin/env python
import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from accounts.models import User
from core.models import Agence, Ville
from learning.models import ClientChurn

print("Überprüfung der Datenbank...")
print(f"- Agences: {Agence.objects.count()}")
print(f"- Villes: {Ville.objects.count()}")
print(f"- ClientChurns: {ClientChurn.objects.count()}")
print(f"- Users: {User.objects.count()}")

# Erstelle Test-Agence, falls notwendig
if Agence.objects.count() == 0:
    ville = Ville.objects.create(nom="Kairouan", code="KR")
    agence = Agence.objects.create(nom="Test Agence", code="AG-TEST", ville=ville)
    print("\n✓ Test-Agence erstellt")

# Erstelle Test-User, falls notwendig
if User.objects.count() == 0:
    agence = Agence.objects.first()
    user = User.objects.create_user(
        username="testuser",
        password="testpass123",
        role="chef_agence",
        agence=agence,
        is_staff=False,
        is_superuser=False,
    )
    print("✓ Test-User erstellt (testuser / testpass123)")

print("\n✓ Setup abgeschlossen.")
