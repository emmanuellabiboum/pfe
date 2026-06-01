from fastapi import APIRouter, Depends

from app.ml.dependencies import get_artifacts
from app.ml.loader       import MLArtifacts
from app.schemas         import HealthResponse
from app.config          import API_VERSION

router = APIRouter(
    tags = ["Système"],
)


@router.get(
    "/health",
    response_model = HealthResponse,
    summary        = "Vérification de l'état du serveur",
    description    = (
        "Retourne le statut du serveur et confirme que le modèle est chargé. "
        "Utilisé par React au démarrage pour vérifier la connexion au backend."
    ),
)
def health_check(
    artefacts: MLArtifacts = Depends(get_artifacts),
) -> HealthResponse:
    """
    Endpoint de santé.

    - status='ok'       : tout fonctionne, l'API peut servir des prédictions
    - status='degraded' : l'API répond mais certaines fonctionnalités sont KO
                         (ex : SHAP matrix absente)
    - status='error'    : situation critique (ne devrait jamais sortir
                         du lifespan car l'API ne démarrerait pas)
    """
    return HealthResponse(
        status  = "ok",
        modele  = "churn_model_v1.pkl",
        version = API_VERSION,
        seuil   = artefacts.seuil,
    )