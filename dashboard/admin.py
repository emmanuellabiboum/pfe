from django.contrib import admin
from .models import (
    Message, ModelPerformance, SystemMetrics,
    Recommandation, Notification, AnalyseSession, RejetRecommandation
)


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ["sujet", "destinataire", "expediteur", "lu", "date_envoi"]
    search_fields = ["sujet", "destinataire__username"]
    list_filter = ["lu", "date_envoi"]


@admin.register(ModelPerformance)
class ModelPerformanceAdmin(admin.ModelAdmin):
    list_display = ["accuracy", "precision", "recall", "roc_auc", "created_at"]


@admin.register(SystemMetrics)
class SystemMetricsAdmin(admin.ModelAdmin):
    list_display = ["total_predictions", "total_pdfs_generated", "total_recommendations", "errors_count", "updated_at"]


@admin.register(Recommandation)
class RecommandationAdmin(admin.ModelAdmin):
    list_display = ["client", "type_recommandation", "statut", "assignee_a", "date_creation"]
    search_fields = ["client__client_id", "contenu"]
    list_filter = ["type_recommandation", "statut", "date_creation"]


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ["titre", "destinataire", "type_notif", "lu", "date_creation"]
    search_fields = ["titre", "destinataire__username"]
    list_filter = ["type_notif", "lu", "archive", "supprimee"]


@admin.register(AnalyseSession)
class AnalyseSessionAdmin(admin.ModelAdmin):
    list_display = ["date_analyse", "agence", "lancee_par", "nb_clients_total", "methode", "supprimee"]
    search_fields = ["agence__nom", "lancee_par__username"]
    list_filter = ["methode", "supprimee", "date_analyse"]


@admin.register(RejetRecommandation)
class RejetRecommandationAdmin(admin.ModelAdmin):
    list_display = ["recommandation", "demandeur", "statut", "valide_par", "date_demande", "date_validation"]
    search_fields = ["recommandation__client__client_id", "demandeur__username", "explication"]
    list_filter = ["statut", "date_demande", "date_validation"]
