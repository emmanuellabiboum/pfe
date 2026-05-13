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

    # Infos client
    client_id = models.CharField(max_length=100)
    nom = models.CharField(max_length=200, blank=True)
    genre_client = models.CharField(
        max_length=10, choices=[("Homme", "Homme"), ("Femme", "Femme")], blank=True
    )
    date_naissance = models.DateField(null=True, blank=True)
    telephone = models.CharField(max_length=20, blank=True)
    email = models.CharField(max_length=200, blank=True)
    adresse_physique = models.CharField(max_length=200, blank=True)
    identifiant_national = models.CharField(max_length=20, blank=True)  # CIN tunisienne
    segment = models.CharField(max_length=100, blank=True)

    # Dates et statut
    date_debut_abonnement = models.DateField(null=True, blank=True)
    statut_actif = models.BooleanField(default=True)
    date_consentement = models.DateField(null=True, blank=True)
    consentement_marketing = models.BooleanField(default=False)
    optout_marketing = models.BooleanField(default=False)

    # Tenure (durée de relation client)
    tenure_jours = models.IntegerField(default=0)
    tenure_mois = models.FloatField(default=0)

    # Profil contractuel
    type_abonnement = models.CharField(
        max_length=20,
        choices=[("prepaye", "Prépayé"), ("postpaye", "Post-payé")],
        default="prepaye",
    )
    plan_tarifaire = models.CharField(max_length=100, blank=True)
    facture_moyenne_mensuelle = models.FloatField(default=0)
    moyen_paiement = models.CharField(max_length=50, blank=True)

    # Usage télécom agrégé (CDR)
    nb_appels = models.IntegerField(default=0)
    duree_appel_totale_sec = models.IntegerField(default=0)
    duree_appel_moyenne_sec = models.FloatField(default=0)
    sms_total = models.IntegerField(default=0)
    data_totale_mb = models.FloatField(default=0)
    nb_evenements_data_cdr = models.IntegerField(default=0)

    # Tendance de consommation
    data_mois_M = models.FloatField(null=True, blank=True)  # Data du mois M
    data_mois_M1 = models.FloatField(null=True, blank=True)  # Data du mois M-1
    tendance_data = models.FloatField(default=0)  # Variation data entre M et M-1

    # Engagement digital
    nb_sessions = models.IntegerField(default=0)
    duree_session_moyenne_sec = models.FloatField(default=0)
    recence_session_jours = models.IntegerField(null=True, blank=True)
    taux_cookies = models.FloatField(default=0)

    # Qualité de service et satisfaction
    zone_reseau_principale = models.CharField(max_length=100, blank=True)
    qualite_signal_dominante = models.CharField(max_length=50, blank=True)
    score_qualite_zone = models.FloatField(default=0)
    satisfaction_client = models.FloatField(null=True, blank=True)  # 1-5
    score_frustration = models.FloatField(default=0)

    # Features ML existants
    anciennete_mois = models.IntegerField(default=0)
    nb_reclamations = models.IntegerField(
        null=True, blank=True
    )  # NaN = jamais contacté support, 0 = contacté sans réclamation
    reclamation_manquante = models.BooleanField(
        default=False
    )  # Indicateur pour distinguer NaN vs 0
    consommation_moyenne = models.FloatField(default=0)
    retards_paiement = models.IntegerField(default=0)
    nb_services = models.IntegerField(default=0)
    recence_cdr_jours = models.IntegerField(
        null=True, blank=True
    )  # Jours depuis dernier CDR (exclu des features ML pour éviter data leakage)

    # Flags structurels pour l'audit RGS-90 (Feature Engineering ML)
    flag_offre_data = models.IntegerField(
        default=0
    )  # 1 si l'offre inclut la data, 0 sinon
    flag_offre_voix = models.IntegerField(
        default=0
    )  # 1 si l'offre inclut la voix, 0 sinon

    # Flags pour valeurs manquantes (stratégie NaN avec flags - RGS-90)
    data_mois_m_manquante = models.IntegerField(default=0)  # 1 si data_mois_M est NaN
    data_mois_m1_manquante = models.IntegerField(default=0)  # 1 si data_mois_M1 est NaN

    # Prédiction
    score_churn = models.FloatField(default=0)  # 0 à 1
    churn_predit = models.BooleanField(default=False)
    date_prediction = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.client_id} — {self.score_churn:.0%}"

    def calculer_churn(self):
        """
        Calcule le churn selon le score ML (prioritaire) ou la règle RGS-90.
        - Si un score ML est disponible (> 0), utilise le seuil 0.32 (aligné FastAPI).
        - Sinon, si recence_cdr_jours >= 90, applique la règle RGS-90.
        - Sinon, conserve la valeur actuelle.

        Returns:
            bool: True si le client est churné, False sinon
        """
        # Priorité au score ML s'il est disponible et valide
        if self.score_churn and self.score_churn > 0:
            return self.score_churn >= 0.32
        if self.recence_cdr_jours is None:
            # Ni score ML ni recence disponible : conserver la valeur actuelle
            return self.churn_predit
        return self.recence_cdr_jours >= 90

    def save(self, *args, **kwargs):
        """
        Surcharge de save pour mettre à jour automatiquement churn_predit.
        Le score ML prend le pas sur la règle RGS-90 dès qu'il est disponible.
        """
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
    numero_destination = models.CharField(max_length=20)  # "INTERNET" pour data
    duree_appel_sec = models.IntegerField(default=0)  # 0 pour non-appel
    sms_compte = models.IntegerField(default=0)  # 0 ou 1
    data_mb = models.FloatField(default=0)  # 0 pour non-data

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
