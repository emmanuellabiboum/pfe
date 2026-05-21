import random
from datetime import datetime, timedelta

# import numpy as np  # Déplacé dans les fonctions
from core.model_config import estimate_clv


# Fonctions d'audit de qualité des données (RGS-90)
def calculer_duree_appel_moyenne(duree_totale, nb_appels):
    """
    A — Calcule la durée moyenne avec protection division par zéro.
    Si nb_appels = 0 → duree_appel_moyenne = 0 (par convention)
    """
    if nb_appels and nb_appels > 0:
        return round(duree_totale / nb_appels, 2)
    return 0


def definir_flags_offre(plan_tarifaire):
    """
    Retourne les flags structurels selon le plan tarifaire.
    """
    offres_avec_data = [
        "Forfait Mobile Mixte",
        "Forfait Illimité",
        "Confort",
        "Premium",
    ]
    offres_avec_voix = ["Offre Classique", "Forfait Mobile Mixte", "Forfait Illimité"]

    return {
        "flag_offre_data": 1 if plan_tarifaire in offres_avec_data else 0,
        "flag_offre_voix": 1 if plan_tarifaire in offres_avec_voix else 0,
    }


def definir_flags_missing(nb_reclamations, data_mois_m, data_mois_m1):
    """
    Crée les flags pour valeurs manquantes (stratégie NaN avec flags)
    """
    return {
        "reclamation_manquante": 1 if nb_reclamations is None else 0,
        "data_mois_m_manquante": 1 if data_mois_m is None else 0,
        "data_mois_m1_manquante": 1 if data_mois_m1 is None else 0,
    }


# Protection: Le mode Mock est strictement interdit en production (DEBUG=False)
# Cette vérification est faite au moment de l'exécution, pas à l'import
_mock_mode_enabled = None


def _check_mock_mode():
    """Vérifie si le mode Mock est autorisé (DEBUG=True uniquement)."""
    global _mock_mode_enabled
    if _mock_mode_enabled is None:
        try:
            from django.conf import settings

            _mock_mode_enabled = getattr(settings, "DEBUG", False)
        except Exception:
            _mock_mode_enabled = True  # Par défaut en développement
    return _mock_mode_enabled


def _ensure_mock_mode():
    """Lève une exception si le mode Mock est utilisé en production."""
    if not _check_mock_mode():
        raise RuntimeError(
            "ERREUR CRITIQUE: Le mode Mock (generer_mock_data) est désactivé en production. "
            "DEBUG=False détecté. Utilisez uniquement en environnement de développement."
        )


REGLES_RECOMMANDATIONS = [
    {
        "id": "rec_reclamations_critique",
        "condition": lambda c: c.nb_reclamations is not None and c.nb_reclamations >= 8,
        "type": "technique",
        "contenu": lambda c: (
            f"Traitement urgent des {c.nb_reclamations} réclamations en attente. "
            f"Volume critique corrélé à un risque de churn élevé."
        ),
        "priorite": 1,
    },
    {
        "id": "rec_reclamations_eleve",
        "condition": lambda c: c.nb_reclamations is not None
        and 4 <= c.nb_reclamations < 8,
        "type": "technique",
        "contenu": lambda c: (
            f"Suivi des {c.nb_reclamations} réclamations ouvertes. "
            f"Planifier un rappel de satisfaction client."
        ),
        "priorite": 2,
    },
    {
        "id": "rec_reclamation_manquante",
        "condition": lambda c: c.reclamation_manquante,
        "type": "marketing",
        "contenu": lambda c: (
            "Client jamais contacté le support (Silent Churner). "
            "Profil potentiellement désengagé — contact proactif conseillé."
        ),
        "priorite": 2,
    },
    {
        "id": "rec_retards_paiement",
        "condition": lambda c: c.retards_paiement >= 3,
        "type": "commercial",
        "contenu": lambda c: (
            f"Client avec {c.retards_paiement} retards de paiement. "
            f"Proposer un échelonnement ou une révision du forfait."
        ),
        "priorite": 1,
    },
    {
        "id": "rec_anciennete_faible",
        "condition": lambda c: c.anciennete_mois <= 6 and c.score_churn >= 0.5,
        "type": "marketing",
        "contenu": lambda c: (
            f"Client récent ({c.anciennete_mois} mois) à risque élevé. "
            f"Déclencher une campagne de fidélisation et offrir un bonus data."
        ),
        "priorite": 2,
    },
    {
        "id": "rec_consommation_faible",
        "condition": lambda c: c.consommation_moyenne < 80 and c.nb_services <= 2,
        "type": "commercial",
        "contenu": lambda c: (
            f"Faible consommation ({c.consommation_moyenne:.0f} DT/mois) "
            f"et seulement {c.nb_services} service(s) actif(s). "
            f"Proposer une offre groupée adaptée."
        ),
        "priorite": 3,
    },
    {
        "id": "rec_score_tres_eleve",
        "condition": lambda c: c.score_churn >= 0.85,
        "type": "marketing",
        "contenu": lambda c: (
            f"Score de churn critique ({c.score_churn*100:.0f}%). "
            f"Contact prioritaire : offrir une remise exceptionnelle ou un geste commercial."
        ),
        "priorite": 1,
    },
    {
        "id": "rec_multiservice_faible",
        "condition": lambda c: c.nb_services == 1 and c.anciennete_mois >= 12,
        "type": "commercial",
        "contenu": lambda c: (
            f"Client fidèle ({c.anciennete_mois} mois) mais sur un seul service. "
            f"Opportunité de cross-sell : présenter les offres convergentes."
        ),
        "priorite": 3,
    },
]

ROLE_PAR_TYPE = {
    "marketing": "agent_marketing",
    "commercial": "agent_commercial",
    "technique": "chef_agence",
}


def generer_recommandations_client(client, agence, createur=None):
    """
    Génère des recommandations pour un client.

    SECURITE: Cette fonction est bloquée en production (DEBUG=False).
    """
    # Vérification de sécurité: interdit en production
    _ensure_mock_mode()

    from dashboard.models import Recommandation, Notification
    from accounts.models import User
    from datetime import datetime

    today = datetime.now().date()
    Recommandation.objects.filter(
        client=client, generee_par_systeme=True, statut="active"
    ).delete()
    regles_matchees = sorted(
        [r for r in REGLES_RECOMMANDATIONS if r["condition"](client)],
        key=lambda r: r["priorite"],
    )
    regles_a_creer = regles_matchees[:3]
    recs_creees = []

    for regle in regles_a_creer:
        # Créer la recommandation directement active
        clv = estimate_clv(client)
        rec = Recommandation.objects.create(
            client=client,
            type_recommandation=regle["type"],
            contenu=regle["contenu"](client),
            echeance=today + timedelta(days=2),
            generee_par_systeme=True,
            clv_estimee=clv,
            statut="active",
        )
        recs_creees.append(rec)

    # Notifier directement les agents concernés
    if recs_creees:
        ROLE_PAR_TYPE = {
            "marketing": "agent_marketing",
            "commercial": "agent_commercial",
            "technique": "chef_agence",
        }
        for rec in recs_creees:
            role_cible = ROLE_PAR_TYPE.get(rec.type_recommandation)
            if role_cible:
                agents = User.objects.filter(
                    agence=agence, role=role_cible, statut="actif"
                )
                for agent in agents:
                    Notification.objects.create(
                        destinataire=agent,
                        type_notif="recommandation",
                        recommandation=rec,
                        titre=f"Nouvelle mission — {rec.get_type_recommandation_display_fr()}",
                        contenu=(
                            f"Client {rec.client.client_id} ({rec.client.nom}) : "
                            f"{rec.contenu[:100]}"
                        ),
                        lien=f"/clients/{rec.client.id}/#recommandations",
                        client=rec.client,
                    )

    return len(recs_creees)


def generer_mock_data(agence_id=None, user_id=None, nb_clients=50):
    """
    Génère des données mock pour les tests.

    SECURITE: Cette fonction est bloquée en production (DEBUG=False).
    """
    # Vérification de sécurité: interdit en production
    _ensure_mock_mode()

    # Imports des modèles Django (faits ici pour éviter les imports circulaires)
    from learning.models import ClientChurn, EvenementCDR, Dataset
    from accounts.models import User
    from core.models import Agence

    agence = (
        Agence.objects.filter(id=agence_id).first()
        if agence_id
        else Agence.objects.first()
    )
    if not agence:
        agence, _ = Agence.objects.get_or_create(
            nom="Agence Kairouan", defaults={"code": "AG-KAI", "ville": "Kairouan"}
        )
    user = (
        User.objects.filter(id=user_id).first()
        if user_id
        else User.objects.filter(is_active=True).first()
    )
    if not user:
        user, _ = User.objects.get_or_create(
            username="mock_chef",
            defaults={"email": "mock@churn.local", "is_active": True},
        )

    if user and getattr(user, "agence", None):
        agence = user.agence

    # Nettoyage — conserver les anciens datasets historiques,
    # mais marquer toutes les anciennes versions comme inactives.
    from django.db.models import Q

    Dataset.objects.filter(
        agence=agence, methode__in=["mock", "csv"], actif=True
    ).update(actif=False)

    # Créer un dataset mock pour l'agence
    dataset = Dataset.objects.create(
        nom=f"Mock dataset - {agence.nom} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        methode="mock",
        agence=agence,
        charge_par=user if user and getattr(user, "is_active", False) else None,
        nb_clients=nb_clients,
        actif=True,
    )

    # Listes de données
    prenoms = [
        "Mohamed",
        "Fatma",
        "Ali",
        "Amina",
        "Houssem",
        "Rania",
        "Karim",
        "Leila",
        "Sami",
        "Nour",
        "Youssef",
        "Mariem",
        "Amine",
        "Salma",
        "Bilel",
    ]
    noms_famille = [
        "Ben Ali",
        "Ben Salah",
        "Hamdi",
        "Trabelsi",
        "Gharbi",
        "Mansouri",
        "Jebali",
        "Mrad",
        "Chaabane",
    ]
    segments = ["Premium", "Standard", "Basic"]
    genres = ["Homme", "Femme"]
    domains_email = ["gmail.com", "outlook.fr", "yahoo.com", "tunisietelecom.tn"]
    zones_reseau = [
        "Kairouan Centre",
        "Kairouan Nord",
        "Kairouan Sud",
        "Haffouz",
        "Chebba",
    ]
    qualites_signal = ["Excellent", "Bon", "Moyen", "Faible"]

    # Distribution réaliste des scores (alignée sur les seuils FastAPI) :
    # - faible : < 0.32
    # - moyen  : 0.32–0.60
    # - élevé  : >= 0.60
    # dont quelques cas à > 0.95 pour tester la colorimétrie
    def score_realiste():
        r = random.random()
        if r < 0.30:
            return round(random.uniform(0.0, 0.32), 2)
        elif r < 0.60:
            return round(random.uniform(0.32, 0.60), 2)
        elif r < 0.90:
            return round(random.uniform(0.60, 0.94), 2)
        else:
            # Cas critiques : 0.95 à 1.00
            return round(random.uniform(0.95, 1.00), 2)

    # Helper functions pour les distributions selon le document
    def type_abonnement_realiste():
        """85% prépayé, 15% postpayé"""
        return "postpaye" if random.random() < 0.15 else "prepaye"

    def plan_tarifaire_realiste():
        """Offre Classique 70%, Mobile Mixte 20%, Illimité 10%"""
        r = random.random()
        if r < 0.70:
            return "Offre Classique"
        elif r < 0.90:
            return "Forfait Mobile Mixte"
        else:
            return "Forfait Illimité"

    def moyen_paiement_realiste(type_abonnement):
        """Recharges 75%, espèces 15%, prélèvement 10%"""
        if type_abonnement == "postpaye":
            return random.choice(["Espèces", "Prélèvement bancaire"])
        r = random.random()
        if r < 0.75:
            return "Tickets de recharge"
        elif r < 0.90:
            return "Espèces"
        else:
            return "Prélèvement bancaire"

    def facture_moyenne_realiste():
        """Bas 5-25DT 70%, intermédiaire 30-60DT 20%, premium 70-160DT 10%"""
        r = random.random()
        if r < 0.70:
            return round(random.uniform(5, 25), 2)
        elif r < 0.90:
            return round(random.uniform(30, 60), 2)
        else:
            return round(random.uniform(70, 160), 2)

    def consentement_marketing_realiste():
        """60% True, 40% False"""
        return random.random() < 0.60

    def optout_realiste(consentement):
        """20% des consentants se désinscrivent"""
        if not consentement:
            return False
        return random.random() < 0.20

    def statut_actif_realiste():
        """70% True, 30% False"""
        return random.random() < 0.70

    def satisfaction_realiste(statut_actif):
        """Score 1-5, corrélation avec statut_actif"""
        if not statut_actif:
            return random.choice([1, 2])
        return random.choice([3, 4, 5])

    def generate_cin():
        """CIN tunisienne: 0 ou 1 suivi de 7 chiffres"""
        return f"{random.randint(0, 1)}{random.randint(1000000, 9999999)}"

    def generate_date_naissance(date_souscription):
        """Générer une date de naissance pour avoir au moins 18 ans à la souscription"""
        min_age = 18
        max_age = 70
        age = random.randint(min_age, max_age)
        return date_souscription - timedelta(days=age * 365 + random.randint(0, 365))

    def generate_telephone():
        """+216 suivi de 2,4,5,9 puis 7 chiffres"""
        indicatif = random.choice([2, 4, 5, 9])
        suffix = random.randint(1000000, 9999999)
        return f"+216 {indicatif}{suffix}"

    created = []
    for i in range(nb_clients):
        score = score_realiste()

        # client_id unique et lisible
        client_id = f"TT-{agence.code}-{1000 + i}"

        # Règle métier : 10% des clients ont nb_reclamations = NaN (jamais contacté support)
        rec_manquante = random.random() < 0.10

        # Cohérence : score élevé → plus de réclamations et retards
        if score >= 0.32:
            nb_rec = random.randint(3, 15) if not rec_manquante else None
            retards = random.randint(2, 8)
            anciennete = random.randint(1, 24)
        elif score >= 0.20:
            nb_rec = random.randint(1, 6) if not rec_manquante else None
            retards = random.randint(0, 4)
            anciennete = random.randint(6, 48)
        else:
            nb_rec = random.randint(0, 3) if not rec_manquante else None
            retards = random.randint(0, 2)
            anciennete = random.randint(12, 60)

        # Règle RGS-90 : churn si recence_cdr_jours >= 90 jours
        # On génère recence_cdr_jours cohérent avec le score de churn
        if score >= 0.32:
            # Churné : inactivité >= 90 jours
            recence_cdr = random.randint(90, 365)
        else:
            # Risque faible : inactivité < 30 jours
            recence_cdr = random.randint(0, 29)

        # Données client selon les distributions du document
        genre = random.choice(genres)
        type_abo = type_abonnement_realiste()
        plan = plan_tarifaire_realiste()
        moyen_paiement = moyen_paiement_realiste(type_abo)
        statut_actif = statut_actif_realiste()
        consentement = consentement_marketing_realiste()
        optout = optout_realiste(consentement)
        satisfaction = satisfaction_realiste(statut_actif)
        cin = generate_cin()

        # Dates
        date_debut = datetime(2020, 1, 1) + timedelta(days=random.randint(0, 365 * 4))
        date_naiss = generate_date_naissance(date_debut)
        date_consent = (
            date_debut + timedelta(days=random.randint(0, 365))
            if consentement
            else None
        )

        # Calcul tenure (aligné sur tenure_mois du CSV réel)
        date_extraction = datetime(2025, 1, 1)
        tenure_days = (date_extraction - date_debut).days
        tenure_months = int(tenure_days / 30.44)
        # Aligner anciennete_mois = tenure_mois (comme le CSV réel)
        anciennete = tenure_months

        # --- APPLICATION DES RÈGLES D'AUDIT RGS-90 ---

        # A — Données CDR avec protection division par zéro
        nb_appels_gen = random.randint(0, 500)
        duree_totale_gen = random.randint(0, 10000)
        # Calcul correct de la durée moyenne (règle A)
        duree_moyenne_calculee = calculer_duree_appel_moyenne(
            duree_totale_gen, nb_appels_gen
        )

        # D — Correction incohérences plan tarifaire/data
        # Offre Classique = pas de data (structurellement nul)
        if plan == "Offre Classique":
            data_totale_mb = 0
            data_m_m = None
            data_m1_m = None
        else:
            # data_moyenne_gb du CSV -> converti en MB pour le modèle
            data_gb = round(random.uniform(0, 5), 2) if random.random() > 0.717 else 0
            data_totale_mb = data_gb * 1024
            data_m_m = random.choice([None, round(random.uniform(0, 3), 2)])
            data_m1_m = random.choice([None, round(random.uniform(0, 3), 2)])

        # F — Flags structurels pour les offres
        flags_offre = definir_flags_offre(plan)

        # C — Flags pour valeurs manquantes (stratégie NaN avec flags)
        flags_missing = definir_flags_missing(nb_rec, data_m_m, data_m1_m)

        # Calcul tendance_data_pct (aligné sur le CSV réel)
        if data_m_m is not None and data_m1_m is not None and data_m1_m != 0:
            tendance_pct = round(((data_m_m - data_m1_m) / data_m1_m) * 100, 2)
        else:
            tendance_pct = round(random.uniform(-50, 50), 2)

        # consommation_moyenne = data_totale_mb (aligné avec l'importer CSV)
        consommation_moy = data_totale_mb

        client = ClientChurn.objects.create(
            dataset=dataset,
            client_id=client_id,
            nom=f"{random.choice(prenoms)} {random.choice(noms_famille)}",
            genre_client=genre,
            date_naissance=date_naiss,
            telephone=generate_telephone(),
            email=f"client_{i}@{random.choice(domains_email)}",
            adresse_physique=f"Adresse_{i}",
            identifiant_national=cin,
            segment=random.choice(segments),
            # Dates et statut
            date_debut_abonnement=date_debut,
            statut_actif=statut_actif,
            date_consentement=date_consent,
            consentement_marketing=consentement,
            optout_marketing=optout,
            # Tenure (aligné : tenure_mois = anciennete_mois)
            tenure_jours=tenure_days,
            tenure_mois=tenure_months,
            # Profil contractuel
            type_abonnement=type_abo,
            plan_tarifaire=plan,
            facture_moyenne_mensuelle=facture_moyenne_realiste(),
            moyen_paiement=moyen_paiement,
            # Usage télécom agrégé (CDR) — Règle A: calcul correct
            nb_appels=nb_appels_gen,
            duree_appel_totale_sec=duree_totale_gen,
            duree_appel_moyenne_sec=duree_moyenne_calculee,
            sms_total=random.randint(0, 1000),
            # D — Data corrigée selon plan tarifaire (en MB, comme le modèle)
            data_totale_mb=data_totale_mb,
            nb_evenements_data_cdr=random.randint(0, 200),
            # Tendance de consommation (alignée sur tendance_data_pct du CSV)
            data_mois_M=data_m_m,
            data_mois_M1=data_m1_m,
            tendance_data=tendance_pct,
            # Engagement digital
            nb_sessions=random.randint(0, 50),
            duree_session_moyenne_sec=round(random.uniform(60, 600), 2),
            recence_session_jours=random.randint(1, 90),
            taux_cookies=round(random.uniform(0, 1), 2),
            # Qualité de service et satisfaction
            zone_reseau_principale=random.choice(zones_reseau),
            qualite_signal_dominante=random.choice(qualites_signal),
            score_qualite_zone=round(random.uniform(1, 5), 2),
            satisfaction_client=satisfaction,
            score_frustration=round(random.uniform(0, 1), 2),
            # Features ML existants
            anciennete_mois=anciennete,
            nb_reclamations=nb_rec,
            reclamation_manquante=rec_manquante,
            # consommation_moyenne alignée avec data_totale_mb (comme l'importer)
            consommation_moyenne=consommation_moy,
            retards_paiement=retards,
            nb_services=random.randint(1, 6),
            score_churn=score,
            recence_cdr_jours=recence_cdr,
            # F — Flags structurels RGS-90
            flag_offre_data=flags_offre["flag_offre_data"],
            flag_offre_voix=flags_offre["flag_offre_voix"],
            # C — Flags valeurs manquantes
            data_mois_m_manquante=flags_missing["data_mois_m_manquante"],
            data_mois_m1_manquante=flags_missing["data_mois_m1_manquante"],
        )
        created.append(client)

    # Générer les données détaillées pour chaque client
    total_events = 0
    total_interactions = 0
    total_geo = 0
    total_reclamations_hist = 0
    total_shap = 0

    for client in created:
        # Événements CDR
        total_events += generer_evenements_cdr(client)
        # Interactions digitales
        total_interactions += generer_interactions_digital(client)
        # Données géospatiales
        total_geo += generer_geolocalisation(client)
        # Réclamations historiques
        total_reclamations_hist += generer_reclamations(client)
        # Valeurs SHAP pour explicabilité
        total_shap += generer_shap_valeurs(client)

    # Générer les recommandations pour les clients à risque
    total_recs = 0
    for client in created:
        if client.churn_predit:
            total_recs += generer_recommandations_client(client, agence, createur=user)

    print(
        f"{len(created)} clients mock générés pour {agence.nom}\n"
        f"  - {total_events} événements CDR\n"
        f"  - {total_interactions} interactions digitales\n"
        f"  - {total_geo} données géospatiales\n"
        f"  - {total_reclamations_hist} réclamations historiques\n"
        f"  - {total_shap} valeurs SHAP\n"
        f"  - {total_recs} recommandations actives\n"
        f"  - Conforme audit RGS-90 (flags structurels, calculs protégés)"
    )
    return ClientChurn.objects.filter(dataset__agence=agence)


def generer_evenements_cdr(client):
    """
    Génère les événements CDR (Call Detail Records) pour un client.
    Selon le document:
    - Type: appel (40%), sms (30%), donnee_mobile (30%)
    - Volume: loi de Poisson avec λ selon plan et statut actif
    - Appels: durée ~ loi exponentielle(scale=180s)
    - Data: volume ~ loi log-normale selon plan tarifaire
    """
    import numpy as np
    from learning.models import EvenementCDR
    from datetime import datetime

    # Déterminer λ (lambda) selon le plan tarifaire et statut actif
    plan_lambda = {
        "Offre Classique": 20,
        "Forfait Mobile Mixte": 30,
        "Forfait Illimité": 45,
    }
    lambda_base = plan_lambda.get(client.plan_tarifaire, 20)

    # Si client inactif, λ réduit au cinquième
    if not client.statut_actif:
        lambda_base = lambda_base / 5

    # Nombre d'événements selon loi de Poisson
    nb_evenements = np.random.poisson(lambda_base)

    # Paramètres pour la loi log-normale de data selon le plan
    mu_data = {
        "Offre Classique": 1.5,
        "Forfait Mobile Mixte": 2.0,
        "Forfait Illimité": 2.8,
    }
    mu = mu_data.get(client.plan_tarifaire, 1.5)
    sigma = 1.0

    evenements = []
    date_debut = client.date_debut_abonnement or datetime(2020, 1, 1)
    date_extraction = datetime(2025, 1, 1)

    for _ in range(nb_evenements):
        # Horodatage aléatoire entre date_debut et date_extraction
        delta = date_extraction - date_debut
        random_seconds = random.randint(0, int(delta.total_seconds()))
        date_heure = date_debut + timedelta(seconds=random_seconds)

        # Type d'événement: appel (40%), sms (30%), donnee_mobile (30%)
        r = random.random()
        if r < 0.40:
            type_evt = "appel"
        elif r < 0.70:
            type_evt = "sms"
        else:
            type_evt = "donnee_mobile"

        # Initialiser les champs
        duree = 0
        sms = 0
        data = 0
        numero_dest = "INTERNET"

        if type_evt == "appel":
            # Durée ~ loi exponentielle(scale=180s), moyenne 3 minutes
            duree = int(np.random.exponential(scale=180))
            duree = max(1, duree)  # Au moins 1 seconde
            # Numéro destination
            indic = random.choice([2, 4, 5, 9])
            suffix = random.randint(1000000, 9999999)
            numero_dest = f"+216 {indic}{suffix}"

        elif type_evt == "sms":
            sms = 1
            indic = random.choice([2, 4, 5, 9])
            suffix = random.randint(1000000, 9999999)
            numero_dest = f"+216 {indic}{suffix}"

        elif type_evt == "donnee_mobile":
            # Volume ~ loi log-normale
            data = np.random.lognormal(mean=mu, sigma=sigma)
            data = round(float(data), 2)

        evenements.append(
            EvenementCDR(
                client=client,
                date_heure=date_heure,
                type_evenement=type_evt,
                numero_source=client.telephone,
                numero_destination=numero_dest,
                duree_appel_sec=duree,
                sms_compte=sms,
                data_mb=data,
            )
        )

    # Création en bulk pour performance
    if evenements:
        EvenementCDR.objects.bulk_create(evenements)

    return len(evenements)


def generer_interactions_digital(client):
    """
    Génère les interactions digitales du client.
    Types: connexion app/web, recharge, modif profil, etc.
    """
    from learning.models import InteractionDigital

    types_interaction = [
        "connexion_app",
        "connexion_web",
        "recharge",
        "modif_profil",
        "consultation_conso",
        "activation_option",
    ]

    # Nombre d'interactions selon statut actif
    if client.statut_actif:
        nb_interactions = random.randint(5, 30)
    else:
        nb_interactions = random.randint(0, 5)

    interactions = []
    date_debut = client.date_debut_abonnement or datetime(2020, 1, 1)
    date_extraction = datetime(2025, 1, 1)

    for _ in range(nb_interactions):
        delta = date_extraction - date_debut
        random_seconds = random.randint(0, int(delta.total_seconds()))
        date_heure = date_debut + timedelta(seconds=random_seconds)

        type_int = random.choice(types_interaction)
        duree = (
            random.randint(60, 1800)
            if type_int in ["connexion_app", "connexion_web"]
            else 0
        )
        pages = (
            random.randint(1, 10)
            if type_int in ["connexion_app", "connexion_web"]
            else 0
        )

        interactions.append(
            InteractionDigital(
                client=client,
                date_heure=date_heure,
                type_interaction=type_int,
                duree_session_sec=duree,
                pages_visitees=pages,
                cookies_acceptes=random.random() < 0.6,
                action_concluante=random.random() < 0.3,
            )
        )

    if interactions:
        InteractionDigital.objects.bulk_create(interactions)

    return len(interactions)


def generer_geolocalisation(client):
    """
    Génère les données géospatiales du client.
    """
    from learning.models import DonneeGeospatiale

    # Coordonnées pour Kairouan (approximatif)
    # Latitude: 35.67, Longitude: 10.10
    lat = 35.67 + random.uniform(-0.5, 0.5)
    lon = 10.10 + random.uniform(-0.5, 0.5)

    zones = [
        "Zone couverte 4G",
        "Zone couverte 3G",
        "Zone limite",
        "Zone faible couverture",
    ]
    qualites = ["4G", "3G", "2G", "EDGE"]

    DonneeGeospatiale.objects.create(
        client=client,
        latitude=round(lat, 6),
        longitude=round(lon, 6),
        code_postal=f"31{random.randint(100, 999):03d}",
        zone_couverture=random.choice(zones),
        qualite_reseau_local=random.choice(qualites),
        signal_dbm=random.randint(-110, -70),
        nb_antennes_proximite=random.randint(0, 5),
    )

    return 1


def generer_reclamations(client):
    """
    Génère les réclamations historiques du client.
    """
    from learning.models import Reclamation

    types_rec = {
        "technique": ["Problème de connexion", "Lenteur réseau", "Appel coupé"],
        "facturation": ["Erreur sur facture", "Frais non justifiés", "Remboursement"],
        "commercial": ["Changement d'offre", "Résiliation", "Promotion"],
        "service": ["Attente trop longue", "Conseiller incompétent"],
        "couverture": ["Pas de réseau", "Zone blanche"],
    }

    # Nombre de réclamations selon score churn
    if client.score_churn >= 0.60:
        nb_rec = random.randint(3, 8)
    elif client.score_churn >= 0.32:
        nb_rec = random.randint(1, 4)
    else:
        nb_rec = random.randint(0, 2)

    if client.reclamation_manquante:
        nb_rec = 0  # Client jamais contacté le support

    reclamations = []
    date_debut = client.date_debut_abonnement or datetime(2020, 1, 1)

    for _ in range(nb_rec):
        type_rec = random.choice(list(types_rec.keys()))
        sujet = random.choice(types_rec[type_rec])

        delta = datetime(2025, 1, 1) - date_debut
        random_days = random.randint(0, delta.days)
        date_creation = date_debut + timedelta(days=random_days)

        statut = random.choice(["ouvert", "en_cours", "resolu", "ferme"])
        date_res = None
        temps_res = None
        satisfait = None

        if statut in ["resolu", "ferme"]:
            date_res = date_creation + timedelta(hours=random.randint(1, 168))
            temps_res = int((date_res - date_creation).total_seconds() / 3600)
            satisfait = random.choice([True, False])

        reclamations.append(
            Reclamation(
                client=client,
                date_creation=date_creation,
                type_reclamation=type_rec,
                sujet=sujet,
                description=f"Description détaillée de la réclamation: {sujet}",
                statut=statut,
                date_resolution=date_res,
                temps_resolution_heures=temps_res,
                satisfait=satisfait,
            )
        )

    if reclamations:
        Reclamation.objects.bulk_create(reclamations)

    return len(reclamations)


def generer_shap_valeurs(client):
    """
    Génère des valeurs SHAP de test pour un client.
    Ces valeurs expliquent la contribution de chaque feature au score de churn.
    """
    from learning.models import ShapValeur

    # Features utilisées par le modèle ML (excluant statut_actif - RGS-90)
    features = [
        ("Anciennete", client.anciennete_mois),
        ("Reclamations", client.nb_reclamations or 0),
        ("Consommation", client.consommation_moyenne),
        ("Retards paiement", client.retards_paiement),
        ("Services", client.nb_services),
        ("Facture mensuelle", client.facture_moyenne_mensuelle),
        ("Appels", client.nb_appels),
        ("Data", client.data_totale_mb),
        ("Sessions", client.nb_sessions),
        ("Score qualite", client.score_qualite_zone),
        # Flags structurels RGS-90
        ("Flag offre data", client.flag_offre_data),
        ("Flag offre voix", client.flag_offre_voix),
    ]

    shap_values = []
    for feature_name, feature_value in features:
        # Générer une valeur SHAP cohérente avec le score de churn
        # Si score élevé, plus de valeurs positives (risque)
        # Si score faible, plus de valeurs négatives (rétention)
        base_impact = (client.score_churn - 0.5) * 2  # -1 à 1
        noise = random.uniform(-0.3, 0.3)
        valeur = base_impact * random.uniform(0.5, 1.5) + noise

        # Importance = valeur absolue (pour le tri)
        importance = abs(valeur)

        shap_values.append(
            ShapValeur(
                client=client,
                feature=feature_name,
                valeur=round(valeur, 4),
                importance=round(importance, 4),
            )
        )

    if shap_values:
        ShapValeur.objects.bulk_create(shap_values)

    return len(shap_values)
