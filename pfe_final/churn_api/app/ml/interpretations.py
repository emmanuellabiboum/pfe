# =============================================================================
# app/ml/interpretations.py — Phrases métier pour les explications SHAP
# PFE — Prédiction du Churn — Tunisie Télécom Agence Kairouan
# =============================================================================
#
# JUSTIFICATION :
# SHAP retourne une valeur numérique brute (par ex. shap=+0.12) qui n'est pas
# parlante pour un conseiller commercial. Ce fichier traduit chaque feature
# en phrase métier compréhensible : "Ancienneté faible → risque de départ".
#
# Stocké dans un fichier dédié pour faciliter la maintenance par l'équipe
# métier (un commercial peut éditer ce fichier sans toucher au code ML).

from typing import Dict


# =============================================================================
# DICTIONNAIRE DES INTERPRÉTATIONS MÉTIER
# =============================================================================
# Pour chaque feature, deux interprétations :
#   - vers_churn    : ce que ça signifie quand SHAP > 0 (pousse vers le départ)
#   - vers_fidelite : ce que ça signifie quand SHAP < 0 (pousse vers la fidélité)
#
# Ces phrases s'affichent dans l'interface React à côté de chaque barre du
# waterfall chart pour expliquer la décision au conseiller.

INTERPRETATIONS: Dict[str, Dict[str, str]] = {
    "tenure_mois": {
        "vers_churn"   : "Ancienneté faible → risque de départ élevé",
        "vers_fidelite": "Ancienneté élevée → client fidélisé",
    },
    "nb_evenements_total": {
        "vers_churn"   : "Faible activité réseau → désengagement",
        "vers_fidelite": "Activité élevée → client engagé",
    },
    "facture_moyenne_mensuelle": {
        "vers_churn"   : "Facture aux extrêmes → insatisfaction tarifaire",
        "vers_fidelite": "Facture équilibrée → bon rapport qualité/prix",
    },
    "duree_appel_moyenne_sec": {
        "vers_churn"   : "Appels courts → usage voix superficiel",
        "vers_fidelite": "Appels longs → usage voix intensif",
    },
    "data_moyenne_gb": {
        "vers_churn"   : "Faible consommation data → sous-utilisation",
        "vers_fidelite": "Forte consommation data → client data intensif",
    },
    "recence_session_jours": {
        "vers_churn"   : "Longue inactivité data → abandon progressif",
        "vers_fidelite": "Session data récente → client actif",
    },
    "duree_session_moyenne_sec": {
        "vers_churn"   : "Sessions courtes → qualité réseau insuffisante",
        "vers_fidelite": "Sessions longues → bonne qualité de connexion",
    },
    "taux_cookies": {
        "vers_churn"   : "Engagement digital élevé → exposition concurrence",
        "vers_fidelite": "Engagement digital modéré → profil stable",
    },
    "nb_sessions": {
        "vers_churn"   : "Peu de sessions → client sous-engagé",
        "vers_fidelite": "Nombreuses sessions → client très actif",
    },
    "ratio_sms_appels": {
        "vers_churn"   : "Usage SMS dominant → migration vers messageries",
        "vers_fidelite": "Usage voix dominant → attachement au réseau",
    },
    "qualite_signal_dominante": {
        "vers_churn"   : "Signal faible → insatisfaction réseau",
        "vers_fidelite": "Signal excellent → satisfaction réseau",
    },
    "satisfaction_client": {
        "vers_churn"   : "Satisfaction basse → risque de résiliation",
        "vers_fidelite": "Satisfaction élevée → client satisfait",
    },
    "score_frustration": {
        "vers_churn"   : "Frustration élevée → client mécontent",
        "vers_fidelite": "Faible frustration → client serein",
    },
    "score_qualite_zone": {
        "vers_churn"   : "Zone à faible qualité → mauvaise expérience",
        "vers_fidelite": "Zone à forte qualité → bonne expérience",
    },
    "ratio_data_voix": {
        "vers_churn"   : "Ratio data/voix déséquilibré → besoin d'offre adaptée",
        "vers_fidelite": "Ratio data/voix équilibré → offre bien calibrée",
    },
    "tendance_data_pct": {
        "vers_churn"   : "Consommation data en baisse → désengagement",
        "vers_fidelite": "Consommation data en hausse → adoption croissante",
    },
    "consentement_marketing": {
        "vers_churn"   : "Pas de consentement marketing → client distant",
        "vers_fidelite": "Consentement marketing → client réceptif",
    },
    "optout_marketing": {
        "vers_churn"   : "Opt-out marketing → rejet de la communication",
        "vers_fidelite": "Pas d'opt-out → ouvert aux offres",
    },
    "flag_offre_data": {
        "vers_churn"   : "Pas d'offre data → besoins non couverts",
        "vers_fidelite": "Offre data active → besoins couverts",
    },
    "flag_offre_voix": {
        "vers_churn"   : "Pas d'offre voix → besoins non couverts",
        "vers_fidelite": "Offre voix active → besoins couverts",
    },
}


def get_interpretation(feature: str, direction: str) -> str:
    """
    Retourne l'interprétation métier d'une feature dans une direction donnée.

    Args:
        feature   : nom de la feature (ex: 'tenure_mois')
        direction : 'vers_churn' ou 'vers_fidelite'

    Returns:
        Phrase d'interprétation, ou un fallback générique si la feature
        n'a pas d'interprétation dédiée (ex: colonnes OHE techniques).

    Pourquoi un fallback :
      Les colonnes OHE comme `genre_client_Homme`, `zone_reseau_principale_URBAIN`
      n'ont pas d'interprétation métier dans le dictionnaire. Plutôt que de
      planter, on retourne un message générique pour que l'API continue de
      fonctionner même si une nouvelle feature apparaît.
    """
    interp_dict = INTERPRETATIONS.get(feature)
    if interp_dict is None:
        # Fallback générique — utilisé pour les colonnes OHE et nouvelles features
        if direction == "vers_churn":
            return f"Cette caractéristique pousse vers le churn"
        else:
            return f"Cette caractéristique pousse vers la fidélité"

    return interp_dict.get(direction, feature)