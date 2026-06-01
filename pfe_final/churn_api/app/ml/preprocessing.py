import unicodedata
from typing import Any, Dict, List, Tuple

import numpy  as np  
import pandas as pd 

from app.schemas import ClientFeatures

# Colonnes nominales qui subissent get_dummies dans le pipeline.
# La colonne 'qualite_signal_dominante' n'en fait pas partie (encodage ordinal).
COLS_NOMINALES = [
    "genre_client",
    "type_abonnement",
    "plan_tarifaire",
    "moyen_paiement",
    "zone_reseau_principale",
]


def nettoyer_modalite(s: Any) -> Any:
    """
    Nettoie une modalité catégorielle pour matcher le format attendu par
    le modèle (post-get_dummies du notebook).

    Pipeline de nettoyage :
      1. Décomposition Unicode (NFD) → sépare les caractères de leurs accents
      2. Suppression des marqueurs combinants (les accents)
      3. Remplacement des parenthèses par rien
      4. Remplacement des espaces par underscores

    Exemples :
      "Offre Prépayée"          → "Offre_Prepayee"
      "Forfait Mobile (Mixte)"  → "Forfait_Mobile_Mixte"
      "Excellent"               → "Excellent"  (inchangé)

    NOTE IMPORTANTE :
      Pour les modalités SANS accent ni parenthèse, il y a quand même un
      remplacement espace → underscore (ex: "Offre Classique" devient
      "Offre_Classique"). C'est cohérent avec le comportement du notebook
      observé dans le diagnostic.

    Args:
        s : la chaîne à nettoyer (peut être autre chose qu'une str → renvoyée
            telle quelle pour ne pas casser sur les NaN/None)

    Returns:
        Chaîne nettoyée, ou la valeur d'origine si pas une str.
    """
    if not isinstance(s, str):
        return s

    # 1. Décomposition NFD (Normalization Form Decomposed)
    # 2. Suppression des marqueurs combinants (Mn = Mark, nonspacing)
    s_sans_accents = "".join(
        c for c in unicodedata.normalize("NFD", s)
        if unicodedata.category(c) != "Mn"
    )

    # 3-4. Parenthèses → rien, espaces → underscores
    s_clean = (
        s_sans_accents
        .replace("(", "")
        .replace(")", "")
        .replace(" ", "_")
    )

    return s_clean


def nettoyer_modalites_dataframe(df: object) -> Tuple[object, List[str]]:
    """
    Applique le nettoyage à toutes les colonnes nominales d'un DataFrame
    et retourne le DataFrame nettoyé + la liste des transformations
    effectivement appliquées (pour le log dans la réponse API).

    Args:
        df : DataFrame brut tel qu'extrait du CSV uploadé

    Returns:
        Tuple (df_nettoye, log_transformations) :
          - df_nettoye : DataFrame avec modalités canoniques
          - log_transformations : liste de strings descriptives, par ex :
              ["type_abonnement: 'Offre Prépayée' → 'Offre_Prepayee' (248 cas)",
               "plan_tarifaire: 'Forfait Mobile (Mixte)' → 'Forfait_Mobile_Mixte' (64 cas)"]

    Le log permet à l'utilisateur de l'API de voir EXACTEMENT quelles
    transformations ont été appliquées à ses données — c'est de la
    transparence essentielle pour un système ML en production.
    """
    import pandas as pd
    df_clean = df.copy()
    log: List[str] = []

    for col in COLS_NOMINALES:
        if col not in df_clean.columns:
            continue

        # Pour chaque colonne nominale, on parcourt les modalités uniques
        # et on note celles qui changent
        modalites_originales = df_clean[col].dropna().unique()

        # Compteur des transformations effectives
        transformations_col: Dict[str, Tuple[str, int]] = {}

        for modalite in modalites_originales:
            modalite_propre = nettoyer_modalite(modalite)
            if modalite != modalite_propre:
                # Compte combien de lignes utilisent cette modalité
                nb_occurrences = int((df_clean[col] == modalite).sum())
                transformations_col[modalite] = (modalite_propre, nb_occurrences)

        # Application des transformations
        if transformations_col:
            mapping = {orig: clean for orig, (clean, _) in transformations_col.items()}
            df_clean[col] = df_clean[col].replace(mapping)

            # Construction du log
            for original, (propre, nb) in transformations_col.items():
                log.append(
                    f"{col}: '{original}' → '{propre}' ({nb} cas)"
                )

    return df_clean, log


def _construire_nom_colonne_ohe(
    variable: str,
    modalite: str,
    nominal_info: Dict[str, Dict],
) -> str | None:
    """
    Reconstruit le nom de colonne OHE attendu par le modèle.

    Pour drop_first=True, pandas trie les modalités alphabétiquement et
    supprime la PREMIÈRE. Le nom de colonne suit le format :
      {variable}_{modalite_nettoyee}

    Retourne None si la modalité est la référence droppée.
    """
    info = nominal_info.get(variable)
    if not info:
        return None

    reference = info["reference"]
    if modalite == reference:
        return None

    # Nettoyage final : espaces → underscores (au cas où)
    modalite_nettoyee = modalite.replace(" ", "_")
    return f"{variable}_{modalite_nettoyee}"


def _verifier_modalite(
    variable: str,
    valeur: str,
    nominal_info: Dict[str, Dict],
) -> None:
    """Vérifie qu'une valeur fait partie des modalités connues."""
    modalites_valides = nominal_info.get(variable, {}).get("modalites", [])
    if valeur not in modalites_valides:
        raise ValueError(
            f"Modalité inconnue pour '{variable}' : '{valeur}'. "
            f"Attendu parmi : {modalites_valides}"
        )


def pretraiter_client(client: ClientFeatures, params: Dict[str, Any]):
    """
    Transforme un ClientFeatures (Pydantic) en DataFrame d'une ligne
    avec les 31 colonnes attendues par le modèle Random Forest.
    """
    import pandas as pd
    ordinal_mapping        = params["ordinal_mapping"]
    ohe_columns            = params["ohe_columns"]
    nominal_info           = params["nominal_info"]
    imputation_stats       = params["imputation_stats"]
    feature_names_ordered  = params["feature_names_ordered"]
    ohe_col_abonnement     = params["ohe_col_abonnement"]

    data = client.model_dump()

    # 1. Booléens → int
    data["consentement_marketing"] = int(data["consentement_marketing"])
    data["optout_marketing"]       = int(data["optout_marketing"])

    # 2. Ordinal
    valeur_signal = data["qualite_signal_dominante"]
    data["qualite_signal_dominante"] = ordinal_mapping["qualite_signal_dominante"].get(
        valeur_signal, 0
    )

    # 3. OHE
    for col in ohe_columns:
        data[col] = 0

    for variable in COLS_NOMINALES:
        valeur = data.get(variable)
        if valeur is None:
            continue

        _verifier_modalite(variable, valeur, nominal_info)
        nom_colonne = _construire_nom_colonne_ohe(variable, valeur, nominal_info)
        if nom_colonne and nom_colonne in ohe_columns:
            data[nom_colonne] = 1
        data.pop(variable, None)

    # 4. Imputation
    if data.get("score_frustration") is None:
        data["score_frustration"] = 0

    if data.get("facture_moyenne_mensuelle") is None:
        stats = imputation_stats["facture_moyenne_mensuelle"]
        if data.get(ohe_col_abonnement, 0) == 1:
            data["facture_moyenne_mensuelle"] = stats["mediane_facture"]
        else:
            data["facture_moyenne_mensuelle"] = stats["mediane_prepayee"]

    for col in ["satisfaction_client", "tendance_data_pct", "ratio_data_voix"]:
        if data.get(col) is None:
            data[col] = imputation_stats[col]["valeur"]

    # 5. Zéros structurels
    if data.get("flag_offre_data", 0) == 0:
        data["data_moyenne_gb"]           = 0
        data["nb_sessions"]               = 0
        data["duree_session_moyenne_sec"] = 0
        data["tendance_data_pct"]         = 0
        data["ratio_data_voix"]           = 0

    if data.get("flag_offre_voix", 0) == 0:
        data["duree_appel_moyenne_sec"] = 0
        data["ratio_sms_appels"]        = 0

    # 6. Réordonnancement
    row = {f: data.get(f, 0) for f in feature_names_ordered}
    return pd.DataFrame([row], columns=feature_names_ordered)


def pretraiter_dataframe(
    df_raw: Any,
    params: Dict[str, Any],
) -> Tuple[Any, List[str]]:
    """
    Transforme un DataFrame brut en DataFrame encodé prêt pour le modèle.

    [Étape 8.2] Cette version retourne aussi un log des transformations
    de modalités appliquées au passage. Utile pour /api/predict/batch
    et /api/analyse qui exposent ce log dans leur réponse.

    Pipeline :
      0. [Étape 8.2] Nettoyage des modalités catégorielles (NFD + parens + espaces)
      1. Suppression de la colonne cible si présente
      2. Conversion booléens → int
      3. Encodage ordinal de qualite_signal_dominante
      4. Encodage OHE vectoriel via pandas.get_dummies
      5. Imputation des NaN
      6. Application des zéros structurels
      7. Réordonnancement selon feature_names_ordered

    Args:
        df_raw : DataFrame brut (CSV uploadé, modalités possiblement avec accents)
        params : preprocessing_params chargé par le loader

    Returns:
        Tuple (df_encode, log_transformations) :
          - df_encode : DataFrame de shape (n, 31) prêt pour predict_proba
          - log_transformations : liste descriptive des nettoyages effectués

    Raises:
        ValueError : si le DataFrame est vide.
    """
    import pandas as pd
    if df_raw.empty:
        raise ValueError("Le DataFrame fourni est vide")

    ordinal_mapping        = params["ordinal_mapping"]
    ohe_columns            = params["ohe_columns"]
    imputation_stats       = params["imputation_stats"]
    feature_names_ordered  = params["feature_names_ordered"]
    ohe_col_abonnement     = params["ohe_col_abonnement"]

    df = df_raw.copy()

    # 0. Nettoyage des modalités catégorielles
    df, log_transformations = nettoyer_modalites_dataframe(df)

    # 1. Suppression de la colonne cible si présente
    if "churn" in df.columns:
        df = df.drop(columns=["churn"])

    # 2. Booléens → int
    for col in ["consentement_marketing", "optout_marketing"]:
        if col in df.columns:
            df[col] = df[col].astype(float).astype(int)

    # 3. Encodage ordinal
    if "qualite_signal_dominante" in df.columns:
        df["qualite_signal_dominante"] = (
            df["qualite_signal_dominante"]
            .map(ordinal_mapping["qualite_signal_dominante"])
            .fillna(0)
            .astype(int)
        )

    # 4. OHE vectoriel
    existing_nominal = [c for c in COLS_NOMINALES if c in df.columns]
    if existing_nominal:
        df = pd.get_dummies(df, columns=existing_nominal, drop_first=True, dtype=int)

    # Création des colonnes OHE manquantes
    for col in ohe_columns:
        if col not in df.columns:
            df[col] = 0

    # 5. Imputation
    if "score_frustration" in df.columns:
        df["score_frustration"] = df["score_frustration"].fillna(0)

    if "facture_moyenne_mensuelle" in df.columns:
        stats = imputation_stats["facture_moyenne_mensuelle"]
        if ohe_col_abonnement in df.columns:
            mask_facture  = (df[ohe_col_abonnement] == 1) & df["facture_moyenne_mensuelle"].isna()
            mask_prepayee = (df[ohe_col_abonnement] == 0) & df["facture_moyenne_mensuelle"].isna()
            df.loc[mask_facture,  "facture_moyenne_mensuelle"] = stats["mediane_facture"]
            df.loc[mask_prepayee, "facture_moyenne_mensuelle"] = stats["mediane_prepayee"]
        else:
            df["facture_moyenne_mensuelle"] = df["facture_moyenne_mensuelle"].fillna(
                stats["mediane_facture"]
            )

    for col in ["satisfaction_client", "tendance_data_pct", "ratio_data_voix"]:
        if col in df.columns:
            df[col] = df[col].fillna(imputation_stats[col]["valeur"])

    # ── 6. Zéros structurels ───────────────────────────────────────────────
    if "flag_offre_data" in df.columns:
        mask_no_data = (df["flag_offre_data"] == 0)
        cols_data = ["data_moyenne_gb", "nb_sessions", "duree_session_moyenne_sec",
                     "tendance_data_pct", "ratio_data_voix"]
        for col in cols_data:
            if col in df.columns:
                df.loc[mask_no_data, col] = 0

    if "flag_offre_voix" in df.columns:
        mask_no_voix = (df["flag_offre_voix"] == 0)
        for col in ["duree_appel_moyenne_sec", "ratio_sms_appels"]:
            if col in df.columns:
                df.loc[mask_no_voix, col] = 0

    # ── 7. Réordonnancement final ──────────────────────────────────────────
    for col in feature_names_ordered:
        if col not in df.columns:
            df[col] = 0

    df_final = df[feature_names_ordered].fillna(0)

    return df_final, log_transformations