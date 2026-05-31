from django.urls import path
from . import views
from django.conf import settings
from django.conf.urls.static import static

app_name = "dashboard"

urlpatterns = [
    path("", views.accueil, name="accueil"),
    path("administration/", views.administration, name="administration"),
    path("administration/villes/creer/", views.creer_ville, name="creer_ville"),
    path(
        "administration/villes/<int:ville_id>/modifier/",
        views.modifier_ville,
        name="modifier_ville",
    ),
    path(
        "administration/villes/<int:ville_id>/supprimer/",
        views.supprimer_ville,
        name="supprimer_ville",
    ),
    path("administration/agences/creer/", views.creer_agence, name="creer_agence"),
    path(
        "administration/agences/<int:agence_id>/modifier/",
        views.modifier_agence,
        name="modifier_agence",
    ),
    path(
        "administration/agences/<int:agence_id>/supprimer/",
        views.supprimer_agence,
        name="supprimer_agence",
    ),
    path(
        "administration/agences/<int:agence_id>/activer/",
        views.activer_agence,
        name="activer_agence",
    ),
    path(
        "administration/agences/<int:agence_id>/historique/",
        views.historique_agence_view,
        name="historique_agence",
    ),
    path(
        "administration/utilisateurs/creer/",
        views.creer_utilisateur,
        name="creer_utilisateur",
    ),
    path(
        "administration/utilisateurs/<int:user_id>/supprimer/",
        views.supprimer_utilisateur,
        name="supprimer_utilisateur",
    ),
    path("clients/", views.liste_clients, name="clients"),
    path(
        "clients/<str:client_id>/shap/", views.shap_explanation, name="shap_explanation"
    ),
    path(
        "clients/<int:client_id>/shap/", views.shap_explanation, name="shap_explanation"
    ),
    path("clients/<str:client_id>/", views.fiche_client, name="fiche_client"),
    path(
        "clients/<int:client_id>/",
        views.fiche_client,
        name="fiche_client",
    ),
    path(
        "clients/<str:client_id>/pdf/",
        views.fiche_client_pdf,
        name="fiche_client_pdf",
    ),
    path("generer-mock/", views.generer_mock, name="generer_mock"),
    path("reinitialiser/", views.reinitialiser_dashboard, name="reinitialiser"),
    path("dashboard-global/", views.dashboard_global, name="dashboard_global"),
    path("dashboard-global/rapport-pdf/", views.export_rapport_pdf, name="rapport_pdf"),
    path("notifications/", views.notifications_view, name="notifications"),
    path("notifications/api/", views.notifications_api_view, name="notifications_api"),
    path("kpi/api/", views.kpi_api_view, name="kpi_api"),
    path("notifications/marquer-lu/", views.marquer_lu, name="marquer_lu"),
    path(
        "notifications/<int:notif_id>/",
        views.notification_detail_view,
        name="notification_detail",
    ),
    path(
        "notifications/<int:notif_id>/supprimer/",
        views.supprimer_notification,
        name="supprimer_notification",
    ),
    path(
        "notifications/<int:notif_id>/archiver/",
        views.archiver_notification,
        name="archiver_notification",
    ),
    path(
        "notifications/<int:notif_id>/marquer-lu/",
        views.marquer_lu_notification,
        name="marquer_lu_notification",
    ),
    path(
        "notifications/<int:notif_id>/desarchiver/",
        views.desarchiver_notification,
        name="desarchiver_notification",
    ),
    path(
        "notifications/archivees/",
        views.notifications_archivees_view,
        name="notifications_archivees",
    ),
    path(
        "notifications/supprimees/",
        views.notifications_supprimees_view,
        name="notifications_supprimees",
    ),
    path(
        "notifications/<int:notif_id>/restaurer/",
        views.restaurer_notification,
        name="restaurer_notification",
    ),
    path(
        "notifications/<int:notif_id>/supprimer-definitivement/",
        views.supprimer_definitivement_notification,
        name="supprimer_definitivement_notification",
    ),
    path(
        "notifications/bulk-delete/",
        views.bulk_delete_notifications,
        name="bulk_delete_notifications",
    ),
    path(
        "notifications/bulk-restore/",
        views.bulk_restore_notifications,
        name="bulk_restore_notifications",
    ),
    path(
        "bulk-hard-delete/",
        views.bulk_hard_delete_notifications,
        name="bulk_hard_delete_notifications",
    ),
    path(
        "analyses/<int:analyse_id>/supprimer-definitivement/",
        views.supprimer_definitivement_analyse,
        name="supprimer_definitivement_analyse",
    ),
    path(
        "analyses/mois/<str:mois_cle>/supprimer/",
        views.supprimer_analyses_mois,
        name="supprimer_analyses_mois",
    ),
    path(
        "lancer-analyse/",
        views.lancer_analyse,
        name="lancer_analyse",
    ),
    path(
        "train-models/",
        views.train_models,
        name="train_models",
    ),
    path(
        "recommandations/<int:rec_id>/completer/",
        views.completer_rec,
        name="completer_rec",
    ),
    path(
        "recommandations/<int:rec_id>/action/",
        views.action_recommandation,
        name="action_recommandation",
    ),
    path(
        "clients/<str:client_id>/recommandations/creer/",
        views.creer_recommandation_agent,
        name="creer_recommandation",
    ),
    path(
        "recommandations/<int:rec_id>/rejeter/",
        views.rejeter_recommandation,
        name="rejeter_recommandation",
    ),
    path(
        "recommandations/<int:rec_id>/valider-creation/",
        views.valider_creation_recommandation,
        name="valider_creation_recommandation",
    ),
    path(
        "recommandations/<int:rec_id>/valider-completion/",
        views.valider_completion_recommandation,
        name="valider_completion_recommandation",
    ),
    path(
        "rejets/<int:rejet_id>/valider/",
        views.valider_rejet_recommandation,
        name="valider_rejet_recommandation",
    ),
    path(
        "recommandations/",
        views.recommandations_dashboard,
        name="recommandations_dashboard",
    ),
    path("pilotage/", views.pilotage_agence, name="pilotage_agence"),
    path("pilotage/datasets/<int:dataset_id>/supprimer/", views.supprimer_dataset, name="supprimer_dataset"),
    path("pilotage/notifications/purger/", views.purger_notifications, name="purger_notifications"),
]


if settings.DEBUG:
    urlpatterns += static(
        settings.STATIC_URL, document_root=settings.STATICFILES_DIRS[0]
    )
