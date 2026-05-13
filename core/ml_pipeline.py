import json
from pathlib import Path

import numpy as np
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent
MODELS_DIR = BASE_DIR / "pfe_final" / "churn_api" / "fastapi_artifacts"
PARAMS_PATH = MODELS_DIR / "preprocessing_params.json"


def _load_preprocessing_params():
    try:
        with open(PARAMS_PATH, "r", encoding="utf-8") as f:
            params = json.load(f)
        return (
            params["feature_names_ordered"],
            params["imputation_stats"],
            params["ordinal_mapping"],
            params["ohe_columns"],
            params["ohe_col_abonnement"],
        )
    except (FileNotFoundError, KeyError):
        # Valeurs par défaut si le fichier n'existe pas
        return (
            [],  # FEATURE_NAMES_ORDERED
            {},  # IMPUTATION_STATS
            {},  # ORDINAL_MAPPING
            [],  # OHE_COLUMNS
            "",  # OHE_COL_ABONNEMENT
        )


(
    FEATURE_NAMES_ORDERED,
    IMPUTATION_STATS,
    ORDINAL_MAPPING,
    OHE_COLUMNS,
    OHE_COL_ABONNEMENT,
) = _load_preprocessing_params()


def pretraiter_client(client_data):
    """Prétraite un client individuel vers le format ML du modèle."""
    if hasattr(client_data, "model_dump"):
        data = client_data.model_dump()
    elif hasattr(client_data, "__dict__"):
        data = vars(client_data).copy()
    elif isinstance(client_data, dict):
        data = client_data.copy()
    else:
        raise TypeError("Le client doit être un dict ou un objet Pydantic / dataclass")

    data["consentement_marketing"] = int(data.get("consentement_marketing", 0))
    data["optout_marketing"] = int(data.get("optout_marketing", 0))

    data["qualite_signal_dominante"] = ORDINAL_MAPPING["qualite_signal_dominante"].get(
        data.get("qualite_signal_dominante"), 0
    )

    for col in OHE_COLUMNS:
        data[col] = 0

    ohe_mappings = {
        "genre_client": {
            "Homme": "genre_client_Homme",
        },
        "type_abonnement": {
            "Offre Prépayée": "type_abonnement_Offre_a_Facture",
        },
        "plan_tarifaire": {
            "Forfait Mobile (Mixte)": "plan_tarifaire_Forfait_Mobile_Mixte",
            "Offre Classique": "plan_tarifaire_Offre_Classique",
        },
        "moyen_paiement": {
            "prelevement_bancaire": "moyen_paiement_prelevement_bancaire",
            "ticket_recharge": "moyen_paiement_ticket_recharge",
        },
        "zone_reseau_principale": {
            "SUBURBAIN": "zone_reseau_principale_SUBURBAIN",
            "URBAIN": "zone_reseau_principale_URBAIN",
        },
    }

    for var, mapping in ohe_mappings.items():
        col_ohe = mapping.get(data.get(var))
        if col_ohe and col_ohe in OHE_COLUMNS:
            data[col_ohe] = 1
        data.pop(var, None)

    if data.get("score_frustration") is None:
        data["score_frustration"] = 0

    if data.get("facture_moyenne_mensuelle") is None:
        stats = IMPUTATION_STATS["facture_moyenne_mensuelle"]
        data["facture_moyenne_mensuelle"] = (
            stats["mediane_prepayee"]
            if data.get(OHE_COL_ABONNEMENT, 0) == 1
            else stats["mediane_facture"]
        )

    for col in ["satisfaction_client", "tendance_data_pct", "ratio_data_voix"]:
        if data.get(col) is None:
            data[col] = IMPUTATION_STATS[col]["valeur"]

    if data.get("flag_offre_data", 0) == 0:
        data["data_moyenne_gb"] = 0
        data["nb_sessions"] = 0
        data["duree_session_moyenne_sec"] = 0
        data["tendance_data_pct"] = 0
        data["ratio_data_voix"] = 0

    if data.get("flag_offre_voix", 0) == 0:
        data["duree_appel_moyenne_sec"] = 0
        data["ratio_sms_appels"] = 0

    row = {f: data.get(f, 0) for f in FEATURE_NAMES_ORDERED}
    return pd.DataFrame([row])


def pretraiter_dataframe(df_raw: pd.DataFrame) -> pd.DataFrame:
    """Prétraite un DataFrame complet pour la prédiction de churn."""
    df = df_raw.copy()

    if "churn" in df.columns:
        df = df.drop(columns=["churn"])

    for col in ["consentement_marketing", "optout_marketing"]:
        if col in df.columns:
            df[col] = df[col].astype(float).astype(int)

    if "qualite_signal_dominante" in df.columns:
        df["qualite_signal_dominante"] = (
            df["qualite_signal_dominante"]
            .map(ORDINAL_MAPPING["qualite_signal_dominante"])
            .fillna(0)
            .astype(int)
        )

    nominal_cols = [
        "genre_client",
        "type_abonnement",
        "plan_tarifaire",
        "moyen_paiement",
        "zone_reseau_principale",
    ]
    existing_nominal = [c for c in nominal_cols if c in df.columns]
    if existing_nominal:
        df = pd.get_dummies(df, columns=existing_nominal, drop_first=True, dtype=int)

    for col in OHE_COLUMNS:
        if col not in df.columns:
            df[col] = 0

    if "score_frustration" in df.columns:
        df["score_frustration"] = df["score_frustration"].fillna(0)

    if "facture_moyenne_mensuelle" in df.columns:
        stats = IMPUTATION_STATS["facture_moyenne_mensuelle"]
        if OHE_COL_ABONNEMENT in df.columns:
            mask_p = (df[OHE_COL_ABONNEMENT] == 1) & df[
                "facture_moyenne_mensuelle"
            ].isna()
            mask_f = (df[OHE_COL_ABONNEMENT] == 0) & df[
                "facture_moyenne_mensuelle"
            ].isna()
            df.loc[mask_p, "facture_moyenne_mensuelle"] = stats["mediane_prepayee"]
            df.loc[mask_f, "facture_moyenne_mensuelle"] = stats["mediane_facture"]
        else:
            df["facture_moyenne_mensuelle"] = df["facture_moyenne_mensuelle"].fillna(
                stats["mediane_facture"]
            )

    for col in ["satisfaction_client", "tendance_data_pct", "ratio_data_voix"]:
        if col in df.columns:
            df[col] = df[col].fillna(IMPUTATION_STATS[col]["valeur"])

    for col in FEATURE_NAMES_ORDERED:
        if col not in df.columns:
            df[col] = 0

    return df[FEATURE_NAMES_ORDERED].fillna(0)
