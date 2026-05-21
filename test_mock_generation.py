#!/usr/bin/env python
"""
Test script to verify dataset loading and mock generation without going through
the web UI. This directly tests the core functions.
"""

import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from accounts.models import User, Agence
from learning.models import ClientChurn
from core.mock_data import generer_mock_data

print("\n" + "=" * 70)
print("TEST: Mock Data Generation")
print("=" * 70)

# Get test user and agence
agence = Agence.objects.first()
user = User.objects.filter(role="chef_agence").first()

if not agence:
    print("❌ Keine Agence vorhanden!")
    exit(1)

if not user:
    print("❌ Kein User vorhanden!")
    exit(1)

print(f"\n✓ Test-Agence: {agence.nom}")
print(f"✓ Test-User: {user.username} ({user.role})")

# Count existing clients
clients_before = ClientChurn.objects.filter(dataset__agence=agence).count()
print(f"\n📊 Clients vor Mock-Generierung: {clients_before}")

try:
    print("\n🔧 Starte Mock-Generierung (50 Clients)...")
    generer_mock_data(agence_id=agence.id, user_id=user.id, nb_clients=50)

    clients_after = ClientChurn.objects.filter(dataset__agence=agence).count()
    print(f"✓ Mock-Generierung erfolgreich!")
    print(f"📊 Clients nach Mock-Generierung: {clients_after}")
    print(f"➕ Neue Clients hinzugefügt: {clients_after - clients_before}")

    # Sample some mock data
    sample_clients = ClientChurn.objects.filter(dataset__agence=agence).order_by(
        "-date_prediction"
    )[:3]
    print(f"\n📋 Sample Mock Clients:")
    for client in sample_clients:
        print(
            f"  - {client.client_id} ({client.nom}): Score={client.score_churn}, Churn={client.churn_predit}"
        )

    print("\n✅ Mock-Generierung TEST PASSED")

except Exception as e:
    print(f"\n❌ Fehler bei Mock-Generierung:")
    print(f"   {type(e).__name__}: {str(e)}")
    import traceback

    traceback.print_exc()
    exit(1)

print("\n" + "=" * 70)
print("Alle Tests abgeschlossen!")
print("=" * 70 + "\n")
