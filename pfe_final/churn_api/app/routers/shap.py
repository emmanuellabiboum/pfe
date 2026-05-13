# =============================================================================
# app/routers/shap.py — Endpoint d'explication SHAP par client du test set
# PFE — Prédiction du Churn — Tunisie Télécom Agence Kairouan
# =============================================================================
#
# Ce routeur expose l'endpoint /api/shap/{client_id} qui retourne les
# explications SHAP pré-calculées d'un client précis du test set, formatées
# pour un waterfall chart côté React.
#
# JUSTIFICATION ARCHITECTURALE :
# Les SHAP values du test set ont été calculées en cellule C8 du notebook
# et exportées dans shap_matrix_v1.csv. Cet endpoint les LIT (sans recalcul)
# pour permettre au dashboard React d'afficher les explications de
# n'importe quel client de référence, instantanément.
#
# Pour un NOUVEAU client (non présent dans le test set), il faut utiliser
# /api/predict qui recalcule les SHAP en live via le TreeExplainer.

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Path, status

from app.ml.dependencies import get_artifacts, get_shap_matrix
from app.ml.loader       import MLArtifacts
from app.ml.predictor    import expliquer_client_test_set
from app.schemas         import ShapWaterfallResponse


router = APIRouter(
    prefix = "/api",
    tags   = ["Prédiction"],
)


# =============================================================================
# GET /api/shap/{client_id} — Waterfall SHAP d'un client du test set
# =============================================================================

@router.get(
    "/shap/{client_id}",
    response_model = ShapWaterfallResponse,
    summary        = "Explication SHAP détaillée pour un client (waterfall chart)",
    description    = (
        "Retourne les SHAP values pré-calculées du client demandé sous "
        "forme de waterfall chart prêt à afficher dans React. "
        "Le client_id est l'index dans le test set (de 0 à 89). "
        "Pour expliquer un nouveau client, utiliser POST /api/predict."
    ),
)
def get_shap_explanation(
    client_id  : int            = Path(
        ...,
        ge          = 0,
        description = "Index du client dans le test set (0 à 89)",
    ),
    artefacts  : MLArtifacts    = Depends(get_artifacts),
    shap_matrix: pd.DataFrame   = Depends(get_shap_matrix),
) -> ShapWaterfallResponse:
    """
    Endpoint de récupération du waterfall SHAP pour un client du test set.

    Workflow :
      1. Vérification que client_id est dans les bornes valides
      2. Délégation à expliquer_client_test_set du predictor
      3. Construction de la réponse Pydantic

    Le top 10 features est retourné (vs top 5 pour /api/predict) parce
    que le waterfall chart de React affiche traditionnellement plus de
    barres pour la vue détaillée.

    Exceptions :
      - 404 : client_id hors bornes (n'existe pas dans le test set)
      - 500 : erreur interne (inattendue)
    """
    try:
        result = expliquer_client_test_set(
            client_id   = client_id,
            shap_matrix = shap_matrix,
            artefacts   = artefacts,
            top_n       = 10,
        )
        return ShapWaterfallResponse(**result)

    except IndexError as e:
        # client_id dépasse la taille de shap_matrix
        raise HTTPException(
            status_code = status.HTTP_404_NOT_FOUND,
            detail      = (
                f"Client #{client_id} non trouvé dans le test set "
                f"(valeurs valides : 0 à {len(shap_matrix) - 1}). "
                f"Détail : {str(e)}"
            ),
        )
    except Exception as e:
        raise HTTPException(
            status_code = status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail      = f"Erreur lors de l'extraction SHAP : {str(e)}",
        )