from django.db import models
from accounts.models import User, Agence


class Dataset(models.Model):
    METHODES = [
        ("csv", "Upload CSV"),
        ("db", "Base de données"),
        ("api", "API externe"),
        ("mock", "Données mock"),
    ]

    nom = models.CharField(max_length=200)
    methode = models.CharField(max_length=10, choices=METHODES)
    fichier = models.FileField(upload_to="datasets/", null=True, blank=True)
    agence = models.ForeignKey(Agence, on_delete=models.CASCADE)
    charge_par = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    date_chargement = models.DateTimeField(auto_now_add=True)
    nb_clients = models.IntegerField(default=0)
    actif = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.nom} ({self.get_methode_display()})"

    class Meta:
        verbose_name = "Dataset"


class ClientChurn(models.Model):
    agence = models.ForeignKey("core.Agence", on_delete=models.CASCADE)

    dataset = models.ForeignKey(
        "Dataset",
        on_delete=models.CASCADE,
        related_name="clients",
        null=True,
        blank=True,
    )
    client_id = models.CharField(max_length=100)
    nom = models.CharField(max_length=200, blank=True)
    genre_client = models.CharField(
        max_length=10, choices=[("Homme", "Homme"), ("Femme", "Femme")], blank=True
    )
    date_naissance = models.DateField(null=True, blank=True)
    telephone = models.CharField(max_length=20, blank=True)
    email = models.CharField(max_length=200, blank=True)
    adresse_physique = models.CharField(max_length=200, blank=True)
    identifiant_national = models.CharField(max_length=20, blank=True)
    segment = models.CharField(max_length=100, blank=True)
    date_debut_abonnement = models.DateField(null=True, blank=True)
    statut_actif = models.BooleanField(default=True)
    date_consentement = models.DateField(null=True, blank=True)
    consentement_marketing = models.BooleanField(default=False)
    optout_marketing = models.BooleanField(default=False)
    tenure_jours = models.IntegerField(default=0)
    tenure_mois = models.FloatField(default=0)
    type_abonnement = models.CharField(
        max_length=20,
        choices=[("prepaye", "Prépayé"), ("postpaye", "Post-payé")],
        default="prepaye",
    )
    plan_tarifaire = models.CharField(max_length=100, blank=True)
    facture_moyenne_mensuelle = models.FloatField(default=0)
    moyen_paiement = models.CharField(max_length=50, blank=True)
    nb_appels = models.IntegerField(default=0)
    duree_appel_totale_sec = models.IntegerField(default=0)
    duree_appel_moyenne_sec = models.FloatField(default=0)
    sms_total = models.IntegerField(default=0)
    data_totale_mb = models.FloatField(default=0)
    nb_evenements_data_cdr = models.IntegerField(default=0)
    data_mois_M = models.FloatField(null=True, blank=True)
    data_mois_M1 = models.FloatField(null=True, blank=True)
    tendance_data = models.FloatField(default=0)
    nb_sessions = models.IntegerField(default=0)
    duree_session_moyenne_sec = models.FloatField(default=0)
    recence_session_jours = models.IntegerField(null=True, blank=True)
    taux_cookies = models.FloatField(default=0)
    zone_reseau_principale = models.CharField(max_length=100, blank=True)
    qualite_signal_dominante = models.CharField(max_length=50, blank=True)
    score_qualite_zone = models.FloatField(default=0)
    satisfaction_client = models.FloatField(null=True, blank=True)
    score_frustration = models.FloatField(default=0)
    anciennete_mois = models.IntegerField(default=0)
    nb_reclamations = models.IntegerField(null=True, blank=True)
    reclamation_manquante = models.BooleanField(default=False)
    consommation_moyenne = models.FloatField(default=0)
    retards_paiement = models.IntegerField(default=0)
    nb_services = models.IntegerField(default=0)
    recence_cdr_jours = models.IntegerField(null=True, blank=True)
    flag_offre_data = models.IntegerField(default=0)
    flag_offre_voix = models.IntegerField(default=0)
    data_mois_m_manquante = models.IntegerField(default=0)
    data_mois_m1_manquante = models.IntegerField(default=0)
    score_churn = models.FloatField(default=0)
    churn_predit = models.BooleanField(default=False)
    date_prediction = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.client_id} - {self.score_churn:.0%}"

    def calculer_churn(self):
        if self.score_churn and self.score_churn > 0:
            return self.score_churn >= 0.32
        if self.recence_cdr_jours is None:
            return self.churn_predit
        return self.recence_cdr_jours >= 90

    def save(self, *args, **kwargs):
        if not self.agence_id and self.dataset_id:
            self.agence_id = self.dataset.agence_id
        self.churn_predit = self.calculer_churn()
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "Client Churn"


class EvenementCDR(models.Model):
    """
    Modèle pour les Call Detail Records (CDR).
    Historique détaillé des événements d'usage : appels voix, SMS, sessions data.
    """

    TYPE_EVENEMENT_CHOICES = [
        ("appel", "Appel"),
        ("sms", "SMS"),
        ("donnee_mobile", "Donnée mobile"),
    ]

    client = models.ForeignKey(
        ClientChurn, on_delete=models.CASCADE, related_name="evenements_cdr"
    )
    date_heure = models.DateTimeField()
    type_evenement = models.CharField(max_length=20, choices=TYPE_EVENEMENT_CHOICES)
    numero_source = models.CharField(max_length=20)
    numero_destination = models.CharField(max_length=20)
    duree_appel_sec = models.IntegerField(default=0)
    sms_compte = models.IntegerField(default=0)
    data_mb = models.FloatField(default=0)

    def __str__(self):
        return f"{self.client.client_id} - {self.type_evenement} - {self.date_heure}"

    class Meta:
        verbose_name = "Événement CDR"
        verbose_name_plural = "Événements CDR"
        ordering = ["-date_heure"]


class InteractionDigital(models.Model):
    """
    Interactions digitales du client (app mobile, site web, etc.)
    Permet de calculer l'engagement digital et la récence d'usage.
    """

    TYPE_INTERACTION_CHOICES = [
        ("connexion_app", "Connexion App"),
        ("connexion_web", "Connexion Web"),
        ("recharge", "Recharge en ligne"),
        ("modif_profil", "Modification profil"),
        ("consultation_conso", "Consultation conso"),
        ("activation_option", "Activation option"),
    ]

    client = models.ForeignKey(
        ClientChurn, on_delete=models.CASCADE, related_name="interactions"
    )
    date_heure = models.DateTimeField()
    type_interaction = models.CharField(max_length=50, choices=TYPE_INTERACTION_CHOICES)
    duree_session_sec = models.IntegerField(default=0)
    pages_visitees = models.IntegerField(default=0)
    cookies_acceptes = models.BooleanField(default=False)
    action_concluante = models.BooleanField(
        default=False
    )  # A-t-il accompli son objectif?

    def __str__(self):
        return f"{self.client.client_id} - {self.type_interaction} - {self.date_heure}"

    class Meta:
        verbose_name = "Interaction Digital"
        verbose_name_plural = "Interactions Digitales"
        ordering = ["-date_heure"]


class DonneeGeospatiale(models.Model):
    """
    Données de géolocalisation pour l'analyse des zones de couverture.
    """

    client = models.OneToOneField(
        ClientChurn, on_delete=models.CASCADE, related_name="geolocalisation"
    )
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    code_postal = models.CharField(max_length=10, blank=True)
    zone_couverture = models.CharField(
        max_length=100, blank=True
    )  # Zone avec/ sans couverture
    qualite_reseau_local = models.CharField(
        max_length=50, blank=True
    )  # 4G, 3G, 2G, EDGE
    signal_dbm = models.IntegerField(null=True, blank=True)  # Puissance signal en dBm
    nb_antennes_proximite = models.IntegerField(default=0)

    def __str__(self):
        return f"{self.client.client_id} - {self.zone_couverture}"

    class Meta:
        verbose_name = "Donnée Géospatiale"
        verbose_name_plural = "Données Géospatiales"


class Reclamation(models.Model):
    """
    Historique des réclamations clients.
    """

    TYPE_RECLAMATION_CHOICES = [
        ("technique", "Technique"),
        ("facturation", "Facturation"),
        ("commercial", "Commercial"),
        ("service", "Service client"),
        ("couverture", "Couverture réseau"),
    ]

    STATUT_CHOICES = [
        ("ouvert", "Ouvert"),
        ("en_cours", "En cours de traitement"),
        ("resolu", "Résolu"),
        ("ferme", "Fermé"),
    ]

    client = models.ForeignKey(
        ClientChurn, on_delete=models.CASCADE, related_name="reclamations"
    )
    date_creation = models.DateTimeField(auto_now_add=True)
    type_reclamation = models.CharField(max_length=50, choices=TYPE_RECLAMATION_CHOICES)
    sujet = models.CharField(max_length=200)
    description = models.TextField()
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default="ouvert")
    date_resolution = models.DateTimeField(null=True, blank=True)
    temps_resolution_heures = models.IntegerField(null=True, blank=True)
    satisfait = models.BooleanField(null=True, blank=True)  # NPS après résolution

    def __str__(self):
        return f"{self.client.client_id} - {self.type_reclamation} - {self.sujet[:30]}"

    class Meta:
        verbose_name = "Réclamation"
        verbose_name_plural = "Réclamations"
        ordering = ["-date_creation"]


class CampagneMarketing(models.Model):
    """
    Campagnes marketing et interactions clients.
    """

    TYPE_CAMPAGNE_CHOICES = [
        ("email", "Email"),
        ("sms", "SMS"),
        ("push", "Push notification"),
        ("appel", "Appel sortant"),
    ]

    nom = models.CharField(max_length=200)
    type_campagne = models.CharField(max_length=20, choices=TYPE_CAMPAGNE_CHOICES)
    date_envoi = models.DateTimeField()
    contenu = models.TextField()
    segment_cible = models.CharField(max_length=100, blank=True)

    def __str__(self):
        return f"{self.nom} ({self.type_campagne})"

    class Meta:
        verbose_name = "Campagne Marketing"
        verbose_name_plural = "Campagnes Marketing"


class InteractionCampagne(models.Model):
    """
    Interaction d'un client avec une campagne marketing.
    """

    campagne = models.ForeignKey(
        CampagneMarketing, on_delete=models.CASCADE, related_name="interactions"
    )
    client = models.ForeignKey(
        ClientChurn, on_delete=models.CASCADE, related_name="campagnes"
    )
    date_reception = models.DateTimeField(null=True, blank=True)
    ouvert = models.BooleanField(default=False)
    date_ouverture = models.DateTimeField(null=True, blank=True)
    clique = models.BooleanField(default=False)
    date_clic = models.DateTimeField(null=True, blank=True)
    converti = models.BooleanField(default=False)  # A-t-il fait l'action demandée?
    date_conversion = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.client.client_id} - {self.campagne.nom}"

    class Meta:
        verbose_name = "Interaction Campagne"
        verbose_name_plural = "Interactions Campagnes"


class ShapValeur(models.Model):
    """
    Valeurs SHAP pour expliquer les prédictions de churn.
    Stocke la contribution de chaque feature au score de churn.
    """

    client = models.ForeignKey(
        ClientChurn, on_delete=models.CASCADE, related_name="shap_valeurs"
    )
    feature = models.CharField(max_length=100)  # Nom de la feature
    valeur = models.FloatField()  # Valeur SHAP (impact sur la prédiction)
    importance = models.FloatField()  # Valeur absolue de SHAP (pour le tri)
    date_calcul = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.client.client_id} - {self.feature}: {self.valeur:.4f}"

    class Meta:
        verbose_name = "Valeur SHAP"
        verbose_name_plural = "Valeurs SHAP"
        ordering = ["-importance"]  # Trier par importance décroissante
