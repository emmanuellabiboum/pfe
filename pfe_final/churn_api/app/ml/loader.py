# =============================================================================
# app/ml/loader.py — Chargement des artefacts ML au démarrage de FastAPI
# PFE — Prédiction du Churn — Tunisie Télécom Agence Kairouan
# =============================================================================
#
# JUSTIFICATION ARCHITECTURALE :
# Charger les artefacts UNE SEULE FOIS au boot (via le lifespan FastAPI)
# plutôt qu'à chaque requête. Avantages :
#   1. Latence /predict réduite : ~50ms au lieu de ~500ms
#   2. Détection précoce des erreurs (modèle absent, pickle corrompu)
#      → on plante au démarrage, pas en plein milieu d'une requête
#   3. Mémoire stable : 1 instance partagée entre tous les workers
#
# Particularités Windows / Python 3.13 :
#   On utilise `builtins.open` + `pickle` natif au lieu de `joblib.load`
#   à cause d'un bug "Errno 9 Bad file descriptor" rencontré dans le
#   notebook (cf. cellule B16). Joblib utilise des fonctions OS spécifiques
#   qui plantent sur Windows + Python 3.13. Pickle natif via builtins
#   contourne ce problème.

import builtins
import json
import pickle
from dataclasses import dataclass
from typing      import Any, Dict, List

from app.config import (
    MODEL_PATH,
    THRESHOLD_PATH,
    METADATA_PATH,
    FEATURE_NAMES_PATH,
    PREPROCESSING_PATH,
    SHAP_EXPLAINER_PATH,
    SHAP_META_PATH,
)


# =============================================================================
# CONTAINER DES ARTEFACTS — partagé par toute l'API
# =============================================================================
# Un dataclass plutôt qu'un dict pour bénéficier de l'autocomplétion IDE
# et de la vérification de types statique.

@dataclass
class MLArtifacts:
    """
    Conteneur des artefacts ML chargés en mémoire au démarrage de FastAPI.
    Une seule instance est créée par le lifespan dans main.py et partagée
    par tous les routers via la dépendance get_artifacts().
    """
    modele                : Any            # sklearn.RandomForestClassifier
    seuil                 : float          # 0.32 dans notre cas
    metadata              : Dict[str, Any] # contenu de churn_metadata_v1.json
    feature_names         : List[str]      # liste ordonnée des 31 colonnes
    preprocessing_params  : Dict[str, Any] # contenu de preprocessing_params.json
    explainer             : Any            # shap.TreeExplainer
    shap_meta             : Dict[str, Any] # contenu de shap_meta_v1.json


# =============================================================================
# FONCTIONS DE CHARGEMENT — une fonction par artefact
# =============================================================================
# Chaque fonction encapsule la lecture d'un fichier. Si une lecture échoue,
# le message d'erreur indique précisément quel fichier pose problème.

def _charger_pickle(chemin) -> Any:
    """Charge un fichier pickle avec builtins.open (workaround Windows)."""
    with builtins.open(chemin, "rb") as f:
        return pickle.load(f)


def _charger_json(chemin) -> Dict[str, Any]:
    """Charge un fichier JSON avec encodage UTF-8 explicite."""
    with builtins.open(chemin, "r", encoding="utf-8") as f:
        return json.load(f)


# =============================================================================
# CHARGEMENT GLOBAL — appelé par le lifespan de FastAPI
# =============================================================================

def charger_tous_artefacts() -> MLArtifacts:
    """
    Charge tous les artefacts ML en mémoire et retourne un MLArtifacts.

    Cette fonction est appelée UNE SEULE FOIS par le lifespan de main.py
    au démarrage de l'application.

    Levée d'exceptions :
      - FileNotFoundError : un artefact attendu est absent
      - ValueError        : un artefact est corrompu ou incohérent
      - pickle.UnpicklingError : version sklearn incompatible entre
                                 l'environnement du notebook et celui
                                 de l'API (très rare avec versions épinglées)
    """
    print("=" * 70)
    print("  CHARGEMENT DES ARTEFACTS ML")
    print("=" * 70)

    # ── 1. Modèle Random Forest (B16) ───────────────────────────────────────
    print("  [1/7] Chargement du modèle Random Forest...")
    modele = _charger_pickle(MODEL_PATH)
    nom_classe = modele.__class__.__name__
    print(f"        → {nom_classe}")
    if nom_classe != "RandomForestClassifier":
        # Pas une erreur fatale (l'API marche quand même), mais signal
        # qu'on s'est peut-être trompé de modèle.
        print(f"        ⚠ Attention : le modèle n'est pas un RandomForestClassifier")

    # ── 2. Seuil de décision (B16) ──────────────────────────────────────────
    print("  [2/7] Chargement du seuil de décision...")
    seuil = float(_charger_pickle(THRESHOLD_PATH))
    print(f"        → {seuil}")
    if not 0 < seuil < 1:
        raise ValueError(f"Seuil invalide : {seuil} (doit être dans ]0, 1[)")

    # ── 3. Métadonnées du modèle (B16) ──────────────────────────────────────
    print("  [3/7] Chargement des métadonnées...")
    metadata = _charger_json(METADATA_PATH)
    metriques = metadata.get("metriques_test", {})
    if metriques:
        print(f"        → AUC={metriques.get('AUC_ROC', 'n/a'):.4f}, "
              f"F1={metriques.get('F1', 'n/a'):.4f}, "
              f"Recall={metriques.get('Recall', 'n/a'):.4f}")

    # ── 4. Liste ordonnée des features (B16) ────────────────────────────────
    print("  [4/7] Chargement des noms de features...")
    feature_names_data = _charger_json(FEATURE_NAMES_PATH)
    feature_names = feature_names_data.get("features", [])
    n_features = len(feature_names)
    print(f"        → {n_features} features")

    if n_features == 0:
        raise ValueError("feature_names_v1.json ne contient aucune feature")

    # ── 5. Paramètres de preprocessing (A-EXPORT) ───────────────────────────
    print("  [5/7] Chargement des paramètres de preprocessing...")
    preprocessing_params = _charger_json(PREPROCESSING_PATH)

    # Validation cruciale : la liste des features dans preprocessing_params
    # DOIT correspondre à celle de feature_names_v1.json. Sinon le modèle
    # va recevoir des colonnes dans le mauvais ordre → prédictions fausses.
    feature_names_pp = preprocessing_params.get("feature_names_ordered", [])
    if feature_names_pp != feature_names:
        raise ValueError(
            "INCOHÉRENCE entre feature_names_v1.json et preprocessing_params.json.\n"
            "Les deux fichiers doivent contenir la MÊME liste de features dans le MÊME ordre.\n"
            f"  feature_names_v1.json   : {len(feature_names)} features\n"
            f"  preprocessing_params    : {len(feature_names_pp)} features\n"
            "→ Re-exécute les cellules A-EXPORT et B16 du notebook pour régénérer "
            "les artefacts de manière cohérente."
        )
    print(f"        → {len(preprocessing_params.get('ohe_columns', []))} colonnes OHE, "
          f"{len(preprocessing_params.get('imputation_stats', {}))} stats d'imputation")

    # ── 6. SHAP Explainer (C8) ──────────────────────────────────────────────
    print("  [6/7] Chargement de l'explainer SHAP...")
    explainer = _charger_pickle(SHAP_EXPLAINER_PATH)
    print(f"        → {explainer.__class__.__name__}")

    # ── 7. Métadonnées SHAP (C8) ────────────────────────────────────────────
    print("  [7/7] Chargement des métadonnées SHAP...")
    if SHAP_META_PATH.exists():
        shap_meta = _charger_json(SHAP_META_PATH)
        base_value = shap_meta.get("base_value", {}).get("valeur", "n/a")
        print(f"        → base_value SHAP = {base_value}")
    else:
        # Pas critique : on peut fonctionner sans, juste sans certaines stats
        print("        ⚠ shap_meta_v1.json absent (endpoints SHAP dégradés)")
        shap_meta = {}

    # ── Test de cohérence final : prédiction sur un vecteur de zéros ────────
    # Si le modèle plante dès le premier appel, autant le savoir tout de suite.
    print("\n  Test de cohérence : prédiction sur vecteur de zéros...")
    import pandas as pd
    X_test = pd.DataFrame([[0.0] * n_features], columns=feature_names)
    proba = float(modele.predict_proba(X_test)[0, 1])
    print(f"        → proba_churn = {proba:.4f} (test OK)")

    print("\n" + "=" * 70)
    print(f"  ✓ TOUS LES ARTEFACTS CHARGÉS — modèle prêt pour la prédiction")
    print("=" * 70 + "\n")

    return MLArtifacts(
        modele               = modele,
        seuil                = seuil,
        metadata             = metadata,
        feature_names        = feature_names,
        preprocessing_params = preprocessing_params,
        explainer            = explainer,
        shap_meta            = shap_meta,
    )