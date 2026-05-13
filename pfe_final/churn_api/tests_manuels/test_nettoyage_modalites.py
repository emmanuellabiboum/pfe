# =============================================================================
# tests_manuels/test_nettoyage_modalites.py
# Test du nettoyage automatique des modalités (Étape 8.2)
# =============================================================================

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd

from app.ml.loader        import charger_tous_artefacts
from app.ml.preprocessing import (
    nettoyer_modalite,
    nettoyer_modalites_dataframe,
    pretraiter_dataframe,
)
from app.ml.predictor     import predire_batch, analyser_portefeuille


# ⚠️ ADAPTE le chemin
CHEMIN_DATASET =  r"C:\pfe_final\dataset_modeling.csv"


# =============================================================================
# TEST 1 — Fonction unitaire nettoyer_modalite
# =============================================================================
print("=" * 70)
print("  TEST 1 — Fonction nettoyer_modalite (cas unitaires)")
print("=" * 70)

cas = [
    ("Forfait Illimité",          "Forfait_Illimite"),
    ("Forfait Mobile (Mixte)",    "Forfait_Mobile_Mixte"),
    ("Offre Prépayée",            "Offre_Prepayee"),
    ("Offre à Facture",           "Offre_a_Facture"),
    ("Excellent",                 "Excellent"),
    ("ticket_recharge",           "ticket_recharge"),
    ("URBAIN",                    "URBAIN"),
]

for entree, attendu in cas:
    resultat = nettoyer_modalite(entree)
    statut = "✓" if resultat == attendu else "✗"
    print(f"  {statut} {repr(entree):<30} → {repr(resultat):<30} (attendu : {repr(attendu)})")


# =============================================================================
# TEST 2 — Nettoyage d'un DataFrame complet
# =============================================================================
print("\n" + "=" * 70)
print("  TEST 2 — Nettoyage d'un DataFrame")
print("=" * 70)

df = pd.read_csv(CHEMIN_DATASET)
print(f"\n  Dataset chargé : {len(df)} lignes")

df_clean, log = nettoyer_modalites_dataframe(df)
print(f"  Transformations détectées : {len(log)}")
for entry in log:
    print(f"    • {entry}")


# =============================================================================
# TEST 3 — Pipeline complet avec dataset réel
# =============================================================================
print("\n" + "=" * 70)
print("  TEST 3 — Pipeline complet pretraiter_dataframe")
print("=" * 70)

artefacts = charger_tous_artefacts()

X_all, log = pretraiter_dataframe(df, artefacts.preprocessing_params)

print(f"\n  Shape résultat   : {X_all.shape}")
print(f"  Colonnes         : {list(X_all.columns)[:5]}, ... ({len(X_all.columns)} total)")
print(f"  Pas de NaN       : {not X_all.isna().any().any()}")
print(f"  Transformations  : {len(log)} appliquées")


# =============================================================================
# TEST 4 — Prédiction batch sur le dataset complet
# =============================================================================
print("\n" + "=" * 70)
print("  TEST 4 — predire_batch sur dataset complet (300 obs)")
print("=" * 70)

result = predire_batch(df, artefacts)

print(f"\n  Total          : {result['total']}")
print(f"  Churn prédit   : {result['nb_churn']} ({result['taux_churn_predit']:.2%})")
print(f"  Transformations: {len(result['transformations_appliquees'])}")
for t in result['transformations_appliquees']:
    print(f"    • {t}")


# =============================================================================
# TEST 5 — Analyse de portefeuille
# =============================================================================
print("\n" + "=" * 70)
print("  TEST 5 — analyser_portefeuille sur dataset complet")
print("=" * 70)

rapport = analyser_portefeuille(df, artefacts)

print(f"\n  Total              : {rapport['total']}")
print(f"  Churn prédit       : {rapport['nb_churn']}")
print(f"  Non-churn prédit   : {rapport['nb_non_churn']}")
print(f"  Score moyen        : {rapport['score_moyen']}%")
print(f"  Taux churn prédit  : {rapport['taux_churn_predit']}%")
print(f"  Recommandations    : {rapport['nb_recommandations']}")


print("\n" + "=" * 70)
print("  TOUS LES TESTS DE L'ETAPE 8.2 SONT TERMINES")
print("=" * 70)