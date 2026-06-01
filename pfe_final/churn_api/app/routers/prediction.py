import io

import logging
import pandas as pd 

logger = logging.getLogger("uvicorn.error")
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, status

from app.ml.dependencies import get_artifacts
from app.ml.loader import MLArtifacts
from app.ml.predictor import (
    predire_client,
    predire_batch,
    analyser_portefeuille,
)
from app.schemas import (
    ClientFeatures,
    PredictionResponse,
    PredictionBatchResponse,
    AnalyseRapportResponse,
)

router = APIRouter(
    prefix="/api",
    tags=["Prédiction"],
)

@router.post(
    "/predict",
    response_model=PredictionResponse,
    summary="Prédiction churn d'un client + explications SHAP",
    description=(
        "Reçoit les features brutes d'un client (28 colonnes), applique "
        "le pipeline complet (encodage + imputation + prédiction RF + SHAP) "
        "et retourne la probabilité, la décision selon le seuil, le niveau "
        "de confiance et le top 5 des features explicatives. "
        "Utilisé par la fiche client React."
    ),
)
def predict_single(
    client: ClientFeatures,
    artefacts: MLArtifacts = Depends(get_artifacts),
) -> PredictionResponse:
    """
    Endpoint de prédiction individuelle.

    Workflow :
      1. Pydantic valide automatiquement les features brutes (Enums, bornes)
      2. predire_client orchestre preprocessing → predict → SHAP
      3. La réponse est construite en PredictionResponse (validation sortie)

    Exceptions traitées :
      - 422 (UNPROCESSABLE_ENTITY) : géré automatiquement par Pydantic si
        une feature a un mauvais type ou modalité inconnue
      - 500 (INTERNAL_SERVER_ERROR) : bug interne (le pipeline a planté)
    """
    try:
        result = predire_client(client, artefacts)
        return PredictionResponse(**result)
    except Exception as e:
        # Catch-all pour ne PAS exposer la stack trace au frontend
        # (sécurité : éviter de leaker des détails d'implémentation)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur de prédiction : {str(e)}",
        )


@router.post(
    "/predict/batch",
    response_model=PredictionBatchResponse,
    summary="Prédiction churn sur un fichier CSV complet",
    description=(
        "Reçoit un CSV contenant plusieurs clients, applique le pipeline "
        "de prédiction sur chaque ligne en mode vectoriel (rapide), et "
        "retourne le détail ligne par ligne. Le CSV doit avoir les mêmes "
        "colonnes que le dataset original (sans la colonne 'churn')."
    ),
)
async def predict_batch_csv(
    file: UploadFile = File(..., description="CSV des clients à scorer"),
    artefacts: MLArtifacts = Depends(get_artifacts),
) -> PredictionBatchResponse:
    """
    Endpoint de prédiction batch.

    Workflow :
      1. Validation du type de fichier (.csv obligatoire)
      2. Lecture du CSV en mémoire
      3. Vérification minimale (nombre de colonnes raisonnable)
      4. Suppression de la colonne 'churn' si présente (sécurité)
      5. predire_batch fait le travail vectoriel
      6. Retour ligne par ligne

    Exceptions :
      - 400 : fichier non-CSV ou structure invalide
      - 500 : erreur de traitement interne
    """
    # ── 1. Validation du type de fichier ────────────────────────────────────
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Le fichier doit être au format CSV (extension .csv).",
        )

    try:
        # ── 2. Lecture du CSV ───────────────────────────────────────────────
        contents = await file.read()
        df_raw = pd.read_csv(io.StringIO(contents.decode("utf-8")))

        # ── 3. Vérification basique ─────────────────────────────────────────
        if df_raw.empty:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Le CSV est vide.",
            )

        if df_raw.shape[1] < 10:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"CSV invalide : seulement {df_raw.shape[1]} colonnes "
                    "détectées. Au moins 10 colonnes du dataset original sont "
                    "attendues."
                ),
            )

        # ── 4. Sécurité : supprimer la colonne cible si elle traîne ─────────
        if "churn" in df_raw.columns:
            df_raw = df_raw.drop(columns=["churn"])

        # ── 5. Prédiction batch (delegation au predictor) ───────────────────
        result = predire_batch(df_raw, artefacts)
        return PredictionBatchResponse(**result)

    except HTTPException:
        # On propage les HTTPException qu'on a soulevées nous-mêmes
        raise
    except Exception as e:
        # Catch-all pour les erreurs inattendues (ex : encoding du CSV)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur de traitement du fichier CSV : {str(e)}",
        )


@router.post(
    "/analyse",
    response_model=AnalyseRapportResponse,
    summary="Analyse churn du portefeuille — segmentation par risque",
    description=(
        "Reçoit un CSV, prédit le churn sur tous les clients et retourne "
        "une synthèse binaire CHURN / NON-CHURN. "
        "Compatible avec le format attendu par le frontend Django sur "
        "/ml/lancer-analyse/."
    ),
)
async def lancer_analyse_portefeuille(
    file: UploadFile = File(..., description="CSV du portefeuille à analyser"),
    artefacts: MLArtifacts = Depends(get_artifacts),
) -> AnalyseRapportResponse:
    """
    Endpoint d'analyse de portefeuille.

    Différence avec /api/predict/batch :
      - /predict/batch retourne le DÉTAIL ligne par ligne
      - /analyse       retourne une SYNTHÈSE agrégée par niveau de risque

    Segmentation binaire (cf. config.py) :
      - nb_churn      : proba >= 0.32
      - nb_non_churn  : proba < 0.32

    Exceptions :
      - 400 : fichier invalide
      - 500 : erreur de traitement
    """
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Format CSV requis.",
        )

    try:
        contents = await file.read()
        df_raw = pd.read_csv(io.StringIO(contents.decode("utf-8")))

        if df_raw.empty:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Le CSV est vide.",
            )

        if "churn" in df_raw.columns:
            df_raw = df_raw.drop(columns=["churn"])

        result = analyser_portefeuille(df_raw, artefacts)
        return AnalyseRapportResponse(**result)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur d'analyse : {str(e)}",
        )
