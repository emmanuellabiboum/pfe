from django.utils import timezone
from accounts.models import User
from core.model_config import estimate_clv

ROLE_PAR_TYPE = {
    "marketing": "agent_marketing",
    "commercial": "agent_commercial",
    "technique": "chef_agence",  
}

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
        "condition": lambda c: (c.anciennete_mois or 0) <= 6
        and (c.score_churn or 0) >= 0.50,
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
        "condition": lambda c: (c.consommation_moyenne or 0) < 80
        and (c.nb_services or 0) <= 2,
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
        "condition": lambda c: (c.nb_services or 0) == 1
        and (c.anciennete_mois or 0) >= 18,
        "type": "commercial",
        "contenu": lambda c: (
            f"Client fidèle ({c.anciennete_mois or 0} mois) sur un seul service. "
            f"Profil idéal pour une offre de cross-sell : présenter les offres convergentes."
        ),
        "priorite": 3,
        "seuil_min": 0.40,
    },
]


def generer_recommandations_et_notifs(client, agence, createur=None, force=False):
    
    from dashboard.models import Recommandation, Notification

    today = timezone.now().date()

    Recommandation.objects.filter(
        client=client, echeance__lt=today, statut="active"
    ).update(statut="expiree")

    if not force:
        regles_existantes = set(
            Recommandation.objects.filter(
                client=client,
                statut__in=["active", "en_cours", "completee_agent"],
                generee_par_systeme=True,
            ).values_list("contenu", flat=True)
        )
        deja_actives = len(regles_existantes) > 0
        if deja_actives:
            return 0

   
    regles_matchees = [
        r
        for r in REGLES
        if r["condition"](client) and (client.score_churn or 0) >= r["seuil_min"]
    ]

    if not regles_matchees:
        return 0

    clv_estimee = estimate_clv(client)
    regles_matchees = sorted(
        regles_matchees, key=lambda r: (r["priorite"], -clv_estimee)
    )[
        :3
    ] 

    if not regles_matchees:
        return 0

    recs_creees = []
    for regle in regles_matchees:
        contenu_base = regle["contenu"](client)
        
        deja_expiree = Recommandation.objects.filter(
            client=client,
            contenu__icontains=contenu_base,
            statut="expiree"
        ).exists()

        final_contenu = contenu_base
        if deja_expiree:
            final_contenu = f"RETARD : {contenu_base}"
            nouvelle_echeance = today + timezone.timedelta(days=1)
        else:
            
            nouvelle_echeance = today + timezone.timedelta(days=2)

        rec = Recommandation.objects.create(
            client=client,
            type_recommandation=regle["type"],
            contenu=final_contenu,
            echeance=nouvelle_echeance,
            generee_par_systeme=True,
            clv_estimee=clv_estimee,
            statut="active",
        )
        recs_creees.append((rec, regle))

    for rec, regle in recs_creees:
        role_cible = ROLE_PAR_TYPE.get(rec.type_recommandation)
        if role_cible:
            agents = User.objects.filter(agence=agence, role=role_cible, statut="actif")
            for agent in agents:
                contenu_notif = f"Client {rec.client.client_id} ({rec.client.nom}) : {rec.contenu[:120]}"

                Notification.objects.create(
                    destinataire=agent,
                    type_notif="recommandation",
                    recommandation=rec,
                    titre=f"Nouvelle mission — {rec.get_type_recommandation_display_fr()}",
                    contenu=contenu_notif,
                    lien=f"/clients/{rec.client.id}/#recommandations",
                    client=rec.client,
                    lu=False,
                )

    return len(recs_creees)


def valider_recommandation(rec, chef, accepte: bool, note: str = ""):
    
    from dashboard.models import Recommandation, Notification

    if accepte:
        rec.statut = "active"
        rec.modifiee_par = chef
        rec.save()

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
    
    from dashboard.models import Notification

    if accepte:
        rec.statut = "completee"
        rec.modifiee_par = chef
        rec.note_agent = note
        rec.save()

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
