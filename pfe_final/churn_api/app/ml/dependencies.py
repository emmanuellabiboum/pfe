# =============================================================================
# app/ml/dependencies.py — Injection de dépendances FastAPI
# PFE — Prédiction du Churn — Tunisie Télécom Agence Kairouan
# =============================================================================
#
# JUSTIFICATION ARCHITECTURALE :
# FastAPI permet d'injecter des dépendances dans les endpoints via Depends().
# On utilise ce mécanisme pour partager les artefacts ML chargés au boot
# avec tous les routers, sans utiliser de variable globale "sale".
#
# Pattern : Singleton + Lazy Loading
#   - Au démarrage, le lifespan de main.py appelle initialiser_artefacts()
#   - Chaque endpoint déclare `artefacts = Depends(get_artifacts)`
#   - FastAPI injecte automatiquement le singleton à chaque appel
#
# Avantages :
#   1. Performance : les artefacts sont chargés UNE SEULE FOIS
#   2. Testabilité : on peut override get_artifacts() dans les tests
#   3. Clarté : chaque endpoint déclare explicitement ce dont il a besoin

from typing import Optional

import pandas as pd

from app.ml.loader import MLArtifacts, charger_tous_artefacts
from app.config    import SHAP_MATRIX_PATH


# =============================================================================
# SINGLETONS — initialisés au démarrage par le lifespan
# =============================================================================
# Variables module-level qui stockent les artefacts une fois chargés.
# Le `Optional` est important : avant le démarrage, ces variables sont None.

_artefacts: Optional[MLArtifacts]   = None
_shap_matrix: Optional[pd.DataFrame] = None


# =============================================================================
# INITIALISATION — appelée par le lifespan de FastAPI au boot
# =============================================================================

def initialiser_artefacts() -> MLArtifacts:
    """
    Charge tous les artefacts ML en mémoire et les stocke dans le singleton.
    Cette fonction est appelée UNE SEULE FOIS au démarrage de FastAPI
    (cf. main.py → lifespan).

    Returns:
        Les artefacts chargés (utiles pour le lifespan qui logge le boot).

    Raises:
        FileNotFoundError : si un artefact attendu manque (cf. config.py)
    """
    global _artefacts
    _artefacts = charger_tous_artefacts()
    return _artefacts


def initialiser_shap_matrix() -> pd.DataFrame:
    """
    Charge la matrice SHAP du test set en mémoire.
    Utilisée par les endpoints /api/shap/{client_id} et /api/clients
    qui exposent les explications pré-calculées par la cellule C8.

    Returns:
        DataFrame de shape (90, 31) avec les SHAP values du test set.

    Raises:
        FileNotFoundError : si shap_matrix_v1.csv est absent.
    """
    global _shap_matrix
    if not SHAP_MATRIX_PATH.exists():
        raise FileNotFoundError(
            f"shap_matrix_v1.csv introuvable dans {SHAP_MATRIX_PATH}.\n"
            "→ Re-exécute la cellule C8 du notebook pour le générer."
        )
    _shap_matrix = pd.read_csv(SHAP_MATRIX_PATH, index_col=0)
    print(f"  ✓ Matrice SHAP chargée : {len(_shap_matrix)} clients × "
          f"{len(_shap_matrix.columns)} features")
    return _shap_matrix


# =============================================================================
# DÉPENDANCES INJECTABLES — utilisées par les endpoints via Depends()
# =============================================================================

def get_artifacts() -> MLArtifacts:
    """
    Dépendance FastAPI : retourne les artefacts ML chargés.

    Usage dans un endpoint :
        @router.post("/predict")
        def predict(
            client: ClientFeatures,
            artefacts: MLArtifacts = Depends(get_artifacts)
        ):
            ...

    Raises:
        RuntimeError : si appelée avant que le lifespan ait initialisé
                       les artefacts (situation anormale).
    """
    if _artefacts is None:
        raise RuntimeError(
            "Les artefacts ML ne sont pas chargés. "
            "Vérifie que le lifespan de main.py a bien été exécuté."
        )
    return _artefacts


def get_shap_matrix() -> pd.DataFrame:
    """
    Dépendance FastAPI : retourne la matrice SHAP du test set.

    Utilisée par les endpoints /api/shap/{client_id} et /api/clients.

    Raises:
        RuntimeError : si appelée avant initialisation.
    """
    if _shap_matrix is None:
        raise RuntimeError(
            "La matrice SHAP n'est pas chargée. "
            "Vérifie que le lifespan de main.py a bien été exécuté."
        )
    return _shap_matrix