# =============================================================================
# app/schemas/__init__.py — Ré-export des schémas Pydantic
# =============================================================================
#
# JUSTIFICATION ARCHITECTURALE :
# Ce fichier permet d'écrire dans les routers et le predictor :
#     from app.schemas import ClientFeatures, PredictionResponse
# au lieu de :
#     from app.schemas.client import ClientFeatures
#     from app.schemas.prediction import PredictionResponse
# C'est plus lisible et c'est la convention Python pour les packages.

from app.schemas.client import (
    ClientFeatures,
    GenreClient,
    TypeAbonnement,
    PlanTarifaire,
    MoyenPaiement,
    ZoneReseau,
    QualiteSignal,
)

from app.schemas.prediction import (
    FeatureExplicative,
    PredictionResponse,
    PredictionBatchItem,
    PredictionBatchResponse,
    AnalyseRapportResponse,
    ShapWaterfallResponse,
    ShapFeatureWaterfall,
    ClientListItem,
    ClientListResponse,
)

from app.schemas.model_info import (
    ModelInfoResponse,
    HealthResponse,
    TrainResponse,
    TrainModeleInfo,
)

# __all__ contrôle ce qui est importé avec `from app.schemas import *`
__all__ = [
    # Client
    "ClientFeatures",
    "GenreClient", "TypeAbonnement", "PlanTarifaire",
    "MoyenPaiement", "ZoneReseau", "QualiteSignal",
    # Prédiction
    "FeatureExplicative",
    "PredictionResponse",
    "PredictionBatchItem", "PredictionBatchResponse",
    "AnalyseRapportResponse",
    "ShapWaterfallResponse", "ShapFeatureWaterfall",
    "ClientListItem", "ClientListResponse",
    # Modèle
    "ModelInfoResponse", "HealthResponse",
    "TrainResponse", "TrainModeleInfo",
]