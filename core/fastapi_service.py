# =============================================================================
# fastapi_service.py — Service d'intégration avec l'API FastAPI
# =============================================================================

import os
import httpx
import pandas as pd
import io
import logging
import traceback
from typing import Dict, Optional, List

logger = logging.getLogger(__name__)

FASTAPI_BASE_URL = os.getenv("FASTAPI_BASE_URL", "http://localhost:8000")
FASTAPI_ENDPOINTS = {
    "health": "/health",
    "model_info": "/api/model/info",
    "predict": "/api/predict",
    "predict_batch": "/api/predict/batch",
    "analyse": "/api/analyse",
}


def check_fastapi_health() -> bool:
    """Vérifie que l'API FastAPI est accessible."""
    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(f"{FASTAPI_BASE_URL}/health")
            return response.status_code == 200
    except Exception as e:
        logger.warning(f"FastAPI health check failed: {type(e).__name__} - {str(e)}")
        return False


def get_model_info() -> Optional[Dict]:
    """Récupère les informations du modèle depuis l'API FastAPI."""
    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.get(
                f"{FASTAPI_BASE_URL}{FASTAPI_ENDPOINTS['model_info']}"
            )
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Model info request failed: {response.status_code}")
                return None
    except Exception as e:
        logger.error(f"Error fetching model info: {type(e).__name__} - {str(e)}")
        return None


def predict_batch_from_dataframe(df: pd.DataFrame) -> Optional[Dict]:
    """
    Appelle l'API FastAPI pour prédire le churn sur un batch de clients.

    Args:
        df: DataFrame contenant les features des clients

    Returns:
        Dict avec les résultats des prédictions ou None en cas d'erreur
    """
    try:
        # Convertir le DataFrame en CSV
        csv_buffer = io.StringIO()
        df.to_csv(csv_buffer, index=False)
        csv_content = csv_buffer.getvalue()

        files = {"file": ("predictions.csv", csv_content, "text/csv")}

        with httpx.Client(timeout=60.0) as client:
            response = client.post(
                f"{FASTAPI_BASE_URL}{FASTAPI_ENDPOINTS['predict_batch']}", files=files
            )

            if response.status_code == 200:
                return response.json()
            else:
                logger.error(
                    f"Batch prediction request failed: {response.status_code} - {response.text}"
                )
                return None

    except Exception as e:
        logger.error(
            f"Error calling FastAPI predict_batch: {type(e).__name__} - {repr(e)}\n"
            f"{traceback.format_exc()}"
        )
        return None


def predict_single_client(client_features: Dict) -> Optional[Dict]:
    """
    Appelle l'API FastAPI pour prédire le churn d'un seul client.

    Args:
        client_features: Dict avec les features du client

    Returns:
        Dict avec la prédiction ou None en cas d'erreur
    """
    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(
                f"{FASTAPI_BASE_URL}{FASTAPI_ENDPOINTS['predict']}",
                json=client_features,
            )

            if response.status_code == 200:
                return response.json()
            else:
                logger.error(
                    f"Single prediction request failed: {response.status_code} - {response.text}"
                )
                return None

    except Exception as e:
        logger.error(
            f"Error calling FastAPI predict: {type(e).__name__} - {repr(e)}\n"
            f"Payload keys: {list(client_features.keys())}\n"
            f"{traceback.format_exc()}"
        )
        return None


def analyse_portefeuille_from_csv(csv_bytes: bytes) -> Optional[Dict]:
    """
    Appelle l'API FastAPI pour analyser le portefeuille complet.

    Args:
        csv_bytes: Contenu du fichier CSV en bytes

    Returns:
        Dict avec les statistiques du portefeuille ou None en cas d'erreur
    """
    try:
        files = {"file": ("portefeuille.csv", csv_bytes, "text/csv")}

        with httpx.Client(timeout=120.0) as client:
            response = client.post(
                f"{FASTAPI_BASE_URL}{FASTAPI_ENDPOINTS['analyse']}", files=files
            )

            if response.status_code == 200:
                return response.json()
            else:
                logger.error(
                    f"Analyse request failed: {response.status_code} - {response.text}"
                )
                return None

    except Exception as e:
        logger.error(
            f"Error calling FastAPI analyse: {type(e).__name__} - {repr(e)}\n"
            f"{traceback.format_exc()}"
        )
        return None
