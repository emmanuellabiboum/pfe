#!/usr/bin/env python
"""
Script pour recalculer les scores churn de tous les clients
"""

import os
import sys
import django

# Configuration Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from learning.models import ClientChurn
from core.ml_service import predict_churn_score_from_client
from core.model_config import predict_churn_score

# Seuil aligné sur FastAPI (pfe_final/churn_api/app/config.py)
SEUIL_CHURN = 0.32
SEUIL_RISQUE_ELEVE = 0.32


def recalculer_tous_les_scores():
    clients = ClientChurn.objects.all()
    total = clients.count()

    print(f"Recalcul des scores pour {total} clients...")

    mis_a_jour = 0
    errors = 0

    for i, client in enumerate(clients, 1):
        try:
            # Essayer d'abord avec le vrai modèle ML
            score_ml = predict_churn_score_from_client(client)

            if score_ml is not None:
                score = score_ml
            else:
                # Fallback sur les règles métier si le modèle ML n'est pas disponible
                score = predict_churn_score(client)

            # Mettre à jour le client
            client.score_churn = score
            client.churn_predit = score >= SEUIL_CHURN
            client.save(update_fields=["score_churn", "churn_predit"])

            mis_a_jour += 1

            if i % 100 == 0:
                print(f"  Progression: {i}/{total} ({i/total*100:.1f}%)")

        except Exception as e:
            errors += 1
            print(f"  Erreur client {client.id}: {e}")

    print(f"\nTerminé!")
    print(f"  Mis à jour: {mis_a_jour}")
    print(f"  Erreurs: {errors}")

    # Statistiques finales
    print(f"\nNouvelle distribution:")
    print(
        f"  Risque élevé (>= {SEUIL_RISQUE_ELEVE}): {clients.filter(score_churn__gte=SEUIL_RISQUE_ELEVE).count()}"
    )
    print(
        f"  Risque faible (< {SEUIL_RISQUE_ELEVE}): {clients.filter(score_churn__lt=SEUIL_RISQUE_ELEVE).count()}"
    )


if __name__ == "__main__":
    recalculer_tous_les_scores()
