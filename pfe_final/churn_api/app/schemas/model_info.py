# =============================================================================
# app/schemas/model_info.py — Schémas pour les endpoints système et modèle
# PFE — Prédiction du Churn — Tunisie Télécom Agence Kairouan
# =============================================================================

from pydantic import BaseModel, Field
from typing   import List, Literal


# =============================================================================
# RÉPONSE — Health check (GET /health)
# =============================================================================

class HealthResponse(BaseModel):
    """
    Réponse du health check. Utilisée par React pour vérifier au démarrage
    que le backend FastAPI est accessible et que le modèle est bien chargé.

    Si cet endpoint répond avec status='ok', tous les artefacts sont chargés
    en mémoire et l'API est prête à servir des prédictions.
    """
    status  : Literal["ok", "degraded", "error"] = Field(
        ..., description="État global de l'API"
    )
    modele  : str = Field(..., description="Nom du fichier modèle chargé")
    version : str = Field(..., description="Version de l'API")
    seuil   : float = Field(..., ge=0, le=1, description="Seuil de décision actif")


# =============================================================================
# RÉPONSE — Informations du modèle (GET /api/model/info)
# =============================================================================

class ModelInfoResponse(BaseModel):
    """
    Métriques de performance du modèle final retenu (RF Optuna Fβ=2).

    Métriques mesurées sur le test set (90 obs, 25 churners) après
    optimisation par Optuna 100 essais et validation croisée 5-folds
    (cf. cellules B.3, B.4 et B15 du notebook).

    Utilisée par le dashboard React pour afficher les KPIs du modèle
    et permettre au comité métier de juger la qualité du système.
    """
    modele        : str   = Field(..., description="Nom complet du modèle")
    version       : str   = Field(..., description="Version du modèle")
    auc_roc       : float = Field(..., ge=0, le=1, description="AUC-ROC sur test set")
    f1_score      : float = Field(..., ge=0, le=1, description="F1-score sur test set")
    recall        : float = Field(..., ge=0, le=1, description="Recall (rappel) sur test set")
    precision     : float = Field(..., ge=0, le=1, description="Précision sur test set")
    seuil_optimal : float = Field(..., ge=0, le=1, description="Seuil de décision optimisé")
    n_features    : int   = Field(..., ge=0, description="Nombre de features finales (post-encodage)")
    feature_names : List[str] = Field(..., description="Liste ordonnée des features")


# =============================================================================
# RÉPONSE — Simulation entraînement (POST /api/train)
# =============================================================================

class TrainModeleInfo(BaseModel):
    """Métriques d'un modèle proposé par l'endpoint /api/train."""
    nom       : str   = Field(..., description="Nom complet du modèle")
    accuracy  : float = Field(..., ge=0, le=1)
    precision : float = Field(..., ge=0, le=1)
    recall    : float = Field(..., ge=0, le=1)
    auc       : float = Field(..., ge=0, le=1)


class TrainResponse(BaseModel):
    """
    Réponse de l'endpoint /api/train.

    NOTE IMPORTANTE pour le jury :
    Cet endpoint NE réentraîne PAS le modèle en ligne. Il retourne les
    métriques du modèle déjà entraîné offline via le notebook (Optuna
    100 essais + CV 5-folds). Le réentraînement en production via API
    serait une mauvaise pratique :
      - Temps de calcul incompatible avec une réponse HTTP synchrone
      - Risque d'écraser le modèle validé par un modèle non testé
      - Impossibilité de reproduire les conditions du benchmark notebook

    L'endpoint sert juste de façade compatible avec l'ancien front Django
    /ml/train-models/ qui s'attend à recevoir des métriques.
    """
    success : bool                  = Field(..., description="Toujours True si l'endpoint répond")
    models  : List[TrainModeleInfo] = Field(..., description="Métriques du/des modèle(s) demandé(s)")