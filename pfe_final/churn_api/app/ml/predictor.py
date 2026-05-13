# =============================================================================
# app/ml/predictor.py — Logique de prédiction + explications SHAP
# PFE — Prédiction du Churn — Tunisie Télécom Agence Kairouan
# =============================================================================
#
# JUSTIFICATION ARCHITECTURALE :
# Ce fichier orchestre l'inférence complète : preprocessing → prédiction →
# SHAP → mise en forme. Il est volontairement DÉCOUPLÉ du framework web
# (FastAPI) pour deux raisons :
#   1. Testabilité : on peut tester ces fonctions sans démarrer un serveur HTTP
#   2. Réutilisabilité : si demain on passe à Flask ou à un job batch, le
#      code reste utilisable tel quel
#
# Les routers (Étape 5) appelleront ces fonctions et se contenteront de gérer
# le HTTP (codes de statut, validation des uploads, etc.)

from typing import Any, Dict, List

import numpy  as np
import pandas as pd

from app.ml.loader          import MLArtifacts
from app.ml.preprocessing   import pretraiter_client, pretraiter_dataframe
from app.ml.interpretations import get_interpretation
from app.config             import (
    SEUIL_CHURN,
    MODEL_VERSION,
)
from app.schemas.client     import ClientFeatures


# =============================================================================
# UTILITAIRES INTERNES
# =============================================================================

def _calculer_confiance(proba: float, seuil: float) -> str:
    """
    Évalue la confiance de la prédiction en fonction de l'écart entre la
    probabilité et le seuil de décision.

    Logique :
      - Plus l'écart est grand, plus la décision est tranchée
      - Plus l'écart est petit (proba ≈ seuil), plus on hésite

    Cette information aide le conseiller à savoir s'il peut suivre la
    recommandation aveuglément (confiance élevée) ou s'il doit examiner
    le dossier de plus près (confiance faible).
    """
    ecart = abs(proba - seuil)
    if ecart >= 0.30:
        return "élevée"
    elif ecart >= 0.15:
        return "modérée"
    else:
        return "faible"





def _extraire_top_features_shap(
    shap_values: np.ndarray,
    valeurs_features: np.ndarray,
    feature_names: List[str],
    top_n: int = 5,
) -> List[Dict[str, Any]]:
    """
    Extrait les top N features par |SHAP value| décroissant et formate la
    réponse pour FeatureExplicative.

    Args:
        shap_values      : vecteur 1D des contributions SHAP (1 par feature)
        valeurs_features : vecteur 1D des valeurs des features (1 par feature)
        feature_names    : noms des features (même ordre que shap_values)
        top_n            : nombre de features à retourner

    Returns:
        Liste de dicts compatibles avec FeatureExplicative (Pydantic).
    """
    indices_top = np.argsort(np.abs(shap_values))[::-1][:top_n]

    explications = []
    for idx in indices_top:
        feature_name = feature_names[idx]
        shap_val     = float(shap_values[idx])
        valeur       = float(valeurs_features[idx])

        # Direction : positive → pousse vers churn, négative → pousse vers fidélité
        direction = "vers_churn" if shap_val > 0 else "vers_fidelite"
        interpretation = get_interpretation(feature_name, direction)

        explications.append({
            "feature"        : feature_name,
            "valeur"         : round(valeur, 4),
            "shap_value"     : round(shap_val, 4),
            "direction"      : direction,
            "interpretation" : interpretation,
        })

    return explications


# =============================================================================
# PRÉDICTION INDIVIDUELLE — pour POST /api/predict
# =============================================================================

def predire_client(
    client: ClientFeatures,
    artefacts: MLArtifacts,
    top_n: int = 5,
) -> Dict[str, Any]:
    """
    Prédit le churn pour un client unique avec explications SHAP individuelles.

    Pipeline complet :
      1. Encodage features brutes → 31 colonnes du modèle (preprocessing)
      2. Prédiction de probabilité (modele.predict_proba)
      3. Décision binaire selon le seuil
      4. Calcul des SHAP values pour ce client (TreeExplainer exact)
      5. Extraction du top 5 par |SHAP value|
      6. Mise en forme de la réponse compatible PredictionResponse

    Args:
        client    : ClientFeatures Pydantic validé
        artefacts : MLArtifacts chargés au boot (modele, seuil, explainer...)
        top_n     : nombre de features SHAP à retourner (défaut 5)

    Returns:
        Dict compatible avec PredictionResponse (Pydantic).

    Note sur le format SHAP :
        TreeExplainer sur RandomForestClassifier retourne un objet Explanation
        avec une matrice 3D : [n_clients, n_features, n_classes].
        On extrait `[0, :, 1]` pour avoir les contributions de la classe 1
        (churn) du premier (et unique) client.
        C'est le format standard pour SHAP >= 0.40 sur les modèles arborescents
        de classification binaire (cf. cellule C8 du notebook).
    """
    # ── 1. Preprocessing ─────────────────────────────────────────────────────
    X = pretraiter_client(client, artefacts.preprocessing_params)

    # ── 2. Prédiction ────────────────────────────────────────────────────────
    proba = float(artefacts.modele.predict_proba(X)[0, 1])

    # ── 3. Décision binaire ──────────────────────────────────────────────────
    decision  = "CHURN" if proba >= artefacts.seuil else "NON-CHURN"
    confiance = _calculer_confiance(proba, artefacts.seuil)

    # ── 4. Calcul SHAP en live ──────────────────────────────────────────────
    # Format moderne de SHAP : explainer(X) renvoie un objet Explanation
    shap_explanation = artefacts.explainer(X)

    # Pour un RandomForestClassifier binaire, .values est de shape (1, 31, 2)
    # On extrait les contributions de la classe 1 (churn) pour le 1er client
    shap_values_client = shap_explanation.values[0, :, 1]
    base_value         = float(shap_explanation.base_values[0, 1])

    # ── 5. Top N features ───────────────────────────────────────────────────
    valeurs_features = X.iloc[0].values
    explications = _extraire_top_features_shap(
        shap_values      = shap_values_client,
        valeurs_features = valeurs_features,
        feature_names    = artefacts.feature_names,
        top_n            = top_n,
    )

    # ── 6. Construction de la réponse ───────────────────────────────────────
    return {
        "probabilite_churn"     : round(proba, 4),
        "decision"              : decision,
        "seuil"                 : artefacts.seuil,
        "confiance"             : confiance,
        "valeur_base_shap"      : round(base_value, 4),
        "features_explicatives" : explications,
        "modele"                : artefacts.metadata.get("modele", {}).get(
                                    "nom", "RF Optuna Fβ=2"),
        "version"               : MODEL_VERSION,
    }


# =============================================================================
# PRÉDICTION BATCH — pour POST /api/predict/batch et /api/analyse
# =============================================================================

def predire_batch(
    df_raw: pd.DataFrame,
    artefacts: MLArtifacts,
) -> Dict[str, Any]:
    """
    Prédit le churn sur un DataFrame complet en mode vectoriel.

    [Étape 8.2] Le log des transformations de modalités est inclus dans la
    réponse pour transparence.
    """
    log_transformations: List[str] = []

    try:
        # Preprocessing vectoriel + récupération du log
        X_all, log_transformations = pretraiter_dataframe(
            df_raw, artefacts.preprocessing_params
        )

        # Prédictions vectorielles
        probas = artefacts.modele.predict_proba(X_all)[:, 1]

        # Mise en forme ligne par ligne
        predictions = []
        for idx, proba in enumerate(probas):
            proba_f   = float(proba)
            decision  = "CHURN" if proba_f >= artefacts.seuil else "NON-CHURN"
            confiance = _calculer_confiance(proba_f, artefacts.seuil)

            predictions.append({
                "index"             : idx,
                "probabilite_churn" : round(proba_f, 4),
                "decision"          : decision,
                "confiance"         : confiance,
            })

    except Exception as e:
        # Fallback : on rend une réponse même en cas d'erreur
        predictions = [
            {
                "index"             : i,
                "probabilite_churn" : -1.0,
                "decision"          : "ERREUR",
                "confiance"         : str(e)[:200],
            }
            for i in range(len(df_raw))
        ]

    nb_churn = sum(1 for p in predictions if p["decision"] == "CHURN")
    total    = len(predictions)

    return {
        "total"                      : total,
        "nb_churn"                   : nb_churn,
        "taux_churn_predit"          : round(nb_churn / total, 4) if total > 0 else 0.0,
        "transformations_appliquees" : log_transformations,    # [Étape 8.2]
        "predictions"                : predictions,
    }


# =============================================================================
# ANALYSE DE PORTEFEUILLE — pour POST /api/analyse
# =============================================================================

def analyser_portefeuille(
    df_raw: pd.DataFrame,
    artefacts: MLArtifacts,
) -> Dict[str, Any]:
    """
    Segmente le portefeuille complet en churn / non-churn.

    [Étape 8.4] Métriques simplifiées :
      - nb_churn            : clients prédits CHURN (proba >= seuil 0.32)
      - nb_non_churn        : clients prédits NON-CHURN (proba < seuil 0.32)
      - taux_churn_predit   : % clients prédits CHURN
      - score_moyen         : moyenne des probabilités du portefeuille
    """
    X_all, log_transformations = pretraiter_dataframe(
        df_raw, artefacts.preprocessing_params
    )
    probas = artefacts.modele.predict_proba(X_all)[:, 1]

    # Comptage binaire
    nb_churn = int(np.sum(probas >= SEUIL_CHURN))
    nb_non_churn = int(np.sum(probas < SEUIL_CHURN))
    total  = len(probas)

    score_moyen       = float(probas.mean()) if total > 0 else 0.0
    taux_churn_predit = nb_churn / total if total > 0 else 0.0

    return {
        "success"                    : True,
        "total"                      : total,
        "nb_churn"                   : nb_churn,
        "nb_non_churn"               : nb_non_churn,
        "score_moyen"                : round(score_moyen * 100, 1),
        "taux_churn_predit"          : round(taux_churn_predit * 100, 1),
        "nb_recommandations"         : nb_churn,
        "transformations_appliquees" : log_transformations,
    }


# =============================================================================
# EXPLICATION SHAP D'UN CLIENT DU TEST SET — pour GET /api/shap/{client_id}
# =============================================================================

def expliquer_client_test_set(
    client_id: int,
    shap_matrix: pd.DataFrame,
    artefacts: MLArtifacts,
    top_n: int = 10,
) -> Dict[str, Any]:
    """
    Récupère les explications SHAP pré-calculées d'un client du test set.

    Différence avec predire_client :
      - predire_client recalcule TOUT à chaque appel (preprocessing + SHAP)
        pour un nouveau client
      - expliquer_client_test_set lit shap_matrix_v1.csv (calculé une fois
        en cellule C8 du notebook) pour un client déjà vu

    Utilisé par le dashboard React pour afficher rapidement le waterfall
    chart de n'importe quel client présent dans la matrice SHAP exportée.

    Args:
        client_id   : index du client dans shap_matrix (positionnel)
        shap_matrix : DataFrame chargé depuis shap_matrix_v1.csv
        artefacts   : MLArtifacts pour reconstituer la proba (le CSV ne
                      contient que les SHAP, pas les probas brutes)
        top_n       : nombre de features à retourner pour le waterfall

    Returns:
        Dict compatible avec ShapWaterfallResponse.

    Raises:
        IndexError : si client_id dépasse la taille de shap_matrix.
    """
    if client_id < 0 or client_id >= len(shap_matrix):
        raise IndexError(
            f"client_id={client_id} hors bornes "
            f"(0 à {len(shap_matrix) - 1} attendu)"
        )

    # Récupération de la ligne SHAP du client demandé
    shap_row = shap_matrix.iloc[client_id]
    feature_names = list(shap_matrix.columns)
    shap_values = shap_row.values

    # ── Calcul de la proba via la base_value SHAP ──────────────────────────
    # Pour un RandomForest, somme(SHAP) + base_value ≈ proba prédite
    # C'est une propriété fondamentale de SHAP (additivité)
    base_value = float(
        artefacts.shap_meta.get("base_value", {}).get("valeur", 0.5)
    )
    proba = float(base_value + np.sum(shap_values))

    # Borne par sécurité dans [0, 1] (peut légèrement dépasser à cause
    # d'arrondis numériques sur certains modèles)
    proba = max(0.0, min(1.0, proba))

    decision = "CHURN" if proba >= artefacts.seuil else "NON-CHURN"

    # ── Top N features avec direction et interprétation ─────────────────────
    indices_top = np.argsort(np.abs(shap_values))[::-1][:top_n]

    features_waterfall = []
    for idx in indices_top:
        feat_name = feature_names[idx]
        shap_val  = float(shap_values[idx])
        direction = "vers_churn" if shap_val > 0 else "vers_fidelite"

        features_waterfall.append({
            "nom"       : feat_name,
            # On n'a pas la valeur brute de la feature dans shap_matrix.csv
            # (seulement les SHAP). On met 0.0 par défaut.
            # En production réelle, on stockerait aussi X_test.csv pour les retrouver.
            "valeur"    : 0.0,
            "shap"      : round(shap_val, 4),
            "direction" : direction,
        })

    return {
        "client_id"         : client_id,
        "probabilite_churn" : round(proba, 4),
        "decision"          : decision,
        "valeur_base"       : round(base_value, 4),
        "features"          : features_waterfall,
    }