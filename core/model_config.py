MODEL_METRICS = {
    "name": "XGBoost Optuna v3",
    "aucroc": 0.8646,
    "f1_score": 0.717,
    "recall": 0.76,
    "precision": 0.6786,
    "optimal_threshold": 0.31,
}

MODEL_HYPERPARAMETERS = {
    "n_estimators": 188,
    "max_depth": 6,
    "learning_rate": 0.0393,
    "scale_pos_weight": 1.1058,
    "min_child_weight": 3,
    "subsample": 0.8377,
    "colsample_bytree": 0.6547,
    "reg_alpha": 0.0795,
    "reg_lambda": 2.1903,
    "gamma": 0.1779,
    "colsample_bylevel": 0.7378,
}

SHAP_FEATURES = [
    {
        "rank": 1,
        "feature": "tenure_mois",
        "importance": 0.1039,
        "description": "Ancienneté en mois",
    },
    {
        "rank": 2,
        "feature": "nb_evenements_total",
        "importance": 0.0752,
        "description": "Nombre total d'événements",
    },
    {
        "rank": 3,
        "feature": "facture_moyenne_mensuelle",
        "importance": 0.0447,
        "description": "Facture moyenne mensuelle",
    },
    {
        "rank": 4,
        "feature": "duree_appel_moyenne_sec",
        "importance": 0.0293,
        "description": "Durée moyenne des appels",
    },
    {
        "rank": 5,
        "feature": "data_moyenne_gb",
        "importance": 0.0269,
        "description": "Consommation data moyenne",
    },
    {
        "rank": 6,
        "feature": "duree_session_moyenne_sec",
        "importance": 0.0218,
        "description": "Durée moyenne des sessions",
    },
    {
        "rank": 7,
        "feature": "taux_cookies",
        "importance": 0.0218,
        "description": "Taux d'acceptation cookies",
    },
    {
        "rank": 8,
        "feature": "recence_session_jours",
        "importance": 0.0205,
        "description": "Récence de la dernière session",
    },
    {
        "rank": 9,
        "feature": "nb_sessions",
        "importance": 0.0142,
        "description": "Nombre de sessions",
    },
    {
        "rank": 10,
        "feature": "ratio_sms_appels",
        "importance": 0.0142,
        "description": "Ratio SMS/Appels",
    },
]

SHAP_INTERPRETATIONS = {
    "tenure_mois": {
        "sens": "négatif",
        "interpretation": "Plus l'ancienneté est élevée, plus le risque de churn diminue. Les clients fidèles sont moins susceptibles de partir.",
    },
    "nb_evenements_total": {
        "sens": "positif",
        "interpretation": "Un nombre élevé d'événements peut indiquer une utilisation intensive mais aussi des problèmes de service.",
    },
    "facture_moyenne_mensuelle": {
        "sens": "positif",
        "interpretation": "Une facture élevée peut indiquer une sensibilité au prix et un risque accru de churn si la valeur perçue baisse.",
    },
    "duree_appel_moyenne_sec": {
        "sens": "positif",
        "interpretation": "Des appels longs peuvent indiquer des problèmes techniques ou des insatisfactions récurrentes.",
    },
    "data_moyenne_gb": {
        "sens": "positif",
        "interpretation": "Une consommation data élevée peut indiquer un usage intensif mais aussi une sensibilité aux coûts.",
    },
}


def get_model_info():
    return {
        "metrics": MODEL_METRICS,
        "hyperparameters": MODEL_HYPERPARAMETERS,
        "shap_features": SHAP_FEATURES,
        "interpretations": SHAP_INTERPRETATIONS,
    }


def get_shap_importance(feature_name):
    for feat in SHAP_FEATURES:
        if feat["feature"] == feature_name:
            return feat["importance"]
    return 0.0


def predict_churn_score(client):
    score = 0.35
    tenure = client.anciennete_mois or 0
    score -= min(tenure / 60, 1.0) * 0.2
    appels = client.nb_appels or 0
    score += min(appels / 50, 1.0) * 0.15
    facture = client.facture_moyenne_mensuelle or 0
    score += min(facture / 150, 1.0) * 0.1
    reclamations = client.nb_reclamations or 0
    score += min(reclamations / 5, 1.0) * 0.3
    retards = client.retards_paiement or 0
    score += min(retards / 4, 1.0) * 0.25
    score = max(0, min(1, score))
    return round(score, 3)


def estimate_clv(
    client,
    score: float = None,
    months_horizon: int = 24,
    min_months: int = 3,
    max_months: int = 36,
) -> float:
    """
    Estime une CLV (valeur vie client) simple et heuristique basée sur la
    facture moyenne mensuelle et la probabilité de churn.

    Logique : on approxime le nombre de mois restants par une heuristique
    dépendant de la probabilité de churn (score). Plus le score est élevé,
    moins la durée attendue est longue.

    Args:
        client: instance contenant `facture_moyenne_mensuelle` et possiblement `score_churn`.
        score: probabilité de churn (0..1). Si None, utilise `client.score_churn` ou `predict_churn_score`.
        months_horizon: échelle de référence (par défaut 24 mois).
        min_months / max_months: bornes pour la durée estimée.

    Returns:
        float: CLV estimée en mêmes unités que `facture_moyenne_mensuelle`.
    """
    facture = float(getattr(client, "facture_moyenne_mensuelle", 0) or 0)
    if facture <= 0:
        return 0.0

    p = score if score is not None else getattr(client, "score_churn", None)
    if p is None:
        try:
            p = predict_churn_score(client)
        except Exception:
            p = 0.32

    # Heuristique : durée attendue proportionnelle à (1 - p) sur l'horizon
    expected_months = int(round((1.0 - float(p)) * months_horizon))
    expected_months = max(min_months, min(max_months, expected_months))

    clv = facture * expected_months
    return round(float(clv), 2)
