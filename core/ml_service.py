import json
import joblib
# import shap  # Déplacé dans les fonctions
import numpy as np
import pandas as pd
import unicodedata
from pathlib import Path

from core.ml_pipeline import (
    FEATURE_NAMES_ORDERED,
    pretraiter_dataframe,
    pretraiter_client,
)

BASE_DIR = Path(__file__).parent.parent
MODELS_DIR = BASE_DIR / "pfe_final" / "churn_api" / "fastapi_artifacts"

MODEL_PATH = MODELS_DIR / "churn_model_v1.pkl"
METADATA_PATH = MODELS_DIR / "churn_metadata_v1.json"

ensemble_model = None
xgb_component = None
metadata = None
params = {"feature_names_ordered": FEATURE_NAMES_ORDERED}
SEUIL = None
explainer = None

# Vérifier si le dossier fastapi_artifacts existe
MODELS_AVAILABLE = MODELS_DIR.exists() and MODEL_PATH.exists()

INTERPRETATIONS = {
    "tenure_mois": {
        "vers_churn": "Ancienneté faible → risque de départ élevé",
        "vers_retention": "Ancienneté élevée → client fidélisé",
    },
    "nb_evenements_total": {
        "vers_churn": "Faible activité réseau → désengagement",
        "vers_retention": "Activité élevée → client engagé",
    },
    "facture_moyenne_mensuelle": {
        "vers_churn": "Facture aux extrêmes → insatisfaction tarifaire",
        "vers_retention": "Facture équilibrée → bon rapport qualité/prix",
    },
    "duree_appel_moyenne_sec": {
        "vers_churn": "Appels courts → usage voix superficiel",
        "vers_retention": "Appels longs → usage voix intensif",
    },
    "data_moyenne_gb": {
        "vers_churn": "Faible consommation data → sous-utilisation",
        "vers_retention": "Forte consommation data → client data intensif",
    },
    "recence_session_jours": {
        "vers_churn": "Longue inactivité data → abandon progressif",
        "vers_retention": "Session data récente → client actif",
    },
    "duree_session_moyenne_sec": {
        "vers_churn": "Sessions courtes → qualité réseau insuffisante",
        "vers_retention": "Sessions longues → bonne qualité de connexion",
    },
    "taux_cookies": {
        "vers_churn": "Engagement digital élevé → exposition concurrence",
        "vers_retention": "Engagement digital modéré → profil stable",
    },
    "nb_sessions": {
        "vers_churn": "Peu de sessions → client sous-engagé",
        "vers_retention": "Nombreuses sessions → client très actif",
    },
    "ratio_sms_appels": {
        "vers_churn": "Usage SMS dominant → migration vers messageries",
        "vers_retention": "Usage voix dominant → attachement au réseau",
    },
    "qualite_signal_dominante": {
        "vers_churn": "Signal faible → insatisfaction réseau",
        "vers_retention": "Signal excellent → satisfaction réseau",
    },
    "satisfaction_client": {
        "vers_churn": "Satisfaction basse → risque de résiliation",
        "vers_retention": "Satisfaction élevée → client satisfait",
    },
    "score_frustration": {
        "vers_churn": "Frustration élevée → client mécontent",
        "vers_retention": "Faible frustration → client serein",
    },
}


def load_ml_model():
    import shap
    import numpy as np
    global ensemble_model, xgb_component, metadata, SEUIL, explainer

    if not MODELS_AVAILABLE:
        print(
            "Modèles ML non disponibles (dossier pfe_final/churn_api/fastapi_artifacts absent)"
        )
        return False

    try:
        ensemble_model = joblib.load(MODEL_PATH)
        # Le modèle est un RandomForestClassifier (pas un ensemble Voting/Stacking)
        # On garde xgb_component comme alias pour la compatibilité avec TreeExplainer
        xgb_component = ensemble_model

        with open(METADATA_PATH, "r", encoding="utf-8") as f:
            metadata = json.load(f)

        SEUIL = metadata.get("seuil_decision", {}).get("valeur", 0.32)

        explainer = shap.TreeExplainer(ensemble_model)
        return True
    except Exception as e:
        print(f"Erreur chargement modèle ML: {e}")
        return False


def _build_fastapi_payload_from_client(client) -> dict:
    """
    Construit le payload canonique attendu par pfe_final/churn_api (/api/predict),
    en tenant compte des enums Pydantic.
    """

    # Mapping des valeurs vers les enums attendus par l'API (cf. pfe_final/churn_api/app/schemas/client.py)
    # NB: /api/predict valide strictement via Pydantic → il faut envoyer les libellés "canoniques".
    def _normalize_label(value: str) -> str:
        if value is None:
            return ""
        normalized = unicodedata.normalize("NFKD", str(value).strip().lower())
        return "".join(ch for ch in normalized if not unicodedata.combining(ch))

    genre_map = {"femme": "Femme", "homme": "Homme"}
    type_abo_map = {
        "offre prepayee": "Offre Prepayee",
        "prepaye": "Offre Prepayee",
        "prepayee": "Offre Prepayee",
        "offre a facture": "Offre a Facture",
        "postpaye": "Offre a Facture",
        "post-payee": "Offre a Facture",
        "facture": "Offre a Facture",
    }
    plan_map = {
        "forfait illimite": "Forfait Illimite",
        "forfait illimitee": "Forfait Illimite",
        "forfait mobile mixte": "Forfait_Mobile_Mixte",
        "forfait mobile (mixte)": "Forfait_Mobile_Mixte",
        "offre classique": "Offre Classique",
    }
    moyen_paiement_map = {
        "especes": "especes",
        "espèces": "especes",
        "espèces": "especes",
        "prelevement_bancaire": "prelevement_bancaire",
        "prelevement": "prelevement_bancaire",
        "prélèvement": "prelevement_bancaire",
        "prélèvement": "prelevement_bancaire",
        "virement": "prelevement_bancaire",
        "ticket_recharge": "ticket_recharge",
        "ticket": "ticket_recharge",
        "recharge": "ticket_recharge",
    }
    zone_map = {"RURAL": "RURAL", "SUBURBAIN": "SUBURBAIN", "URBAIN": "URBAIN"}
    signal_map = {"Faible": "Faible", "Bon": "Bon", "Excellent": "Excellent"}

    zone_val = getattr(client, "zone_reseau_principale", None) or getattr(
        client, "zone_reseau", None
    )
    signal_val = getattr(client, "qualite_signal_dominante", None) or getattr(
        client, "qualite_signal", None
    )

    duree_appel_moyenne_sec = float(getattr(client, "duree_appel_moyenne_sec", 0) or 0)
    data_totale_mb = getattr(client, "data_totale_mb", None)
    if data_totale_mb is None:
        data_totale_mb = getattr(client, "consommation_moyenne", None)
    data_moyenne_gb = getattr(client, "data_moyenne_gb", None)
    if data_moyenne_gb is None:
        data_moyenne_gb = float((data_totale_mb / 1024) if data_totale_mb else 0)
    else:
        data_moyenne_gb = float(data_moyenne_gb or 0)
    nb_appels = float(getattr(client, "nb_appels", 0) or 0)
    sms_total = float(getattr(client, "sms_total", 0) or 0)
    ratio_sms_appels = float((sms_total / nb_appels) if nb_appels > 0 else 0)

    # Déterminer les flags d'offre intelligemment selon l'usage réel si non fournis
    # On considère qu'une offre existe si n'importe quel indicateur d'usage est > 0
    has_data_usage = (
        data_moyenne_gb > 0
        or int(getattr(client, "nb_sessions", 0) or 0) > 0
        or float(getattr(client, "duree_session_moyenne_sec", 0) or 0) > 0
    )
    has_voix_usage = (
        duree_appel_moyenne_sec > 0
        or float(getattr(client, "ratio_sms_appels", 0) or 0) > 0
    )

    flag_offre_data = getattr(client, "flag_offre_data", None)
    if flag_offre_data is None or flag_offre_data == 0:
        flag_offre_data = 1 if has_data_usage else 0

    flag_offre_voix = getattr(client, "flag_offre_voix", None)
    if flag_offre_voix is None or flag_offre_voix == 0:
        flag_offre_voix = 1 if has_voix_usage else 0

    raw_type_abonnement = _normalize_label(getattr(client, "type_abonnement", None))
    raw_plan_tarifaire = _normalize_label(getattr(client, "plan_tarifaire", None))
    raw_moyen_paiement = _normalize_label(getattr(client, "moyen_paiement", ""))

    type_abonnement = type_abo_map.get(raw_type_abonnement)
    if type_abonnement is None:
        if "prepay" in raw_type_abonnement:
            type_abonnement = "Offre Prepayee"
        elif "facture" in raw_type_abonnement:
            type_abonnement = "Offre a Facture"
        else:
            type_abonnement = "Offre Prepayee"

    plan_tarifaire = plan_map.get(raw_plan_tarifaire)
    if plan_tarifaire is None:
        if "mobile" in raw_plan_tarifaire and "mixte" in raw_plan_tarifaire:
            plan_tarifaire = "Forfait_Mobile_Mixte"
        elif "illimit" in raw_plan_tarifaire:
            plan_tarifaire = "Forfait Illimite"
        elif "offre classique" in raw_plan_tarifaire:
            plan_tarifaire = "Offre Classique"
        else:
            plan_tarifaire = "Forfait Illimite"

    moyen_paiement = moyen_paiement_map.get(raw_moyen_paiement)
    if moyen_paiement is None:
        if "espec" in raw_moyen_paiement:
            moyen_paiement = "especes"
        elif "prelev" in raw_moyen_paiement:
            moyen_paiement = "prelevement_bancaire"
        elif "ticket" in raw_moyen_paiement:
            moyen_paiement = "ticket_recharge"
        else:
            moyen_paiement = "especes"

    return {
        "genre_client": genre_map.get(getattr(client, "genre_client", None), "Homme"),
        "type_abonnement": type_abonnement,
        "plan_tarifaire": plan_tarifaire,
        "moyen_paiement": moyen_paiement,
        "zone_reseau_principale": zone_map.get(zone_val, "URBAIN"),
        "qualite_signal_dominante": signal_map.get(signal_val, "Bon"),
        "tenure_mois": int(getattr(client, "tenure_mois", 0) or 0),
        "duree_appel_moyenne_sec": duree_appel_moyenne_sec,
        "data_moyenne_gb": data_moyenne_gb,
        "nb_evenements_total": int(getattr(client, "nb_evenements_data_cdr", 0) or 0),
        "nb_sessions": int(getattr(client, "nb_sessions", 0) or 0),
        "duree_session_moyenne_sec": float(
            getattr(client, "duree_session_moyenne_sec", None)
            or getattr(client, "duree_session_moyenne", 0)
            or 0
        ),
        "taux_cookies": float(getattr(client, "taux_cookies", 0) or 0),
        "recence_session_jours": int(getattr(client, "recence_session_jours", 0) or 0),
        "ratio_sms_appels": ratio_sms_appels,
        "score_qualite_zone": float(getattr(client, "score_qualite_zone", 4.0) or 4.0),
        "flag_offre_data": int(flag_offre_data),
        "flag_offre_voix": int(flag_offre_voix),
        "consentement_marketing": bool(
            getattr(client, "consentement_marketing", False) or False
        ),
        "optout_marketing": bool(getattr(client, "optout_marketing", False) or False),
        "data_manquante": int(1 if data_totale_mb is None else 0),
        "satisfaction_manquante": int(
            1 if getattr(client, "satisfaction_client", None) is None else 0
        ),
        "reclamation_manquante": int(
            1 if getattr(client, "reclamation_manquante", False) else 0
        ),
        "facture_moyenne_mensuelle": (
            float(getattr(client, "facture_moyenne_mensuelle", 0) or 0)
            if getattr(client, "facture_moyenne_mensuelle", None) is not None
            else None
        ),
        "satisfaction_client": (
            float(getattr(client, "satisfaction_client", 0) or 0)
            if getattr(client, "satisfaction_client", None) is not None
            else None
        ),
        "tendance_data_pct": (
            float(getattr(client, "tendance_data", 0) or 0)
            if getattr(client, "tendance_data", None) is not None
            else None
        ),
        "ratio_data_voix": (
            float(
                (data_moyenne_gb / duree_appel_moyenne_sec)
                if duree_appel_moyenne_sec > 0
                else 0
            )
            if duree_appel_moyenne_sec is not None
            else None
        ),
        "score_frustration": (
            float(getattr(client, "score_frustration", 0) or 0)
            if getattr(client, "score_frustration", None) is not None
            else None
        ),
    }


def get_fastapi_prediction_details(client):
    """Retourne la réponse complète de /api/predict (probabilité + SHAP + méta)."""
    from core.fastapi_service import predict_single_client

    try:
        payload = _build_fastapi_payload_from_client(client)
        return predict_single_client(payload)
    except Exception as e:
        print(f"Erreur FastAPI /api/predict: {e}")
        return None


def predict_churn_score_from_client(client):
    """Utilise l'API FastAPI pour prédire le score de churn (probabilité)."""
    result = get_fastapi_prediction_details(client)
    if result:
        # pfe_final/churn_api renvoie "probabilite_churn" (pas "score_churn")
        return result.get("probabilite_churn", result.get("score_churn"))
    return None


def get_shap_explanation(client):
    import shap
    import numpy as np
    if ensemble_model is None or explainer is None:
        load_ml_model()

    if ensemble_model is None or explainer is None:
        return None

    try:
        shap_path = MODELS_DIR / "shap_explications.json"

        if shap_path.exists():
            import json as json_lib

            with open(shap_path, "r", encoding="utf-8") as f:
                explications = json_lib.load(f)

            client_index = int(client.client_id) if client.client_id.isdigit() else 0

            if client_index < len(explications):
                explication = explications[client_index]

                features = []
                for f in explication["features_explicatives"]:
                    interp_dict = INTERPRETATIONS.get(f["feature"])
                    interp = (
                        interp_dict.get(f["direction"], f["feature"])
                        if interp_dict
                        else f["feature"]
                    )

                    features.append(
                        {
                            "feature": f["feature"],
                            "valeur": f["valeur"],
                            "shap_value": f["shap_value"],
                            "direction": f["direction"],
                            "interpretation": interp,
                        }
                    )

                return {
                    "base_value": explication["valeur_base"],
                    "features": features,
                }

        # Mapping correct des champs modèle → features ML
        # Utilise les VRAIS noms de champs du modèle ClientChurn
        genre = getattr(client, "genre_client", None) or "Homme"
        zone = getattr(client, "zone_reseau_principale", None) or "Kairouan Centre"
        qualite = getattr(client, "qualite_signal_dominante", None) or "Bon"
        duree_moy = getattr(client, "duree_appel_moyenne_sec", None) or 0
        data_mb = getattr(client, "data_totale_mb", None) or 0
        nb_events = getattr(client, "nb_evenements_data_cdr", None) or 0
        nb_rec = getattr(client, "nb_reclamations", None)
        rec_manquante = getattr(client, "reclamation_manquante", False)
        satisfaction = getattr(client, "satisfaction_client", None)
        tendance = getattr(client, "tendance_data", None) or 0
        nb_appels = getattr(client, "nb_appels", None) or 0
        sms = getattr(client, "sms_total", None) or 0

        # Calcul des ratios et dérivés
        ratio_sms_appels = round(sms / nb_appels, 2) if nb_appels else 0
        ratio_data_voix = round(data_mb / max(duree_moy, 1), 2) if duree_moy else 0
        data_gb = round(data_mb / 1024, 2) if data_mb else 0

        data = {
            "genre_client": genre,
            "type_abonnement": client.type_abonnement or "prepaye",
            "plan_tarifaire": client.plan_tarifaire or "Offre Classique",
            "moyen_paiement": client.moyen_paiement or "Tickets de recharge",
            "facture_moyenne_mensuelle": client.facture_moyenne_mensuelle or 0,
            "satisfaction_client": satisfaction or 3,
            "consentement_marketing": getattr(client, "consentement_marketing", False),
            "optout_marketing": getattr(client, "optout_marketing", False),
            "tenure_mois": getattr(client, "tenure_mois", 0)
            or getattr(client, "anciennete_mois", 0)
            or 0,
            "duree_appel_moyenne_sec": duree_moy,
            "data_moyenne_gb": data_gb,
            "nb_evenements_total": nb_events,
            "nb_sessions": getattr(client, "nb_sessions", 0) or 0,
            "duree_session_moyenne_sec": getattr(client, "duree_session_moyenne_sec", 0)
            or 0,
            "taux_cookies": getattr(client, "taux_cookies", 0) or 0,
            "recence_session_jours": getattr(client, "recence_session_jours", 0) or 0,
            "zone_reseau_principale": zone,
            "qualite_signal_dominante": qualite,
            "data_manquante": (
                1
                if getattr(client, "data_mois_m_manquante", 0)
                or getattr(client, "data_mois_m1_manquante", 0)
                else 0
            ),
            "satisfaction_manquante": 1 if satisfaction is None else 0,
            "reclamation_manquante": 1 if rec_manquante or nb_rec is None else 0,
            "tendance_data_pct": tendance,
            "ratio_sms_appels": ratio_sms_appels,
            "ratio_data_voix": ratio_data_voix,
            "score_qualite_zone": getattr(client, "score_qualite_zone", 0) or 0,
            "score_frustration": getattr(client, "score_frustration", 0) or 0,
            "flag_offre_data": getattr(
                client, "flag_offre_data", 1 if data_mb > 0 else 0
            ),
            "flag_offre_voix": getattr(
                client, "flag_offre_voix", 1 if duree_moy > 0 else 0
            ),
        }

        df = pd.DataFrame([data])
        X = pretraiter_dataframe(df)

        shap_vals = explainer.shap_values(X)
        expected_value = explainer.expected_value
        if isinstance(expected_value, (list, tuple)):
            base_raw = expected_value[1] if len(expected_value) > 1 else expected_value[0]
        else:
            expected_arr = np.asarray(expected_value)
            base_raw = expected_arr.reshape(-1)[1] if expected_arr.size > 1 else expected_arr.reshape(-1)[0]
        base_value = float(np.asarray(base_raw).reshape(-1)[0])

        if isinstance(shap_vals, list):
            sv = np.asarray(shap_vals[1] if len(shap_vals) > 1 else shap_vals[0])[0]
        else:
            shap_arr = np.asarray(shap_vals)
            if shap_arr.ndim == 3:
                if shap_arr.shape[-1] > 1:
                    sv = shap_arr[0, :, 1]
                elif shap_arr.shape[0] > 1:
                    sv = shap_arr[1, 0, :]
                else:
                    sv = shap_arr[0, :, 0]
            elif shap_arr.ndim == 2:
                sv = shap_arr[0]
            else:
                sv = shap_arr
        sv = np.asarray(sv, dtype=float).reshape(-1)

        indices_top = np.argsort(np.abs(sv))[::-1][:5]
        features = []

        for idx in indices_top:
            feat_name = FEATURE_NAMES_ORDERED[idx]
            shap_val = float(sv[idx])
            direction = "vers_churn" if shap_val > 0 else "vers_retention"
            interp_dict = INTERPRETATIONS.get(feat_name)
            interp = interp_dict.get(direction, feat_name) if interp_dict else feat_name

            features.append(
                {
                    "feature": feat_name,
                    "valeur": round(float(X.iloc[0, idx]), 4),
                    "shap_value": round(shap_val, 4),
                    "direction": direction,
                    "interpretation": interp,
                }
            )

        return {
            "base_value": round(base_value, 4),
            "features": features,
        }
    except Exception as e:
        print(f"Erreur SHAP: {e}")
        return None
