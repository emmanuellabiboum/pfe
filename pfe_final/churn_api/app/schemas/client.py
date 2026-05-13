# =============================================================================
# app/schemas/client.py — Schéma d'entrée pour /api/predict
# PFE — Prédiction du Churn — Tunisie Télécom Agence Kairouan
# =============================================================================
#
# VERSION ÉTAPE 8 — Validateurs métier croisés + bornes calibrées sur le
# dataset réel (cf. tests_manuels/diagnostic_dataset.py).
#
# DIFFÉRENCES VS ÉTAPE 2 :
#   - Bornes élargies pour matcher les valeurs réellement observées
#     (sinon on rejetterait des données légitimes)
#   - Ajout du @model_validator pour validation croisée stricte
#   - Stockage des warnings dans _warnings (privé)

from pydantic import BaseModel, Field, model_validator
from typing   import Optional
from enum     import Enum

from app.schemas.validators import (
    valider_coherence_metier,
    detecter_warnings,
)


# =============================================================================
# ENUMS — Modalités catégorielles (post-nettoyage)
# =============================================================================
# Ces valeurs correspondent aux modalités APRÈS nettoyage NFD + underscores.
# Le dataset original contient des accents et parenthèses, mais le notebook
# les nettoie avant get_dummies. L'API utilise les modalités nettoyées comme
# format d'entrée canonique.

class GenreClient(str, Enum):
    femme = "Femme"
    homme = "Homme"


class TypeAbonnement(str, Enum):
    """Sans accents (post-nettoyage NFD)."""
    prepayee = "Offre Prepayee"
    facture  = "Offre a Facture"


class PlanTarifaire(str, Enum):
    """Sans accents, parenthèses → underscores."""
    illimite  = "Forfait Illimite"
    mixte     = "Forfait_Mobile_Mixte"
    classique = "Offre Classique"


class MoyenPaiement(str, Enum):
    especes              = "especes"
    prelevement_bancaire = "prelevement_bancaire"
    ticket_recharge      = "ticket_recharge"


class ZoneReseau(str, Enum):
    rural     = "RURAL"
    suburbain = "SUBURBAIN"
    urbain    = "URBAIN"


class QualiteSignal(str, Enum):
    faible    = "Faible"
    bon       = "Bon"
    excellent = "Excellent"


# =============================================================================
# SCHÉMA D'ENTRÉE — Bornes calibrées sur le dataset réel
# =============================================================================

class ClientFeatures(BaseModel):
    """
    Features brutes d'un client. Bornes calibrées sur le dataset (300 obs)
    et validées par diagnostic métier.

    Validation croisée stricte (rejet 422) :
      - flag_offre_data=0 → usage data nul
      - flag_offre_voix=0 → usage voix nul
      - satisfaction_manquante=1 → satisfaction_client null

    Validation croisée tolérante (warnings dans _warnings) :
      - plan_tarifaire ↔ flags non standard (6% des cas du dataset)
      - consentement + optout simultanés (10% des cas du dataset)
    """

    # ── Variables catégorielles (obligatoires) ──────────────────────────────
    genre_client             : GenreClient   = Field(..., description="Genre du client")
    type_abonnement          : TypeAbonnement = Field(..., description="Type d'abonnement")
    plan_tarifaire           : PlanTarifaire = Field(..., description="Plan tarifaire")
    moyen_paiement           : MoyenPaiement = Field(..., description="Moyen de paiement")
    zone_reseau_principale   : ZoneReseau    = Field(..., description="Zone réseau")
    qualite_signal_dominante : QualiteSignal = Field(..., description="Qualité signal")

    # ── Numériques obligatoires — bornes raisonnables ───────────────────────
    tenure_mois              : int   = Field(..., ge=0, le=600,
                                             description="Ancienneté en mois (0-600)")
    duree_appel_moyenne_sec  : float = Field(..., ge=0, le=3600,
                                             description="Durée moyenne appels (sec, 0-3600)")
    data_moyenne_gb          : float = Field(..., ge=0, le=1000,
                                             description="Conso data (Go, 0-1000)")
    nb_evenements_total      : int   = Field(..., ge=0, le=100000,
                                             description="Nb événements réseau")
    nb_sessions              : int   = Field(..., ge=0, le=10000,
                                             description="Nb sessions data")
    duree_session_moyenne_sec: float = Field(..., ge=0, le=86400,
                                             description="Durée moyenne session (sec)")
    taux_cookies             : float = Field(..., ge=0.0, le=1.0,
                                             description="Taux cookies (0-1)")
    recence_session_jours    : int   = Field(..., ge=0, le=3650,
                                             description="Jours depuis dernière session")
    ratio_sms_appels         : float = Field(..., ge=0, le=100,
                                             description="Ratio SMS / appels")
    # [Étape 8] Borne ÉLARGIE : observé 1-9 dans le dataset, on garde 0-15
    score_qualite_zone       : float = Field(..., ge=0, le=15,
                                             description="Score qualité zone (0-15, observé 1-9)")
    flag_offre_data          : int   = Field(..., ge=0, le=1)
    flag_offre_voix          : int   = Field(..., ge=0, le=1)

    # ── Booléens ────────────────────────────────────────────────────────────
    consentement_marketing   : bool  = Field(...)
    optout_marketing         : bool  = Field(...)

    # ── Flags de données manquantes ─────────────────────────────────────────
    data_manquante           : int   = Field(0, ge=0, le=1)
    satisfaction_manquante   : int   = Field(0, ge=0, le=1)
    reclamation_manquante    : int   = Field(0, ge=0, le=1)

    # ── Optionnels — bornes ÉLARGIES pour matcher le dataset réel ───────────
    facture_moyenne_mensuelle: Optional[float] = Field(
        None, ge=0, le=10000,
        description="Facture moyenne (DT)"
    )
    satisfaction_client      : Optional[float] = Field(
        None, ge=1, le=5,
        description="Satisfaction (1-5)"
    )
    # [Étape 8] Borne ÉLARGIE : observé -93 à 200 dans le dataset
    tendance_data_pct        : Optional[float] = Field(
        None, ge=-150, le=300,
        description="Tendance data en % (observé -93 à 200, marge -150 à 300)"
    )
    # [Étape 8] Borne ÉLARGIE : observé 0 à 10257 dans le dataset
    ratio_data_voix          : Optional[float] = Field(
        None, ge=0, le=15000,
        description="Ratio data/voix (observé 0 à 10257, marge 0 à 15000)"
    )
    # [Étape 8] Borne ÉLARGIE : observé 0 à 65 dans le dataset
    score_frustration        : Optional[float] = Field(
        None, ge=0, le=100,
        description="Score frustration (observé 0 à 65, marge 0 à 100)"
    )

    # =========================================================================
    # VALIDATEUR MÉTIER CROISÉ
    # =========================================================================

    @model_validator(mode="after")
    def valider_coherence_globale(self) -> "ClientFeatures":
        """
        Validation croisée APRÈS validation des champs individuels.

        - Validateurs STRICTS → ValueError → HTTP 422
        - Validateurs NON BLOQUANTS → stockés dans self._warnings
        """
        data = self.model_dump()

        # ── Validateurs stricts ─────────────────────────────────────────────
        erreurs = valider_coherence_metier(data)
        if erreurs:
            raise ValueError(" | ".join(erreurs))

        # ── Warnings non bloquants ──────────────────────────────────────────
        warnings = detecter_warnings(data)
        # On utilise object.__setattr__ pour stocker un attribut privé
        # sans qu'il apparaisse dans le schéma OpenAPI
        object.__setattr__(self, "_warnings", warnings)

        return self

    # ── Configuration Pydantic ──────────────────────────────────────────────
    model_config = {
        "use_enum_values": True,
        "extra": "ignore",
        "json_schema_extra": {
            "example": {
                "genre_client": "Homme",
                "type_abonnement": "Offre Prepayee",
                "plan_tarifaire": "Forfait_Mobile_Mixte",
                "moyen_paiement": "ticket_recharge",
                "zone_reseau_principale": "URBAIN",
                "qualite_signal_dominante": "Bon",
                "tenure_mois": 24,
                "duree_appel_moyenne_sec": 180.5,
                "data_moyenne_gb": 5.2,
                "nb_evenements_total": 450,
                "nb_sessions": 120,
                "duree_session_moyenne_sec": 240.0,
                "taux_cookies": 0.65,
                "recence_session_jours": 3,
                "ratio_sms_appels": 0.4,
                "score_qualite_zone": 6.0,
                "flag_offre_data": 1,
                "flag_offre_voix": 1,
                "consentement_marketing": True,
                "optout_marketing": False,
                "data_manquante": 0,
                "satisfaction_manquante": 0,
                "reclamation_manquante": 0,
                "facture_moyenne_mensuelle": 22.5,
                "satisfaction_client": 4.0,
                "tendance_data_pct": 5.0,
                "ratio_data_voix": 1.2,
                "score_frustration": 0.1
            }
        }
    }