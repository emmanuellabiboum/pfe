from django.db import models


class Ville(models.Model):
    """Villes couvertes par Tunisie Telecom (Kairouan prioritaire pour le stage)"""
    nom = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=10, unique=True, blank=True)
    region = models.CharField(max_length=100, blank=True)
    prioritaire = models.BooleanField(default=False, help_text="Ville prioritaire pour le stage")
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["-prioritaire", "nom"]
        verbose_name = "Ville"

    def __str__(self):
        return f"{self.nom} ({self.region})" if self.region else self.nom

    def save(self, *args, **kwargs):
        if not self.code:
            self.code = self.nom.lower().replace(" ", "_")[:10]
        super().save(*args, **kwargs)


class Agence(models.Model):
    """Agences Tunisie Telecom - liées à une ville"""
    nom = models.CharField(max_length=100)
    ville = models.ForeignKey(Ville, on_delete=models.PROTECT, related_name="agences", null=False, blank=False)
    adresse = models.CharField(max_length=255, blank=True)
    telephone = models.CharField(max_length=20, blank=True)
    code = models.CharField(max_length=20, unique=True)
    active = models.BooleanField(default=True)
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["ville__prioritaire", "ville__nom", "nom"]
        verbose_name = "Agence"

    def __str__(self):
        return f"{self.nom} - {self.ville.nom}"
