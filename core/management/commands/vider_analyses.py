from django.core.management.base import BaseCommand
from dashboard.models import AnalyseSession


class Command(BaseCommand):
    help = "Supprime toutes les sessions d'analyse (AnalyseSession)"

    def handle(self, *args, **options):
        count = AnalyseSession.objects.count()
        AnalyseSession.objects.all().delete()
        self.stdout.write(
            self.style.SUCCESS(f"{count} session(s) d'analyse supprimée(s)")
        )
