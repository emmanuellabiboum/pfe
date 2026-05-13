# =============================================================================
# tests_manuels/test_predictor.py
# Tests manuels du predictor — à lancer après l'Étape 4
# =============================================================================
#
# Usage : depuis la racine du projet (C:\pfe_final\churn_api\),
#   python tests_manuels/test_predictor.py
#
# Ce script remplace les commandes "python -c ..." multi-lignes qui
# posent problème avec PowerShell (échappement des guillemets).

import sys
from pathlib import Path

# Ajoute la racine du projet au chemin Python
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd

from app.ml.loader    import charger_tous_artefacts
from app.ml.predictor import (
    predire_client,
    analyser_portefeuille,
    expliquer_client_test_set,
)
from app.schemas      import ClientFeatures


def afficher_separateur(titre: str) -> None:
    print("\n" + "=" * 70)
    print(f"  {titre}")
    print("=" * 70)


# ── Chargement des artefacts (une seule fois) ────────────────────────────────
artefacts = charger_tous_artefacts()


# =============================================================================
# TEST 1 — Profil FIDELE (attendu : NON-CHURN)
# =============================================================================
afficher_separateur("TEST 1 — PROFIL FIDELE (attendu : NON-CHURN)")

client_fidele = ClientFeatures(
    genre_client             = "Femme",
    type_abonnement          = "Offre a Facture",
    plan_tarifaire           = "Forfait Illimite",
    moyen_paiement           = "prelevement_bancaire",
    zone_reseau_principale   = "URBAIN",
    qualite_signal_dominante = "Excellent",
    tenure_mois              = 72,
    duree_appel_moyenne_sec  = 300.0,
    data_moyenne_gb          = 15.0,
    nb_evenements_total      = 1200,
    nb_sessions              = 350,
    duree_session_moyenne_sec= 400.0,
    taux_cookies             = 0.3,
    recence_session_jours    = 1,
    ratio_sms_appels         = 0.2,
    score_qualite_zone       = 0.9,
    flag_offre_data          = 1,
    flag_offre_voix          = 1,
    consentement_marketing   = True,
    optout_marketing         = False,
    facture_moyenne_mensuelle= 45.0,
    satisfaction_client      = 5.0,
)

result = predire_client(client_fidele, artefacts)

print(f"  Probabilite churn : {result['probabilite_churn']:.4f}")
print(f"  Decision          : {result['decision']}")
print(f"  Confiance         : {result['confiance']}")
print(f"  Modele            : {result['modele']}")
print(f"  Base value SHAP   : {result['valeur_base_shap']:.4f}")
print()
print("  Top 5 features :")
for f in result["features_explicatives"]:
    print(f"    - {f['feature']:<30} SHAP={f['shap_value']:+.4f} ({f['direction']})")
    print(f"      -> {f['interpretation']}")


# =============================================================================
# TEST 2 — Profil A RISQUE (attendu : CHURN)
# =============================================================================
afficher_separateur("TEST 2 — PROFIL A RISQUE (attendu : CHURN)")

client_risque = ClientFeatures(
    genre_client             = "Homme",
    type_abonnement          = "Offre Prepayee",
    plan_tarifaire           = "Offre Classique",
    moyen_paiement           = "especes",
    zone_reseau_principale   = "RURAL",
    qualite_signal_dominante = "Faible",
    tenure_mois              = 2,
    duree_appel_moyenne_sec  = 30.0,
    data_moyenne_gb          = 0.5,
    nb_evenements_total      = 20,
    nb_sessions              = 5,
    duree_session_moyenne_sec= 30.0,
    taux_cookies             = 0.95,
    recence_session_jours    = 45,
    ratio_sms_appels         = 2.5,
    score_qualite_zone       = 0.2,
    flag_offre_data          = 0,
    flag_offre_voix          = 1,
    consentement_marketing   = False,
    optout_marketing         = True,
    satisfaction_client      = 1.0,
    score_frustration        = 8.0,
)

result = predire_client(client_risque, artefacts)

print(f"  Probabilite churn : {result['probabilite_churn']:.4f}")
print(f"  Decision          : {result['decision']}")
print(f"  Confiance         : {result['confiance']}")
print()
print("  Top 5 features :")
for f in result["features_explicatives"]:
    print(f"    - {f['feature']:<30} SHAP={f['shap_value']:+.4f} ({f['direction']})")
    print(f"      -> {f['interpretation']}")


# =============================================================================
# TEST 3 — Vérification cohérence avec la matrice SHAP
# =============================================================================
afficher_separateur("TEST 3 — COHERENCE MATRICE SHAP")

shap_matrix = pd.read_csv("fastapi_artifacts/shap_matrix_v1.csv", index_col=0)

print(f"  Portefeuille de test : {len(shap_matrix)} clients SHAP")
print(f"  Nombre de features   : {len(shap_matrix.columns)}")
print(f"  Coherence avec modele: ", end="")
if list(shap_matrix.columns) == artefacts.feature_names:
    print("OK (memes colonnes dans le meme ordre)")
else:
    print("INCOHERENCE - voir le diff plus bas")

print(f"  analyser_portefeuille importable : {callable(analyser_portefeuille)}")


# =============================================================================
# TEST 4 — SHAP d'un client du test set
# =============================================================================
afficher_separateur("TEST 4 — SHAP CLIENT #0 DU TEST SET")

explication = expliquer_client_test_set(
    client_id   = 0,
    shap_matrix = shap_matrix,
    artefacts   = artefacts,
    top_n       = 5,
)

print(f"  Client ID         : {explication['client_id']}")
print(f"  Probabilite       : {explication['probabilite_churn']:.4f}")
print(f"  Decision          : {explication['decision']}")
print(f"  Base value        : {explication['valeur_base']:.4f}")
print()
print("  Top 5 features (waterfall) :")
for f in explication["features"]:
    print(f"    - {f['nom']:<35} SHAP={f['shap']:+.4f} ({f['direction']})")


# =============================================================================
# RECAPITULATIF
# =============================================================================
print("\n" + "=" * 70)
print("  TOUS LES TESTS DE L'ETAPE 4 ONT ETE EXECUTES")
print("=" * 70)