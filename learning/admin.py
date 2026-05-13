from django.contrib import admin
from .models import (
    Dataset,
    ClientChurn,
    EvenementCDR,
    InteractionDigital,
    DonneeGeospatiale,
    Reclamation,
    CampagneMarketing,
    InteractionCampagne,
)


@admin.register(Dataset)
class DatasetAdmin(admin.ModelAdmin):
    list_display = ["nom", "methode", "agence", "charge_par", "nb_clients", "actif"]
    search_fields = ["nom"]
    list_filter = ["methode", "actif"]


@admin.register(ClientChurn)
class ClientChurnAdmin(admin.ModelAdmin):
    list_display = [
        "client_id",
        "nom",
        "score_churn",
        "churn_predit",
        "dataset",
    ]
    search_fields = ["client_id", "nom"]
    list_filter = ["churn_predit", "dataset"]


@admin.register(EvenementCDR)
class EvenementCDRAdmin(admin.ModelAdmin):
    list_display = [
        "client",
        "type_evenement",
        "date_heure",
        "duree_appel_sec",
        "data_mb",
    ]
    list_filter = ["type_evenement", "date_heure"]
    search_fields = ["client__client_id"]


@admin.register(InteractionDigital)
class InteractionDigitalAdmin(admin.ModelAdmin):
    list_display = ["client", "type_interaction", "date_heure", "duree_session_sec"]
    list_filter = ["type_interaction", "date_heure"]
    search_fields = ["client__client_id"]


@admin.register(DonneeGeospatiale)
class DonneeGeospatialeAdmin(admin.ModelAdmin):
    list_display = [
        "client",
        "latitude",
        "longitude",
        "zone_couverture",
        "qualite_reseau_local",
    ]
    list_filter = ["zone_couverture", "qualite_reseau_local"]
    search_fields = ["client__client_id"]


@admin.register(Reclamation)
class ReclamationAdmin(admin.ModelAdmin):
    list_display = ["client", "type_reclamation", "sujet", "statut", "date_creation"]
    list_filter = ["type_reclamation", "statut", "date_creation"]
    search_fields = ["client__client_id", "sujet"]


@admin.register(CampagneMarketing)
class CampagneMarketingAdmin(admin.ModelAdmin):
    list_display = ["nom", "type_campagne", "date_envoi", "segment_cible"]
    list_filter = ["type_campagne", "date_envoi"]
    search_fields = ["nom"]


@admin.register(InteractionCampagne)
class InteractionCampagneAdmin(admin.ModelAdmin):
    list_display = ["campagne", "client", "ouvert", "clique", "converti"]
    list_filter = ["ouvert", "clique", "converti"]
    search_fields = ["client__client_id", "campagne__nom"]
