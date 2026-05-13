from django.utils import timezone
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from .models import Recommandation, Notification
from accounts.models import User
import logging

logger = logging.getLogger(__name__)


def check_expired_recommendations():
    today = timezone.now().date()
    expired_recs = Recommandation.objects.filter(
        echeance__lt=today, statut="active"
    ).select_related("client", "assignee_a", "client__dataset__agence")

    count = 0
    for rec in expired_recs:
        rec.statut = "expiree"
        rec.save(update_fields=["statut"])
        count += 1

        if rec.assignee_a:
            Notification.objects.create(
                destinataire=rec.assignee_a,
                type_notif="alerte_churn",
                titre=f"Recommandation expirée - Client {rec.client.client_id}",
                contenu=f'La recommandation "{rec.contenu[:100]}..." pour le client {rec.client.nom} a expiré le {rec.echeance}.',
                lien=f"/fiche_client/{rec.client.id}/",
                client=rec.client,
                recommandation=rec,
            )
            logger.info(
                f"Notification créée pour {rec.assignee_a.username} - Recommandation expirée {rec.id}"
            )

    logger.info(f"{count} recommandations marquées comme expirées")
    return {"expired_count": count}


def send_reminder_notifications():
    reminder_days = 3
    reminder_date = timezone.now().date() + timezone.timedelta(days=reminder_days)

    upcoming_recs = Recommandation.objects.filter(
        echeance=reminder_date, statut="active"
    ).select_related("client", "assignee_a", "client__dataset__agence")

    count = 0
    for rec in upcoming_recs:
        if rec.assignee_a:
            Notification.objects.create(
                destinataire=rec.assignee_a,
                type_notif="info",
                titre=f"Rappel - Échéance proche",
                contenu=f"La recommandation pour le client {rec.client.nom} expire dans {reminder_days} jours ({rec.echeance}).",
                lien=f"/fiche_client/{rec.client.id}/",
                client=rec.client,
                recommandation=rec,
            )
            count += 1
            logger.info(
                f"Rappel envoyé à {rec.assignee_a.username} - Recommandation {rec.id}"
            )

    logger.info(
        f"{count} rappels envoyés pour les échéances dans {reminder_days} jours"
    )
    return {"reminder_count": count}


def generate_recommendations_for_high_risk_clients():
    from learning.models import ClientChurn
    from .utils import generer_recommandations_client

    high_risk_clients = ClientChurn.objects.filter(
        score_churn__gte=0.60
    ).select_related("dataset__agence")

    count = 0
    for client in high_risk_clients:
        has_active_recs = Recommandation.objects.filter(
            client=client, statut="active"
        ).exists()

        if not has_active_recs:
            users = User.objects.filter(agence=client.agence, is_active=True).first()
            if users:
                generer_recommandations_client(client, client.agence, createur=users)
                count += 1

    logger.info(
        f"{count} nouvelles recommandations générées pour clients à haut risque"
    )
    return {"generated_count": count}
