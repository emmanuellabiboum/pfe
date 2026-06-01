from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent
ARTIFACTS_DIR = BASE_DIR / "fastapi_artifacts"

MODEL_PATH = ARTIFACTS_DIR / "churn_model_v1.pkl"
THRESHOLD_PATH = ARTIFACTS_DIR / "churn_threshold_v1.pkl"
METADATA_PATH = ARTIFACTS_DIR / "churn_metadata_v1.json"
FEATURE_NAMES_PATH = ARTIFACTS_DIR / "feature_names_v1.json"
PREPROCESSING_PATH = ARTIFACTS_DIR / "preprocessing_params.json"
SHAP_EXPLAINER_PATH = ARTIFACTS_DIR / "shap_explainer_v1.pkl"
SHAP_MATRIX_PATH = ARTIFACTS_DIR / "shap_matrix_v1.csv"
SHAP_IMPORTANCE_PATH = ARTIFACTS_DIR / "shap_importance_v1.csv"
SHAP_META_PATH = ARTIFACTS_DIR / "shap_meta_v1.json"

API_TITLE = "Churn Prediction API — Tunisie Télécom Kairouan"
API_DESCRIPTION = "API de prédiction du churn client basée sur Random Forest avec SHAP"
API_VERSION = "1.0.0"
MODEL_VERSION = "v1"

CORS_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]

SEUIL_CHURN = 0.32

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100

def verifier_artefacts() -> dict:
    artefacts_critiques = {
        "Modèle": MODEL_PATH,
        "Seuil": THRESHOLD_PATH,
        "Métadonnées": METADATA_PATH,
        "Features": FEATURE_NAMES_PATH,
        "Preprocessing": PREPROCESSING_PATH,
        "SHAP Explainer": SHAP_EXPLAINER_PATH,
    }

    artefacts_optionnels = {
        "SHAP Matrix": SHAP_MATRIX_PATH,
        "SHAP Importance": SHAP_IMPORTANCE_PATH,
        "SHAP Meta": SHAP_META_PATH,
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
            rapport["optionnels_absents"].append(f"  ⚠ {label:<18} {chemin.name} — absent")

    if rapport["manquants"]:
        message = (
            f"\n\n❌ Artefacts critiques manquants dans {ARTIFACTS_DIR} :\n"
            + "\n".join(rapport["manquants"])
            + "\n\n→ Vérifie que tu as bien copié tous les fichiers du Bureau"
            + "\n   vers le dossier fastapi_artifacts/ du projet.\n"
        )
        raise FileNotFoundError(message)

    return rapport