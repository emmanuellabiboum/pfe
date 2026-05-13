from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from core.models import Notification


class Command(BaseCommand):
    help = "Supprime les notifications en double et nettoie les anciennes notifications"

    def handle(self, *args, **options):
        # Trouver les notifications en double (même titre, même contenu, même destinataire, créées dans un court intervalle)
        notifications = Notification.objects.all()
        duplicates = 0
        deleted = 0

        # Grouper par destinataire, titre, contenu et client
        for notif in notifications:
            # Chercher les notifications similaires créées dans les 5 dernières minutes
            similar = Notification.objects.filter(
                destinataire=notif.destinataire,
                titre=notif.titre,
                contenu=notif.contenu,
                client=notif.client,
                date_creation__gte=notif.date_creation - timedelta(minutes=5),
                date_creation__lt=notif.date_creation
            ).exclude(id=notif.id)

            if similar.exists():
                duplicates += similar.count()
                similar.delete()
                deleted += similar.count()

        # Supprimer les notifications archivées de plus de 30 jours
        old_archived = Notification.objects.filter(
            archive=True,
            date_creation__lt=timezone.now() - timedelta(days=30)
        )
        old_count = old_archived.count()
        old_archived.delete()

        # Supprimer les notifications supprimées (soft-delete) de plus de 30 jours
        old_deleted = Notification.objects.filter(
            supprimee=True,
            date_creation__lt=timezone.now() - timedelta(days=30)
        )
        deleted_count = old_deleted.count()
        old_deleted.delete()

        total_deleted = deleted + old_count + deleted_count

        self.stdout.write(
            self.style.SUCCESS(
                f"Nettoyage terminé : {duplicates} doublons supprimés, "
                f"{old_count} notifications archivées supprimées, "
                f"{deleted_count} notifications supprimées définitivement. "
                f"Total : {total_deleted} notifications supprimées."
            )
        )
