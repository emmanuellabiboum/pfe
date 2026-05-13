from django.core.management.base import BaseCommand
from core.models import Notification


class Command(BaseCommand):
    help = "Supprime toutes les notifications (sans supprimer les comptes utilisateurs)"

    def handle(self, *args, **options):
        count = Notification.objects.count()
        Notification.objects.all().delete()
        self.stdout.write(
            self.style.SUCCESS(f"{count} notification(s) supprimée(s)")
        )
