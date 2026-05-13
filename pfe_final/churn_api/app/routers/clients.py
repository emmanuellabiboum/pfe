# =============================================================================
# app/routers/clients.py — Liste paginée des clients avec scores churn
# PFE — Prédiction du Churn — Tunisie Télécom Agence Kairouan
# =============================================================================
#
# Ce routeur expose /api/clients qui retourne la liste paginée des clients
# du test set avec leur probabilité de churn et niveau de risque.
#
# Utilisé par le dashboard React (table de clients à actionner) et par le
# frontend Django pour enrichir /clients/ avec les scores ML.
#
# JUSTIFICATION DU CALCUL DES PROBAS :
# On utilise la propriété d'additivité de SHAP : pour un TreeExplainer,
# proba_predite = base_value + sum(shap_values_features).
# Cette propriété est exacte (à 1e-6 près) pour les modèles arborescents.
# On évite ainsi de stocker un CSV supplémentaire de probabilités.

from typing import List, Optional, Literal

import numpy  as np
import pandas as pd
from fastapi import APIRouter, Depends, Query

from app.ml.dependencies import get_artifacts, get_shap_matrix
from app.ml.loader       import MLArtifacts
from app.schemas         import ClientListResponse, ClientListItem
from app.config          import (
    SEUIL_CHURN,
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_SIZE,
)


router = APIRouter(
    prefix = "/api",
    tags   = ["Clients"],
)


# =============================================================================
# UTILITAIRE INTERNE — calcul des probabilités via additivité SHAP
# =============================================================================

def _calculer_probas_depuis_shap(
    shap_matrix: pd.DataFrame,
    base_value : float,
) -> np.ndarray:
    """
    Reconstitue les probabilités de churn pour chaque client du test set
    via la propriété d'additivité de SHAP.

    Formule (exacte pour TreeExplainer sur RandomForest) :
        proba_client = base_value + sum(shap_values_client)

    Args:
        shap_matrix : DataFrame de shape (n_clients, n_features)
        base_value  : probabilité moyenne du train set (cf. shap_meta_v1.json)

    Returns:
        Vecteur 1D de probabilités, borné dans [0, 1] par sécurité numérique.
    """
    sommes_shap = shap_matrix.sum(axis=1).values
    probas = base_value + sommes_shap

    # Borne par sécurité (les arrondis numériques peuvent légèrement
    # déborder de [0, 1] sur certains modèles, typiquement ±1e-6)
    return np.clip(probas, 0.0, 1.0)





# =============================================================================
# GET /api/clients — Liste paginée avec filtre par risque
# =============================================================================

@router.get(
    "/clients",
    response_model = ClientListResponse,
    summary        = "Liste des clients avec score churn",
    description    = (
        "Retourne la liste paginée des clients du test set avec leur "
        "probabilité de churn et décision binaire (CHURN / NON-CHURN)."
    ),
)
def get_clients(
    page       : int = Query(
        default     = 1,
        ge          = 1,
        description = "Page courante (1-indexed)",
    ),
    limit      : int = Query(
        default     = DEFAULT_PAGE_SIZE,
        ge          = 1,
        le          = MAX_PAGE_SIZE,
        description = f"Nombre d'items par page (max {MAX_PAGE_SIZE})",
    ),
    artefacts  : MLArtifacts  = Depends(get_artifacts),
    shap_matrix: pd.DataFrame = Depends(get_shap_matrix),
) -> ClientListResponse:
    """
    Endpoint de listing paginé des clients du test set.

    Workflow :
      1. Récupère la base_value SHAP depuis les métadonnées
      2. Reconstitue les probabilités via additivité SHAP
      3. Construit la liste complète avec décision et risque
      4. Filtre par niveau de risque si demandé
      5. Applique la pagination
      6. Retourne la réponse

    Performance :
      Toutes les opérations sont vectorielles (numpy/pandas), donc rapide
      même si shap_matrix grandissait à plusieurs milliers de clients.

    Exemple d'appel :
        GET /api/clients?risque=eleve&page=1&limit=20
        → retourne les 20 premiers clients à risque élevé
    """
    # ── 1. Récupération de la base_value SHAP ──────────────────────────────
    # base_value = probabilité moyenne de churn sur le train set (≈ 0.49)
    base_value = float(
        artefacts.shap_meta.get("base_value", {}).get("valeur", 0.5)
    )

    # ── 2. Reconstitution vectorielle des probabilités ─────────────────────
    probas = _calculer_probas_depuis_shap(shap_matrix, base_value)

    # ── 3. Construction de la liste complète ───────────────────────────────
    seuil = artefacts.seuil
    clients_complets: List[ClientListItem] = [
        ClientListItem(
            id                = int(idx),
            probabilite_churn = round(float(proba), 4),
            decision          = "CHURN" if proba >= seuil else "NON-CHURN",
        )
        for idx, proba in enumerate(probas)
    ]

    # ── 5. Pagination ──────────────────────────────────────────────────────
    total  = len(clients_complets)
    debut  = (page - 1) * limit
    fin    = debut + limit
    pages  = (total + limit - 1) // limit if total > 0 else 0

    clients_page = clients_complets[debut:fin]

    # ── 6. Construction de la réponse ──────────────────────────────────────
    return ClientListResponse(
        total   = total,
        page    = page,
        limit   = limit,
        pages   = pages,
        clients = clients_page,
    )