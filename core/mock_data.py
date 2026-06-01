import random
from datetime import datetime, timedelta

# import numpy as np  # Déplacé dans les fonctions
from core.model_config import estimate_clv


# Fonctions d'audit de qualité des données (RGS-90)
def calculer_duree_appel_moyenne(duree_totale, nb_appels):
    if nb_appels and nb_appels > 0:
        return round(duree_totale / nb_appels, 2)
    return 0


def definir_flags_offre(plan_tarifaire):
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
    return {
        "reclamation_manquante": 1 if nb_reclamations is None else 0,
        "data_mois_m_manquante": 1 if data_mois_m is None else 0,
        "data_mois_m1_manquante": 1 if data_mois_m1 is None else 0,
    }


# Protection: Le mode Mock est strictement interdit en production (DEBUG=False)
# Cette vérification est faite au moment de l'exécution, pas à l'import
_mock_mode_enabled = None


def _check_mock_mode():
    global _mock_mode_enabled
    if _mock_mode_enabled is None:
        try:
            from django.conf import settings

            _mock_mode_enabled = getattr(settings, "DEBUG", False)
        except Exception:
            _mock_mode_enabled = True  # Par défaut en développement
    return _mock_mode_enabled


def _ensure_mock_mode():
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
    _ensure_mock_mode()

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

    Dataset.objects.filter(agence=agence, actif=True).update(actif=False)

    dataset = Dataset.objects.create(
        nom=f"Mock dataset - {agence.nom} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        methode="mock",
        agence=agence,
        charge_par=user if user and getattr(user, "is_active", False) else None,
        nb_clients=nb_clients,
        actif=True,
    )
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

    def score_realiste():
        r = random.random()
        if r < 0.30:
            return round(random.uniform(0.0, 0.32), 2)
        elif r < 0.60:
            return round(random.uniform(0.32, 0.60), 2)
        elif r < 0.90:
            return round(random.uniform(0.60, 0.94), 2)
        else:
            return round(random.uniform(0.95, 1.00), 2)

    def type_abonnement_realiste():
        return "postpaye" if random.random() < 0.15 else "prepaye"

    def plan_tarifaire_realiste():
        r = random.random()
        if r < 0.70:
            return "Offre Classique"
        elif r < 0.90:
            return "Forfait Mobile Mixte"
        else:
            return "Forfait Illimité"

    def moyen_paiement_realiste(type_abonnement):
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
        r = random.random()
        if r < 0.70:
            return round(random.uniform(5, 25), 2)
        elif r < 0.90:
            return round(random.uniform(30, 60), 2)
        else:
            return round(random.uniform(70, 160), 2)

    def consentement_marketing_realiste():
        return random.random() < 0.60

    def optout_realiste(consentement):
        if not consentement:
            return False
        return random.random() < 0.20

    def statut_actif_realiste():
        return random.random() < 0.70

    def satisfaction_realiste(statut_actif):
        if not statut_actif:
            return random.choice([1, 2])
        return random.choice([3, 4, 5])

    def generate_cin():
        return f"{random.randint(0, 1)}{random.randint(1000000, 9999999)}"

    def generate_date_naissance(date_souscription):
        min_age = 18
        max_age = 70
        age = random.randint(min_age, max_age)
        return date_souscription - timedelta(days=age * 365 + random.randint(0, 365))

    def generate_telephone():
        indicatif = random.choice([2, 4, 5, 9])
        suffix = random.randint(1000000, 9999999)
        return f"+216 {indicatif}{suffix}"

    created = []
    for i in range(nb_clients):
        score = score_realiste()

        client_id = f"TT-{agence.code}-{1000 + i}"

        rec_manquante = random.random() < 0.10

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

        if score >= 0.32:
            recence_cdr = random.randint(90, 365)
        else:
            recence_cdr = random.randint(0, 29)

        genre = random.choice(genres)
        type_abo = type_abonnement_realiste()
        plan = plan_tarifaire_realiste()
        moyen_paiement = moyen_paiement_realiste(type_abo)
        statut_actif = statut_actif_realiste()
        consentement = consentement_marketing_realiste()
        optout = optout_realiste(consentement)
        satisfaction = satisfaction_realiste(statut_actif)
        cin = generate_cin()

        date_debut = datetime(2020, 1, 1) + timedelta(days=random.randint(0, 365 * 4))
        date_naiss = generate_date_naissance(date_debut)
        date_consent = (
            date_debut + timedelta(days=random.randint(0, 365))
            if consentement
            else None
        )

        date_extraction = datetime(2025, 1, 1)
        tenure_days = (date_extraction - date_debut).days
        tenure_months = int(tenure_days / 30.44)
        anciennete = tenure_months

        nb_appels_gen = random.randint(0, 500)
        duree_totale_gen = random.randint(0, 10000)
        duree_moyenne_calculee = calculer_duree_appel_moyenne(
            duree_totale_gen, nb_appels_gen
        )

        if plan == "Offre Classique":
            data_totale_mb = 0
            data_m_m = None
            data_m1_m = None
        else:
            data_gb = round(random.uniform(0, 5), 2) if random.random() > 0.717 else 0
            data_totale_mb = data_gb * 1024
            data_m_m = random.choice([None, round(random.uniform(0, 3), 2)])
            data_m1_m = random.choice([None, round(random.uniform(0, 3), 2)])

        flags_offre = definir_flags_offre(plan)

        flags_missing = definir_flags_missing(nb_rec, data_m_m, data_m1_m)

        if data_m_m is not None and data_m1_m is not None and data_m1_m != 0:
            tendance_pct = round(((data_m_m - data_m1_m) / data_m1_m) * 100, 2)
        else:
            tendance_pct = round(random.uniform(-50, 50), 2)

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
            date_debut_abonnement=date_debut,
            statut_actif=statut_actif,
            date_consentement=date_consent,
            consentement_marketing=consentement,
            optout_marketing=optout,
            tenure_jours=tenure_days,
            tenure_mois=tenure_months,
            type_abonnement=type_abo,
            plan_tarifaire=plan,
            facture_moyenne_mensuelle=facture_moyenne_realiste(),
            moyen_paiement=moyen_paiement,
            nb_appels=nb_appels_gen,
            duree_appel_totale_sec=duree_totale_gen,
            duree_appel_moyenne_sec=duree_moyenne_calculee,
            sms_total=random.randint(0, 1000),
            data_totale_mb=data_totale_mb,
            nb_evenements_data_cdr=random.randint(0, 200),
            data_mois_M=data_m_m,
            data_mois_M1=data_m1_m,
            tendance_data=tendance_pct,
            nb_sessions=random.randint(0, 50),
            duree_session_moyenne_sec=round(random.uniform(60, 600), 2),
            recence_session_jours=random.randint(1, 90),
            taux_cookies=round(random.uniform(0, 1), 2),
            zone_reseau_principale=random.choice(zones_reseau),
            qualite_signal_dominante=random.choice(qualites_signal),
            score_qualite_zone=round(random.uniform(1, 5), 2),
            satisfaction_client=satisfaction,
            score_frustration=round(random.uniform(0, 1), 2),
            anciennete_mois=anciennete,
            nb_reclamations=nb_rec,
            reclamation_manquante=rec_manquante,
            consommation_moyenne=consommation_moy,
            retards_paiement=retards,
            nb_services=random.randint(1, 6),
            score_churn=score,
            recence_cdr_jours=recence_cdr,
            flag_offre_data=flags_offre["flag_offre_data"],
            flag_offre_voix=flags_offre["flag_offre_voix"],
            data_mois_m_manquante=flags_missing["data_mois_m_manquante"],
            data_mois_m1_manquante=flags_missing["data_mois_m1_manquante"],
        )
        created.append(client)

    total_events = 0
    total_interactions = 0
    total_geo = 0
    total_reclamations_hist = 0
    total_shap = 0

    from core.ml_service import predict_churn_score_from_client, get_shap_explanation

    for client in created:
        total_events += generer_evenements_cdr(client)
        total_interactions += generer_interactions_digital(client)
        total_geo += generer_geolocalisation(client)
        total_reclamations_hist += generer_reclamations(client)
        
        score = predict_churn_score_from_client(client)
        if score is not None:
            client.score_churn = round(score, 4)
            client.churn_predit = score >= 0.32
            client.save(update_fields=["score_churn", "churn_predit"])

        try:
            shap_data = get_shap_explanation(client)
            if shap_data and shap_data.get("features"):
                from learning.models import ShapValeur
                ShapValeur.objects.filter(client=client).delete()
                
                shap_objs = []
                for f in shap_data["features"]:
                    shap_objs.append(
                        ShapValeur(
                            client=client,
                            feature=f["feature"],
                            valeur=round(f["shap_value"], 4),
                            importance=abs(round(f["shap_value"], 4)),
                        )
                    )
                if shap_objs:
                    ShapValeur.objects.bulk_create(shap_objs)
                    total_shap += 1
        except Exception as e:
            print(f"Erreur SHAP Mock pour client {client.client_id}: {e}")

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
    import numpy as np
    from learning.models import EvenementCDR
    from datetime import datetime

    plan_lambda = {
        "Offre Classique": 20,
        "Forfait Mobile Mixte": 30,
        "Forfait Illimité": 45,
    }
    lambda_base = plan_lambda.get(client.plan_tarifaire, 20)

    if not client.statut_actif:
        lambda_base = lambda_base / 5

    nb_evenements = np.random.poisson(lambda_base)

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
        delta = date_extraction - date_debut
        random_seconds = random.randint(0, int(delta.total_seconds()))
        date_heure = date_debut + timedelta(seconds=random_seconds)

        r = random.random()
        if r < 0.40:
            type_evt = "appel"
        elif r < 0.70:
            type_evt = "sms"
        else:
            type_evt = "donnee_mobile"

        duree = 0
        sms = 0
        data = 0
        numero_dest = "INTERNET"

        if type_evt == "appel":
            duree = int(np.random.exponential(scale=180))
            duree = max(1, duree)
            indic = random.choice([2, 4, 5, 9])
            suffix = random.randint(1000000, 9999999)
            numero_dest = f"+216 {indic}{suffix}"

        elif type_evt == "sms":
            sms = 1
            indic = random.choice([2, 4, 5, 9])
            suffix = random.randint(1000000, 9999999)
            numero_dest = f"+216 {indic}{suffix}"

        elif type_evt == "donnee_mobile":
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

    if evenements:
        EvenementCDR.objects.bulk_create(evenements)

    return len(evenements)


def generer_interactions_digital(client):
    from learning.models import InteractionDigital

    types_interaction = [
        "connexion_app",
        "connexion_web",
        "recharge",
        "modif_profil",
        "consultation_conso",
        "activation_option",
    ]

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
    from learning.models import DonneeGeospatiale

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
    from learning.models import Reclamation

    types_rec = {
        "technique": ["Problème de connexion", "Lenteur réseau", "Appel coupé"],
        "facturation": ["Erreur sur facture", "Frais non justifiés", "Remboursement"],
        "commercial": ["Changement d'offre", "Résiliation", "Promotion"],
        "service": ["Attente trop longue", "Conseiller incompétent"],
        "couverture": ["Pas de réseau", "Zone blanche"],
    }

    if client.score_churn >= 0.60:
        nb_rec = random.randint(3, 8)
    elif client.score_churn >= 0.32:
        nb_rec = random.randint(1, 4)
    else:
        nb_rec = random.randint(0, 2)

    if client.reclamation_manquante:
        nb_rec = 0

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
    from learning.models import ShapValeur

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
        ("Flag offre data", client.flag_offre_data),
        ("Flag offre voix", client.flag_offre_voix),
    ]

    shap_values = []
    for feature_name, feature_value in features:
        base_impact = (client.score_churn - 0.5) * 2
        noise = random.uniform(-0.3, 0.3)
        valeur = base_impact * random.uniform(0.5, 1.5) + noise

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
