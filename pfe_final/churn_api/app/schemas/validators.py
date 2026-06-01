from typing import Any, Dict, List, Optional

MAPPING_PLAN_FLAGS: Dict[str, Dict[str, int]] = {
    "Forfait Illimite":     {"flag_offre_data": 1, "flag_offre_voix": 0},
    "Offre Classique":      {"flag_offre_data": 0, "flag_offre_voix": 1},
    "Forfait_Mobile_Mixte": {"flag_offre_data": 1, "flag_offre_voix": 1},
}

def valider_flag_data_vs_usage(data: Dict[str, Any]) -> Optional[str]:
    """
    Si flag_offre_data=0, alors le client ne peut PAS avoir d'usage data.

    Cette règle est STRICTE car elle est respectée à 100% dans le dataset
    (0 anomalie sur 300 obs). Tout cas qui la viole serait une saisie
    erronée que l'API doit rejeter.

    Champs concernés :
      - data_moyenne_gb            (strict : doit être 0)
      - nb_sessions                (strict : doit être 0)
      - duree_session_moyenne_sec  (strict : doit être 0)
      - tendance_data_pct          (tolérant : None, 0 ou négatif accepté)
      - ratio_data_voix            (tolérant : None ou 0 accepté)
    """
    if data.get("flag_offre_data") != 0:
        return None

    incoherences = []
    cols_strictes = ["data_moyenne_gb", "nb_sessions", "duree_session_moyenne_sec"]

    for col in cols_strictes:
        valeur = data.get(col)
        if valeur is not None and valeur > 0:
            incoherences.append(f"{col}={valeur}")

    if incoherences:
        return (
            f"Incohérence : flag_offre_data=0 mais usage data détecté "
            f"({', '.join(incoherences)}). Si le client n'a pas d'offre data, "
            f"sa consommation data doit être nulle."
        )
    return None


def valider_flag_voix_vs_usage(data: Dict[str, Any]) -> Optional[str]:
    """
    Si flag_offre_voix=0, alors le client ne peut PAS avoir d'usage voix.

    Champs concernés :
      - duree_appel_moyenne_sec    (strict : doit être 0)
      - ratio_sms_appels           (strict : doit être 0)
    """
    if data.get("flag_offre_voix") != 0:
        return None

    incoherences = []
    for col in ["duree_appel_moyenne_sec", "ratio_sms_appels"]:
        valeur = data.get(col)
        if valeur is not None and valeur > 0:
            incoherences.append(f"{col}={valeur}")

    if incoherences:
        return (
            f"Incohérence : flag_offre_voix=0 mais usage voix détecté "
            f"({', '.join(incoherences)}). Si le client n'a pas d'offre voix, "
            f"son usage voix doit être nul."
        )
    return None


def valider_flags_manquantes(data: Dict[str, Any]) -> Optional[str]:
    """
    Si *_manquante=1, alors la valeur correspondante doit être None.

    Règles strictes :
      - satisfaction_manquante=1 → satisfaction_client doit être None
    """
    if (data.get("satisfaction_manquante") == 1
        and data.get("satisfaction_client") is not None):
        return (
            f"Incohérence : satisfaction_manquante=1 mais satisfaction_client="
            f"{data.get('satisfaction_client')}. Si le flag indique une donnée "
            f"manquante, la valeur doit être null."
        )
    return None


def detecter_warning_plan_vs_flags(data: Dict[str, Any]) -> Optional[str]:
    """
    Vérifie que le plan tarifaire correspond au mapping standard.

    POURQUOI WARNING ET PAS ERREUR :
      Le dataset original (300 obs) contient 18 cas (6%) qui ne respectent
      pas le mapping standard, par exemple :
        - 14 clients "Offre Classique" avec flag_data=0, flag_voix=0
          (probablement des comptes inactifs/suspendus)
        - 3 clients "Forfait_Mobile_Mixte" avec flag_data=0, flag_voix=1
        - 1 client "Forfait_Mobile_Mixte" avec flag_data=1, flag_voix=0

      Ces cas étant présents dans le train set, le modèle a appris à les
      gérer. Rejeter ces inputs en API serait incohérent : on rejetterait
      des clients que le modèle traite en réalité parfaitement.

      → On préfère SIGNALER ces cas (transparence) sans bloquer.
    """
    plan = data.get("plan_tarifaire")
    flag_data = data.get("flag_offre_data")
    flag_voix = data.get("flag_offre_voix")

    if plan not in MAPPING_PLAN_FLAGS:
        return None  # plan inconnu → géré par l'Enum Pydantic

    attendu = MAPPING_PLAN_FLAGS[plan]
    if flag_data != attendu["flag_offre_data"] or flag_voix != attendu["flag_offre_voix"]:
        return (
            f"Cas atypique : plan '{plan}' attend habituellement "
            f"flag_data={attendu['flag_offre_data']}, "
            f"flag_voix={attendu['flag_offre_voix']}, "
            f"mais reçu flag_data={flag_data}, flag_voix={flag_voix}. "
            f"Le modèle gère ce cas (présent dans le train set) mais "
            f"vérifier l'exactitude des données."
        )
    return None


def detecter_warning_marketing(data: Dict[str, Any]) -> Optional[str]:
    """
    Détecte les configurations marketing étranges sans bloquer la requête.

    POURQUOI WARNING ET PAS ERREUR :
      31 clients du dataset (10%) ont consentement_marketing=True ET
      optout_marketing=True simultanément. C'est cohérent avec un parcours
      RGPD réel : le client a consenti, puis s'est rétracté.
    """
    consent = data.get("consentement_marketing")
    optout  = data.get("optout_marketing")

    if consent is True and optout is True:
        return (
            "Cas atypique : consentement_marketing=True ET "
            "optout_marketing=True simultanément. Probablement un "
            "consentement initialement donné puis retiré (parcours RGPD)."
        )
    return None


def valider_coherence_metier(data: Dict[str, Any]) -> List[str]:
    """
    Exécute les validateurs STRICTS et retourne la liste des erreurs.

    Args:
        data : dict des features brutes du client (issu de Pydantic)

    Returns:
        Liste vide si OK, sinon liste des messages d'erreur (→ 422 HTTP).
    """
    erreurs = []
    for validateur in [
        valider_flag_data_vs_usage,
        valider_flag_voix_vs_usage,
        valider_flags_manquantes,
    ]:
        erreur = validateur(data)
        if erreur:
            erreurs.append(erreur)
    return erreurs


def detecter_warnings(data: Dict[str, Any]) -> List[str]:
    """
    Exécute les validateurs NON BLOQUANTS et retourne la liste des warnings.

    Returns:
        Liste vide si tout standard, sinon liste de warnings informatifs.
    """
    warnings = []
    for validateur in [
        detecter_warning_plan_vs_flags,
        detecter_warning_marketing,
    ]:
        warning = validateur(data)
        if warning:
            warnings.append(warning)
    return warnings