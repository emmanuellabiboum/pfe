from django.db import models
from accounts.models import User
from learning.models import ClientChurn


class Message(models.Model):
    destinataire = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="messages_recus"
    )
    expediteur = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="messages_envoyes",
    )
    client = models.ForeignKey(
        ClientChurn, on_delete=models.SET_NULL, null=True, blank=True
    )
    sujet = models.CharField(max_length=200)
    contenu = models.TextField()
    lu = models.BooleanField(default=False)
    date_envoi = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date_envoi"]
        verbose_name = "Message"

    def __str__(self):
        return f"{self.sujet} → {self.destinataire.username}"


class ModelPerformance(models.Model):
    accuracy = models.FloatField(default=0)
    precision = models.FloatField(default=0)
    recall = models.FloatField(default=0)
    roc_auc = models.FloatField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)


class SystemMetrics(models.Model):
    total_predictions = models.IntegerField(default=0)
    total_pdfs_generated = models.IntegerField(default=0)
    total_recommendations = models.IntegerField(default=0)
    errors_count = models.IntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)


from django.db import models
from django.utils import timezone

NOTIF_TYPES = [
    ("recommandation", "Recommandation"),
    ("validation_requise", "Validation requise"),
    ("validation_acceptee", "Validation acceptée"),
    ("validation_refusee", "Validation refusée"),
    ("alerte_churn", "Alerte churn"),
    ("compte", "Compte utilisateur"),
    ("info", "Information"),
]

REC_TYPES = [
    ("marketing", "Marketing"),
    ("commercial", "Commercial"),
    ("technique", "Technique"),
]

REC_STATUTS = [
    ("en_attente_validation", "En attente de validation"),
    ("active", "Active"),
    ("en_cours", "En cours"),
    ("completee_agent", "Complétée (à valider)"),
    ("completee", "Complétée"),
    ("retiree", "Rejetée"),
    ("expiree", "Expirée"),
]


class Recommandation(models.Model):
    client = models.ForeignKey(
        "learning.ClientChurn", on_delete=models.CASCADE, related_name="recommandations"
    )
    type_recommandation = models.CharField(max_length=20, choices=REC_TYPES)
    contenu = models.TextField()
    echeance = models.DateField(null=True, blank=True)
    statut = models.CharField(max_length=25, choices=REC_STATUTS, default="active")
    generee_par_systeme = models.BooleanField(default=True)
    clv_estimee = models.FloatField(
        null=True,
        blank=True,
        help_text="Estimation CLV (DT) au moment de la génération",
    )
    cree_par = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="recs_creees",
    )

    assignee_a = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="recs_assignees",
    )
    modifiee_par = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="recs_modifiees",
    )
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    note_agent = models.TextField(blank=True)

    class Meta:
        ordering = ["-date_creation"]

    def __str__(self):
        return f"[{self.type_recommandation}] {self.client} — {self.statut}"

    def get_type_recommandation_display_fr(self):
        return dict(REC_TYPES).get(self.type_recommandation, self.type_recommandation)

    @property
    def temps_restant_jours(self) -> int:
        """
        Calcule le nombre de jours restants avant l'échéance.

        Returns:
            Nombre de jours (négatif si dépassée)
        """
        from datetime import date

        if not self.echeance:
            return 0
        delta = self.echeance - date.today()
        return delta.days

    @property
    def temps_restant_affichage(self) -> str:
        """
        Retourne le temps restant formaté pour l'affichage.

        Returns:
            String formatée (ex: "3j restants", "Échéance dépassée", "Pas d'échéance")
        """
        if not self.echeance:
            return "Pas d'échéance"

        jours = self.temps_restant_jours

        if jours < 0:
            return f"Échéance dépassée de {-jours}j"
        elif jours == 0:
            return "Échéance aujourd'hui"
        elif jours == 1:
            return "1j restant"
        elif jours <= 7:
            return f"{jours}j restants"
        elif jours <= 30:
            semaines = jours // 7
            return f"{semaines}s restantes"
        else:
            return f"{jours}j restants"

    @property
    def urgence(self) -> str:
        """
        Détermine le niveau d'urgence basé sur le temps restant.

        Returns:
            'critique', 'eleve', 'moyen', 'faible', or 'none'
        """
        if not self.echeance:
            return "none"

        jours = self.temps_restant_jours

        if self.statut in ["completee", "retiree", "expiree"]:
            return "none"

        if jours < 0:
            return "critique"  # Échéance dépassée
        elif jours <= 1:
            return "critique"  # Moins de 24h
        elif jours <= 3:
            return "eleve"  # 1-3 jours
        elif jours <= 7:
            return "moyen"  # 4-7 jours
        else:
            return "faible"  # Plus d'une semaine

    @property
    def couleur_urgence(self) -> str:
        """
        Retourne la couleur associée au niveau d'urgence.

        Returns:
            Code couleur CSS/bootstrap
        """
        couleurs = {
            "critique": "danger",  # Rouge
            "eleve": "warning",  # Orange
            "moyen": "info",  # Bleu
            "faible": "success",  # Vert
            "none": "secondary",  # Gris
        }
        return couleurs.get(self.urgence, "secondary")


class Notification(models.Model):
    destinataire = models.ForeignKey(
        "accounts.User", on_delete=models.CASCADE, related_name="notifications"
    )
    type_notif = models.CharField(max_length=25, choices=NOTIF_TYPES)
    titre = models.CharField(max_length=200)
    contenu = models.TextField()
    lien = models.CharField(max_length=300, blank=True)
    client = models.ForeignKey(
        "learning.ClientChurn", on_delete=models.SET_NULL, null=True, blank=True
    )
    recommandation = models.ForeignKey(
        Recommandation, on_delete=models.SET_NULL, null=True, blank=True
    )
    lu = models.BooleanField(default=False)
    archive = models.BooleanField(default=False)
    supprimee = models.BooleanField(default=False)
    date_suppression = models.DateTimeField(null=True, blank=True)
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date_creation"]

    def __str__(self):
        return f"[{self.type_notif}] → {self.destinataire} — {'lu' if self.lu else 'non lu'}"


class RejetRecommandation(models.Model):
    """Stocke les demandes de rejet de recommandation avec explication"""

    recommandation = models.ForeignKey(
        Recommandation, on_delete=models.CASCADE, related_name="rejets"
    )
    demandeur = models.ForeignKey(
        "accounts.User", on_delete=models.CASCADE, related_name="rejets_demandes"
    )
    explication = models.TextField(
        help_text="Pourquoi voulez-vous rejeter cette recommandation ?"
    )
    statut = models.CharField(
        max_length=20,
        choices=[
            ("en_attente", "En attente de validation"),
            ("accepte", "Accepté"),
            ("refuse", "Refusé"),
        ],
        default="en_attente",
    )
    valide_par = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="rejets_valides",
    )
    date_demande = models.DateTimeField(auto_now_add=True)
    date_validation = models.DateTimeField(null=True, blank=True)
    note_validation = models.TextField(blank=True)

    class Meta:
        ordering = ["-date_demande"]
        verbose_name = "Rejet de recommandation"
        verbose_name_plural = "Rejets de recommandations"

    def __str__(self):
        return f"Rejet {self.recommandation.id} par {self.demandeur.username} — {self.statut}"


class AnalyseSession(models.Model):

    agence = models.ForeignKey(
        "core.Agence", on_delete=models.CASCADE, related_name="analyses"
    )
    lancee_par = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        related_name="analyses_lancees",
    )
    date_analyse = models.DateTimeField(auto_now_add=True)

    nb_clients_total = models.IntegerField(default=0)
    nb_clients_churn = models.IntegerField(default=0)
    nb_clients_non_churn = models.IntegerField(default=0)

    score_churn_moyen = models.FloatField(default=0.0)
    nb_recommandations_generees = models.IntegerField(default=0)

    # Métriques du modèle ML
    seuil_optimal = models.FloatField(default=0.25)
    auc_roc = models.FloatField(default=0.0)
    f1_score = models.FloatField(default=0.0)
    recall = models.FloatField(default=0.0)
    precision = models.FloatField(default=0.0)

    METHODE_CHOICES = [
        ("mock", "Données simulées"),
        ("csv", "Import CSV"),
        ("api", "API Externe"),
    ]
    methode = models.CharField(max_length=10, choices=METHODE_CHOICES, default="mock")

    supprimee = models.BooleanField(default=False)
    date_suppression = models.DateTimeField(null=True, blank=True)

    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-date_analyse"]
        verbose_name = "Session d'analyse"
        verbose_name_plural = "Sessions d'analyse"

    def __str__(self):
        return f"Analyse {self.date_analyse.strftime('%d/%m/%Y %H:%M')} - {self.agence.nom} ({self.nb_clients_total} clients)"

    def get_differences_with_previous(self):
        previous = AnalyseSession.objects.filter(
            agence=self.agence, date_analyse__lt=self.date_analyse
        ).first()

        if not previous:
            return None

        return {
            "clients_diff": self.nb_clients_total - previous.nb_clients_total,
            "churn_diff": self.nb_clients_churn - previous.nb_clients_churn,
            "non_churn_diff": self.nb_clients_non_churn - previous.nb_clients_non_churn,
            "score_moyen_diff": round(
                self.score_churn_moyen - previous.score_churn_moyen, 2
            ),
            "recommandations_diff": self.nb_recommandations_generees
            - previous.nb_recommandations_generees,
            "previous_date": previous.date_analyse,
        }
