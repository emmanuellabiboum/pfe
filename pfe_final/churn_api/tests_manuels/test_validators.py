# =============================================================================
# tests_manuels/test_validators.py
# Tests des validateurs métier (Étape 8.1)
# =============================================================================

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from pydantic import ValidationError
from app.schemas import ClientFeatures


def client_valide_de_base() -> dict:
    """Forfait Mixte cohérent — devrait passer sans warning."""
    return {
        "genre_client"             : "Homme",
        "type_abonnement"          : "Offre Prepayee",
        "plan_tarifaire"           : "Forfait_Mobile_Mixte",
        "moyen_paiement"           : "ticket_recharge",
        "zone_reseau_principale"   : "URBAIN",
        "qualite_signal_dominante" : "Bon",
        "tenure_mois"              : 24,
        "duree_appel_moyenne_sec"  : 180.5,
        "data_moyenne_gb"          : 5.2,
        "nb_evenements_total"      : 450,
        "nb_sessions"              : 120,
        "duree_session_moyenne_sec": 240.0,
        "taux_cookies"             : 0.65,
        "recence_session_jours"    : 3,
        "ratio_sms_appels"         : 0.4,
        "score_qualite_zone"       : 6.0,
        "flag_offre_data"          : 1,
        "flag_offre_voix"          : 1,
        "consentement_marketing"   : True,
        "optout_marketing"         : False,
    }


def test_passe(nom: str, data: dict, warnings_attendus: int = 0) -> None:
    print(f"\n--- {nom} ---")
    try:
        client = ClientFeatures(**data)
        warnings = getattr(client, "_warnings", [])
        if len(warnings) == warnings_attendus:
            statut = "✓ ACCEPTE"
            if warnings:
                print(f"  {statut} avec {len(warnings)} warning(s) (attendu)")
                for w in warnings:
                    print(f"      ⚠ {w[:120]}...")
            else:
                print(f"  {statut} (aucun warning, attendu)")
        else:
            print(f"  ⚠ ACCEPTE mais {len(warnings)} warnings (attendu {warnings_attendus})")
            for w in warnings:
                print(f"      ⚠ {w[:120]}...")
    except ValidationError as e:
        print(f"  ✗ REJETE (inattendu) :")
        for err in e.errors():
            print(f"      - {err.get('msg', err)[:200]}")


def test_doit_rejeter(nom: str, data: dict) -> None:
    print(f"\n--- {nom} ---")
    try:
        ClientFeatures(**data)
        print(f"  ✗ BUG : la donnée incohérente a été ACCEPTEE !")
    except ValidationError as e:
        print(f"  ✓ REJETE comme prévu :")
        for err in e.errors():
            msg = str(err.get("msg", err))
            print(f"      - {msg[:200]}")


# =============================================================================
# CAS QUI DOIVENT PASSER
# =============================================================================
print("=" * 70)
print("  TESTS QUI DOIVENT PASSER")
print("=" * 70)

# Cas 1 : Forfait Mixte standard
test_passe("Forfait Mixte standard", client_valide_de_base())

# Cas 2 : Forfait Illimite cohérent
illimite = client_valide_de_base()
illimite.update({
    "plan_tarifaire": "Forfait Illimite",
    "flag_offre_data": 1,
    "flag_offre_voix": 0,
    "duree_appel_moyenne_sec": 0,
    "ratio_sms_appels": 0,
})
test_passe("Forfait Illimite (data only)", illimite)

# Cas 3 : Offre Classique cohérente
classique = client_valide_de_base()
classique.update({
    "plan_tarifaire": "Offre Classique",
    "flag_offre_data": 0,
    "flag_offre_voix": 1,
    "data_moyenne_gb": 0,
    "nb_sessions": 0,
    "duree_session_moyenne_sec": 0,
})
test_passe("Offre Classique (voix only)", classique)

# Cas 4 : Cas atypique du dataset (Offre Classique sans data ni voix)
atypique_1 = client_valide_de_base()
atypique_1.update({
    "plan_tarifaire": "Offre Classique",
    "flag_offre_data": 0,
    "flag_offre_voix": 0,
    "data_moyenne_gb": 0,
    "nb_sessions": 0,
    "duree_session_moyenne_sec": 0,
    "duree_appel_moyenne_sec": 0,
    "ratio_sms_appels": 0,
})
test_passe(
    "Cas ATYPIQUE du dataset (Classique sans rien)",
    atypique_1,
    warnings_attendus=1,  # warning attendu sur plan/flags
)

# Cas 5 : Marketing consent + optout (atypique du dataset)
marketing_atypique = client_valide_de_base()
marketing_atypique["optout_marketing"] = True
test_passe(
    "Marketing consent + optout (atypique)",
    marketing_atypique,
    warnings_attendus=1,
)


# =============================================================================
# CAS QUI DOIVENT ETRE REJETES
# =============================================================================
print("\n" + "=" * 70)
print("  TESTS QUI DOIVENT ETRE REJETES")
print("=" * 70)

# Rejet 1 : flag_data=0 mais data > 0 (règle stricte du dataset)
rejet_1 = client_valide_de_base()
rejet_1.update({
    "plan_tarifaire": "Offre Classique",
    "flag_offre_data": 0,
    "flag_offre_voix": 1,
    "data_moyenne_gb": 5.0,  # ❌ usage data sans offre
})
test_doit_rejeter("flag_data=0 mais data_moyenne_gb=5", rejet_1)

# Rejet 2 : flag_voix=0 mais duree_appel > 0
rejet_2 = client_valide_de_base()
rejet_2.update({
    "plan_tarifaire": "Forfait Illimite",
    "flag_offre_data": 1,
    "flag_offre_voix": 0,
    "duree_appel_moyenne_sec": 100,  # ❌ usage voix sans offre
    "ratio_sms_appels": 0,
})
test_doit_rejeter("flag_voix=0 mais duree_appel=100", rejet_2)

# Rejet 3 : satisfaction_manquante=1 + valeur renseignée
rejet_3 = client_valide_de_base()
rejet_3.update({
    "satisfaction_manquante": 1,
    "satisfaction_client"   : 4.0,  # ❌ contradictoire
})
test_doit_rejeter("satisfaction_manquante=1 + valeur=4", rejet_3)

# Rejet 4 : score hors borne
rejet_4 = client_valide_de_base()
rejet_4["score_frustration"] = 999  # ❌ borne le=100
test_doit_rejeter("score_frustration=999 (hors borne 0-100)", rejet_4)

# Rejet 5 : ton bug original
rejet_5 = {
    "consentement_marketing": True, "data_manquante": 0,
    "data_moyenne_gb": 5.2, "duree_appel_moyenne_sec": 180.5,
    "duree_session_moyenne_sec": 240, "facture_moyenne_mensuelle": 22.5,
    "flag_offre_data": 1, "flag_offre_voix": 1,
    "genre_client": "Homme", "moyen_paiement": "ticket_recharge",
    "nb_evenements_total": 450, "nb_sessions": 120,
    "optout_marketing": False, "plan_tarifaire": "Forfait Illimite",
    "qualite_signal_dominante": "Bon", "ratio_data_voix": 1.2,
    "ratio_sms_appels": 0.4, "recence_session_jours": 3,
    "reclamation_manquante": 0, "satisfaction_client": 4,
    "satisfaction_manquante": 0, "score_frustration": 0.1,
    "score_qualite_zone": 6.0, "taux_cookies": 0.65,
    "tendance_data_pct": 5, "tenure_mois": 24,
    "type_abonnement": "Offre Prepayee", "zone_reseau_principale": "URBAIN",
}
# Note : ce cas devrait passer avec WARNING (Forfait Illimite + flag_voix=1
# est un cas atypique mais pas une incohérence stricte). Pour le rejeter,
# il faudrait ajouter usage voix > 0, ce que la donnée fait déjà :
# duree_appel_moyenne_sec=180.5 alors que flag_voix=1 → mais ça reste cohérent
# car flag_voix=1 autorise l'usage voix. Donc ce cas devrait PASSER avec warning.
print("\n--- Le 'bug original' que tu avais identifié ---")
print("    NOTE : avec la nouvelle politique, ce cas est ACCEPTE avec warning")
print("    car le plan Illimite + flag_voix=1 est atypique mais pas absurde")
print("    (le client a un Illimité ET un usage voix → cas du dataset).")
test_passe(
    "Bug original (Forfait Illimite + flag_voix=1)",
    rejet_5,
    warnings_attendus=1,  # warning sur plan/flags
)


print("\n" + "=" * 70)
print("  FIN DES TESTS")
print("=" * 70)