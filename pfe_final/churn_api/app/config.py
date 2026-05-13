# =============================================================================
# app/config.py — Configuration centrale de l'API
# PFE — Prédiction du Churn — Tunisie Télécom Agence Kairouan
# =============================================================================
#
# JUSTIFICATION ARCHITECTURALE :
# Centraliser la configuration dans UN SEUL fichier garantit que :
#   1. Les chemins relatifs ne se baladent pas dans tout le code
#   2. Changer le port ou la version se fait à un seul endroit
#   3. Les déploiements (local / cloud) lisent les mêmes constantes
#   4. Le jury voit immédiatement où sont les paramètres clés
#
# Aucune logique métier ici, uniquement des constantes et des chemins.

from pathlib import Path
import os


# =============================================================================
# CHEMINS DU PROJET
# =============================================================================
# BASE_DIR remonte de app/config.py vers la racine churn_api/
# Path(__file__) → .../app/config.py
# .resolve()     → chemin absolu (résout les liens symboliques)
# .parent.parent → remonte de 2 niveaux : app/config.py → app → churn_api

BASE_DIR       = Path(__file__).resolve().parent.parent
ARTIFACTS_DIR  = BASE_DIR / "fastapi_artifacts"


# =============================================================================
# CHEMINS DES ARTEFACTS DU MODÈLE
# =============================================================================
# Tous générés par le notebook modelisation.ipynb :
#   • A-EXPORT  : preprocessing_params.json
#   • B16       : churn_model_v1.pkl, churn_threshold_v1.pkl,
#                 feature_names_v1.json, churn_metadata_v1.json
#   • C8        : shap_explainer_v1.pkl, shap_matrix_v1.csv,
#                 shap_importance_v1.csv, shap_meta_v1.json

# Modèle et seuil (B16)
MODEL_PATH         = ARTIFACTS_DIR / "churn_model_v1.pkl"
THRESHOLD_PATH     = ARTIFACTS_DIR / "churn_threshold_v1.pkl"
METADATA_PATH      = ARTIFACTS_DIR / "churn_metadata_v1.json"
FEATURE_NAMES_PATH = ARTIFACTS_DIR / "feature_names_v1.json"

# Preprocessing (A-EXPORT — à copier manuellement depuis le Bureau)
PREPROCESSING_PATH = ARTIFACTS_DIR / "preprocessing_params.json"

# SHAP (C8)
SHAP_EXPLAINER_PATH  = ARTIFACTS_DIR / "shap_explainer_v1.pkl"
SHAP_MATRIX_PATH     = ARTIFACTS_DIR / "shap_matrix_v1.csv"
SHAP_IMPORTANCE_PATH = ARTIFACTS_DIR / "shap_importance_v1.csv"
SHAP_META_PATH       = ARTIFACTS_DIR / "shap_meta_v1.json"


# =============================================================================
# MÉTADONNÉES DE L'API
# =============================================================================

API_TITLE = "Churn Prediction API — Tunisie Télécom Kairouan"
API_DESCRIPTION = (
    "API de prédiction du churn client basée sur un Random Forest optimisé "
    "avec Optuna (scoring Fβ=2, 100 essais). "
    "Explications SHAP exactes au niveau individuel via TreeExplainer. "
    "Modèle final retenu après validation croisée 5-folds et comparaison "
    "avec 5 stratégies d'ensemble (cf. cellule B15 du notebook)."
)
API_VERSION = "1.0.0"
MODEL_VERSION = "v1"


# =============================================================================
# CORS — Origines autorisées
# =============================================================================
# JUSTIFICATION : React (front) tourne sur localhost:3000, FastAPI sur 8000.
# Sans CORS, le navigateur bloque les requêtes cross-origin.
# Pour le déploiement cloud (Render, Railway), on ajoutera l'URL de prod.

CORS_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:8000",   # Pour tester depuis Swagger UI directement
    "http://127.0.0.1:8000",
    # ajouter ici l'URL de prod du frontend après déploiement cloud :
    # "https://churn-frontend-kairouan.onrender.com",
]


# =============================================================================
# SEUIL MÉTIER (segmentation binaire)
# =============================================================================
# Utilisé par /api/analyse et /api/clients pour identifier les clients à risque.
#
# RAPPEL : ce seuil de SEGMENTATION est aligné sur le seuil de DÉCISION
# binaire churn / non-churn (valeur 0.32).

SEUIL_CHURN = 0.32   # proba >= 0.32 → Churn prédit (action requise)
# < 0.32 → Faible risque → suivi standard


# =============================================================================
# CONFIGURATION DE PAGINATION
# =============================================================================

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE     = 100


# =============================================================================
# VALIDATION DE L'ENVIRONNEMENT (au boot)
# =============================================================================
# Cette fonction est appelée par le lifespan de FastAPI au démarrage.
# Elle plante TÔT si un artefact manque, plutôt que d'avoir une 500 mystérieuse
# au premier appel /predict.

def verifier_artefacts() -> dict:
    """
    Vérifie que tous les artefacts attendus sont présents et lisibles.
    Retourne un dictionnaire avec le détail des fichiers trouvés/manquants.
    Lève FileNotFoundError si un artefact critique manque.
    """
    artefacts_critiques = {
        "Modèle"           : MODEL_PATH,
        "Seuil"            : THRESHOLD_PATH,
        "Métadonnées"      : METADATA_PATH,
        "Features"         : FEATURE_NAMES_PATH,
        "Preprocessing"    : PREPROCESSING_PATH,
        "SHAP Explainer"   : SHAP_EXPLAINER_PATH,
    }

    artefacts_optionnels = {
        "SHAP Matrix"      : SHAP_MATRIX_PATH,
        "SHAP Importance"  : SHAP_IMPORTANCE_PATH,
        "SHAP Meta"        : SHAP_META_PATH,
    }

    rapport = {"trouvés": [], "manquants": [], "optionnels_absents": []}

    for label, chemin in artefacts_critiques.items():
        if chemin.exists():
            taille_kb = chemin.stat().st_size / 1024
            rapport["trouvés"].append(f"  ✓ {label:<18} {chemin.name:<30} ({taille_kb:>8.1f} Ko)")
        else:
            rapport["manquants"].append(f"  ✗ {label:<18} {chemin.name} — INTROUVABLE")

    for label, chemin in artefacts_optionnels.items():
        if chemin.exists():
            taille_kb = chemin.stat().st_size / 1024
            rapport["trouvés"].append(f"  ✓ {label:<18} {chemin.name:<30} ({taille_kb:>8.1f} Ko)")
        else:
            rapport["optionnels_absents"].append(f"  ⚠ {label:<18} {chemin.name} — absent (endpoints SHAP/clients dégradés)")

    if rapport["manquants"]:
        message = (
            f"\n\n❌ Artefacts critiques manquants dans {ARTIFACTS_DIR} :\n"
            + "\n".join(rapport["manquants"])
            + "\n\n→ Vérifie que tu as bien copié tous les fichiers du Bureau"
            + "\n   vers le dossier fastapi_artifacts/ du projet."
            + "\n→ Référence : cellules A-EXPORT, B16 et C8 du notebook.\n"
        )
        raise FileNotFoundError(message)

    return rapport