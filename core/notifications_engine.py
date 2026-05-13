# core/notifications_engine.py
# Moteur central : génère recommandations + notifications selon les règles métier

from django.utils import timezone
from accounts.models import User


# ── CORRESPONDANCE TYPE → RÔLE AGENT ────────────────────────────────────────
ROLE_PAR_TYPE = {
    "marketing": "agent_marketing",
    "commercial": "agent_commercial",
    "technique": "chef_agence",  # technique → chef directement
}

# ── RÈGLES MÉTIER ────────────────────────────────────────────────────────────
# Chaque règle définit :
#   condition  : lambda(client) → bool
#   type       : "marketing" | "commercial" | "technique"
#   contenu    : lambda(client) → str
#   priorite   : int (1 = plus urgent)
#   seuil_min  : score_churn minimum pour déclencher la règle

REGLES = [
    {
        "id": "score_critique",
        "condition": lambda c: c.score_churn >= 0.85,
        "type": "marketing",
        "contenu": lambda c: (
            f"Score de churn critique ({c.score_churn*100:.0f}%). "
            f"Contact client prioritaire requis : proposer une remise exceptionnelle "
            f"ou un geste commercial personnalisé."
        ),
        "priorite": 1,
        "seuil_min": 0.85,
    },
    {
        "id": "reclamations_critique",
        "condition": lambda c: (c.nb_reclamations or 0) >= 8,
        "type": "technique",
        "contenu": lambda c: (
            f"Volume de réclamations critique : {c.nb_reclamations or 0} réclamations ouvertes. "
            f"Intervention technique urgente requise avant escalade."
        ),
        "priorite": 1,
        "seuil_min": 0.40,
    },
    {
        "id": "reclamations_eleve",
        "condition": lambda c: 4 <= (c.nb_reclamations or 0) < 8,
        "type": "technique",
        "contenu": lambda c: (
            f"{c.nb_reclamations or 0} réclamations en attente. "
            f"Planifier un rappel de satisfaction et résoudre les incidents ouverts."
        ),
        "priorite": 2,
        "seuil_min": 0.40,
    },
    {
        "id": "retards_paiement",
        "condition": lambda c: (c.retards_paiement or 0) >= 3,
        "type": "commercial",
        "contenu": lambda c: (
            f"{c.retards_paiement or 0} retards de paiement enregistrés. "
            f"Proposer un plan d'échelonnement ou réviser le forfait actuel."
        ),
        "priorite": 1,
        "seuil_min": 0.40,
    },
    {
        "id": "anciennete_faible_risque",
        "condition": lambda c: (c.anciennete_mois or 0) <= 6 and (c.score_churn or 0) >= 0.50,
        "type": "marketing",
        "contenu": lambda c: (
            f"Client récent ({c.anciennete_mois or 0} mois) avec risque élevé. "
            f"Déclencher une campagne de fidélisation : bonus data ou offre bienvenue."
        ),
        "priorite": 2,
        "seuil_min": 0.50,
    },
    {
        "id": "faible_consommation_monoservice",
        "condition": lambda c: (c.consommation_moyenne or 0) < 80 and (c.nb_services or 0) <= 2,
        "type": "commercial",
        "contenu": lambda c: (
            f"Faible consommation ({(c.consommation_moyenne or 0):.0f} DT/mois) "
            f"sur {c.nb_services or 0} service(s). "
            f"Opportunité : proposer une offre groupée convergente."
        ),
        "priorite": 3,
        "seuil_min": 0.40,
    },
    {
        "id": "fidele_monoservice",
        "condition": lambda c: (c.nb_services or 0) == 1 and (c.anciennete_mois or 0) >= 18,
        "type": "commercial",
        "contenu": lambda c: (
            f"Client fidèle ({c.anciennete_mois or 0} mois) sur un seul service. "
            f"Profil idéal pour une offre de cross-sell : présenter les offres convergentes."
        ),
        "priorite": 3,
        "seuil_min": 0.40,
    },
]


# ── FONCTION PRINCIPALE ──────────────────────────────────────────────────────


def generer_recommandations_et_notifs(client, agence, createur=None, force=False):
    """
    Génère les recommandations système pour un client et crée les notifications
    correspondantes pour les agents concernés (sans validation chef).

    Args:
        client   : instance ClientChurn
        agence   : instance Agence
        createur : User à l'origine de l'appel (optionnel)
        force    : si True, régénère même si des recs actives existent

    Returns:
        int : nombre de recommandations créées
    """
    from dashboard.models import Recommandation, Notification

    today = timezone.now().date()

    # Expirer les recommandations passées
    Recommandation.objects.filter(
        client=client, echeance__lt=today, statut="active"
    ).update(statut="expiree")

    # Ne pas régénérer si des recs actives existent déjà
    if not force:
        deja_actives = Recommandation.objects.filter(
            client=client,
            statut__in=["active", "en_cours", "completee_agent"],
        ).exists()
        if deja_actives:
            return 0

    # Appliquer les règles
    regles_matchees = sorted(
        [
            r
            for r in REGLES
            if r["condition"](client) and (client.score_churn or 0) >= r["seuil_min"]
        ],
        key=lambda r: r["priorite"],
    )[
        :3
    ]  # max 3 recommandations par client

    if not regles_matchees:
        return 0

    recs_creees = []
    for regle in regles_matchees:
        rec = Recommandation.objects.create(
            client=client,
            type_recommandation=regle["type"],
            contenu=regle["contenu"](client),
            echeance=today + timezone.timedelta(days=14),
            generee_par_systeme=True,
            statut="active",  # ← directement active, sans validation
        )
        recs_creees.append((rec, regle))

    # ── Notifier directement les agents concernés ────────────────────────────
    for rec, regle in recs_creees:
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
                    lu=False,
                )

    return len(recs_creees)


def valider_recommandation(rec, chef, accepte: bool, note: str = ""):
    """
    Le chef valide ou rejette une recommandation.
    Si acceptée → notifier l'agent concerné.
    """
    from dashboard.models import Recommandation, Notification

    if accepte:
        rec.statut = "active"
        rec.modifiee_par = chef
        rec.save()

        # Notifier l'agent du bon service
        role_cible = ROLE_PAR_TYPE.get(rec.type_recommandation)
        if role_cible:
            agents = User.objects.filter(
                agence=chef.agence, role=role_cible, statut="actif"
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
                    lu=False,
                )

    else:
        rec.statut = "retiree"
        rec.note_agent = note
        rec.modifiee_par = chef
        rec.save()


def confirmer_completion(rec, chef, accepte: bool, note: str = ""):
    """
    L'agent dit qu'il a terminé (statut → completee_agent).
    Le chef doit ensuite confirmer ici.
    Si accepté → statut completee. Sinon → retour en active.
    """
    from dashboard.models import Notification

    if accepte:
        rec.statut = "completee"
        rec.modifiee_par = chef
        rec.note_agent = note
        rec.save()

        # Notifier l'agent que sa complétion est confirmée
        if rec.assignee_a:
            Notification.objects.create(
                destinataire=rec.assignee_a,
                type_notif="validation_acceptee",
                recommandation=rec,
                titre="Complétion confirmée par le chef",
                contenu=f"Client {rec.client.client_id} — mission clôturée.",
                lien=f"/clients/{rec.client.id}/#recommandations",
                client=rec.client,
                lu=False,
            )
    else:
        # Remettre en cours
        rec.statut = "active"
        rec.modifiee_par = chef
        rec.save()

        if rec.assignee_a:
            Notification.objects.create(
                destinataire=rec.assignee_a,
                type_notif="validation_refusee",
                recommandation=rec,
                titre="Complétion non confirmée — à reprendre",
                contenu=f"Client {rec.client.client_id} — {note[:80] if note else 'vérification requise'}",
                lien=f"/clients/{rec.client.id}/#recommandations",
                client=rec.client,
                lu=False,
            )


def notifier_alerte_churn(client, agence):
    """
    Crée une alerte churn critique pour le chef d'agence
    (utilisée quand score > 0.90, en dehors des recommandations).
    """
    from dashboard.models import Notification

    chefs = User.objects.filter(agence=agence, role="chef_agence", statut="actif")
    for chef in chefs:
        Notification.objects.get_or_create(
            destinataire=chef,
            type_notif="alerte_churn",
            client=client,
            defaults={
                "titre": f"Alerte churn — {client.client_id}",
                "contenu": (
                    f"Score de churn extrême : {client.score_churn*100:.0f}%. "
                    f"Client {client.nom} ({client.segment}) — intervention immédiate recommandée."
                ),
                "lien": f"/clients/{client.id}/",
                "lu": False,
            },
        )
