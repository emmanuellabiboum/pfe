# =============================================================================
# app/schemas/prediction.py — Schémas de réponse pour les endpoints de prédiction
# PFE — Prédiction du Churn — Tunisie Télécom Agence Kairouan
# =============================================================================
#
# JUSTIFICATION :
# Définir les réponses comme des modèles Pydantic présente trois avantages :
#   1. FastAPI valide automatiquement la sortie (impossible de renvoyer
#      un format incorrect par accident)
#   2. Swagger UI affiche le format exact attendu pour chaque endpoint
#   3. React peut générer un client TypeScript typé depuis OpenAPI (pratique
#      pour Mehdi/Zied dans leur dashboard)

from pydantic import BaseModel, Field
from typing   import List, Literal


# =============================================================================
# RÉPONSE — Prédiction individuelle (POST /api/predict)
# =============================================================================

class FeatureExplicative(BaseModel):
    """
    Une feature explicative parmi le top N retourné par SHAP pour un client.

    Direction :
      - 'vers_churn'    : la valeur de cette feature pousse le client à partir
      - 'vers_fidelite' : la valeur de cette feature pousse le client à rester
    """
    feature        : str   = Field(..., description="Nom de la feature")
    valeur         : float = Field(..., description="Valeur de la feature pour ce client")
    shap_value     : float = Field(..., description="Contribution SHAP (peut être négative)")
    direction      : Literal["vers_churn", "vers_fidelite"] = Field(
        ..., description="Sens de l'effet sur la prédiction"
    )
    interpretation : str   = Field(..., description="Interprétation métier en français")


class PredictionResponse(BaseModel):
    """
    Réponse complète d'une prédiction individuelle avec explications SHAP.

    Utilisée par la fiche client React pour afficher :
      - Le verdict (CHURN / NON-CHURN)
      - La probabilité brute (0 à 1)
      - Le seuil de décision retenu (0.32 pour le RF Optuna Fβ=2)
      - Le niveau de confiance basé sur l'écart au seuil
      - Le top 5 des features qui ont le plus influencé la décision
    """
    probabilite_churn     : float = Field(..., ge=0, le=1,
                                          description="Probabilité de churn (0 à 1)")
    decision              : Literal["CHURN", "NON-CHURN"] = Field(
        ..., description="Décision binaire selon le seuil"
    )
    seuil                 : float = Field(..., ge=0, le=1,
                                          description="Seuil de décision utilisé")
    confiance             : Literal["élevée", "modérée", "faible"] = Field(
        ..., description="Niveau de confiance basé sur l'écart au seuil"
    )
    valeur_base_shap      : float = Field(..., description="Valeur de base SHAP (proba moyenne du train)")
    features_explicatives : List[FeatureExplicative] = Field(
        ..., description="Top N features triées par |SHAP value| décroissant"
    )
    modele                : str   = Field(..., description="Nom du modèle utilisé")
    version               : str   = Field(..., description="Version du modèle")


# =============================================================================
# RÉPONSE — Prédiction batch sur CSV (POST /api/predict/batch)
# =============================================================================

class PredictionBatchItem(BaseModel):
    """Une ligne de prédiction dans une réponse batch."""
    index             : int    = Field(..., description="Index de la ligne dans le CSV")
    probabilite_churn : float  = Field(..., description="Probabilité de churn (0 à 1, ou -1 si erreur)")
    decision          : str    = Field(..., description="CHURN / NON-CHURN / ERREUR")
    confiance         : str    = Field(..., description="élevée / modérée / faible / message d'erreur")


class PredictionBatchResponse(BaseModel):
    """
    Réponse complète d'une prédiction batch sur un fichier CSV.

    [Étape 8.2] Inclut maintenant la liste des transformations de modalités
    appliquées automatiquement au CSV brut (transparence pour l'utilisateur).
    """
    total                      : int   = Field(..., description="Nombre total de clients traités")
    nb_churn                   : int   = Field(..., description="Nombre de churners prédits")
    taux_churn_predit          : float = Field(..., ge=0, le=1, description="Taux de churn prédit (0 à 1)")
    transformations_appliquees : List[str] = Field(
        default_factory = list,
        description     = (
            "Transformations de modalités appliquées automatiquement au CSV brut "
            "(suppression accents, parenthèses, etc.). Vide si aucune transformation."
        ),
    )
    predictions                : List[PredictionBatchItem] = Field(
        ..., description="Détail ligne par ligne"
    )


# =============================================================================
# RÉPONSE — Analyse complète du portefeuille (POST /api/analyse)
# =============================================================================

class AnalyseRapportResponse(BaseModel):
    """
    Rapport de segmentation du portefeuille en churn / non-churn.

    [Étape 8.4] Métriques simplifiées pour segmentation binaire :
      - nb_churn          : nombre de clients prédits CHURN (proba >= seuil 0.32)
      - nb_non_churn      : nombre de clients prédits NON-CHURN (proba < seuil 0.32)
    """
    success                    : bool  = Field(..., description="Statut de l'analyse")
    total                      : int   = Field(..., description="Nombre total de clients analysés")
    nb_churn                   : int   = Field(..., description="Clients prédits CHURN (proba >= 0.32)")
    nb_non_churn               : int   = Field(..., description="Clients prédits NON-CHURN (proba < 0.32)")
    score_moyen                : float = Field(..., description="Score de churn moyen du portefeuille (en %)")
    taux_churn_predit          : float = Field(..., description="Taux de clients prédits CHURN, seuil 0.32 (en %)")
    nb_recommandations         : int   = Field(..., description="Nombre de clients à actionner (CHURN)")
    transformations_appliquees : List[str] = Field(
        default_factory = list,
        description     = "Transformations de modalités appliquées au CSV brut",
    )


# =============================================================================
# RÉPONSE — Explication SHAP par client (GET /api/shap/{client_id})
# =============================================================================

class ShapFeatureWaterfall(BaseModel):
    """Une feature dans le waterfall chart SHAP."""
    nom       : str    = Field(..., description="Nom de la feature")
    valeur    : float  = Field(..., description="Valeur de la feature pour ce client")
    shap      : float  = Field(..., description="Contribution SHAP")
    direction : Literal["vers_churn", "vers_fidelite"] = Field(
        ..., description="Sens de l'effet"
    )


class ShapWaterfallResponse(BaseModel):
    """
    Réponse formatée pour le waterfall chart SHAP côté React.

    Utilisée par /api/shap/{client_id} pour afficher le détail visuel des
    contributions de chaque feature à la prédiction d'un client précis du
    test set (cf. shap_matrix_v1.csv exporté en cellule C8 du notebook).
    """
    client_id         : int   = Field(..., description="Index du client dans le test set")
    probabilite_churn : float = Field(..., ge=0, le=1,
                                      description="Probabilité de churn pour ce client")
    decision          : str   = Field(..., description="CHURN / NON-CHURN")
    valeur_base       : float = Field(..., description="Valeur de base SHAP")
    features          : List[ShapFeatureWaterfall] = Field(
        ..., description="Top features avec leur contribution SHAP"
    )


# =============================================================================
# RÉPONSE — Liste paginée des clients (GET /api/clients)
# =============================================================================

class ClientListItem(BaseModel):
    """Un client dans la liste paginée avec son score churn."""
    id                : int    = Field(..., description="Index du client dans le test set")
    probabilite_churn : float  = Field(..., ge=0, le=1)
    decision          : str    = Field(..., description="CHURN / NON-CHURN")


class ClientListResponse(BaseModel):
    """
    Liste paginée des clients du test set avec leur score churn pré-calculé.

    Source des données : shap_matrix_v1.csv (Étape C8 du notebook). En
    production réelle, ces clients viendraient d'une base de données et les
    scores seraient calculés à la volée via le modèle chargé.
    """
    total   : int                  = Field(..., description="Nombre total de clients (avant pagination)")
    page    : int                  = Field(..., ge=1, description="Page courante (1-indexed)")
    limit   : int                  = Field(..., ge=1, description="Nombre d'items par page")
    pages   : int                  = Field(..., ge=0, description="Nombre total de pages")
    clients : List[ClientListItem] = Field(..., description="Clients de cette page")