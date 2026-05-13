from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, JsonResponse
from django.conf import settings
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.template.loader import render_to_string
from django.core.serializers.json import DjangoJSONEncoder
from django.core.exceptions import ObjectDoesNotExist
from django.contrib import messages
from django.utils import timezone
from django.db import models
from django.db.models import Avg, Count
from django.db.models import ExpressionWrapper, FloatField, F

import json
import pdfkit
import pandas as pd

from accounts.models import User
from accounts.forms import AgenceForm
from learning.models import ClientChurn
from learning.importers import create_dataset_from_dataframe
from dashboard.models import Recommandation, Notification, AnalyseSession
from core.mock_data import generer_mock_data
from core.notifications_engine import valider_recommandation, confirmer_completion


def _can_manage_tables(user):
    return user.is_superuser or user.role in ["chef_agence", "admin", "super_admin"]


def _can_manage_users(user):
    return user.is_superuser or user.role in ["admin", "super_admin"]


@login_required
def accueil(request):
    if request.user.role in ["admin", "super_admin"]:
        return redirect("accounts:gestion_comptes")

    context = {}
    is_agent = request.user.role in ["agent_marketing", "agent_commercial"]
    is_chef = request.user.role == "chef_agence"
    is_superuser = request.user.is_superuser

    # Charger les modèles ML depuis le metadata.json
    import json
    from pathlib import Path

    BASE_DIR = Path(__file__).parent.parent
    METADATA_PATH = (
        BASE_DIR / "pfe_final" / "churn_api" / "fastapi_artifacts" / "churn_metadata_v1.json"
    )

    ml_models = []
    _metadata = {}
    if METADATA_PATH.exists():
        with open(METADATA_PATH, "r", encoding="utf-8") as f:
            _metadata = json.load(f)
            metriques = _metadata.get("metriques_test", {})
            # Créer un modèle ML depuis le metadata
            ml_models.append(
                {
                    "nom": _metadata.get("modele", {}).get("nom", "Random Forest"),
                    "type_modele": "random_forest",
                    "accuracy": metriques.get("AUC_ROC", 0),
                    "precision": metriques.get("Precision", 0),
                    "recall": metriques.get("Recall", 0),
                    "auc": metriques.get("AUC_ROC", 0),
                    "f1_score": metriques.get("F1", 0),
                }
            )
    else:
        # Fallback: utiliser les métriques depuis core/model_config.py
        from core.model_config import MODEL_METRICS

        ml_models.append(
            {
                "nom": MODEL_METRICS["name"],
                "type_modele": "xgboost",
                "accuracy": MODEL_METRICS["aucroc"],
                "precision": MODEL_METRICS["precision"],
                "recall": MODEL_METRICS["recall"],
                "auc": MODEL_METRICS["aucroc"],
                "f1_score": MODEL_METRICS["f1_score"],
            }
        )

    context["ml_models"] = ml_models

    if is_agent and not is_superuser:
        return render(request, "dashboard/accueil_agent.html", context)

    if request.user.agence:
        from learning.models import ClientChurn
        from dashboard.tasks import check_expired_recommendations

        check_expired_recommendations()

        clients = ClientChurn.objects.filter(dataset__agence=request.user.agence)
        total_clients = clients.count()
        clients_churn = clients.filter(churn_predit=True).count()
        clients_non_churn = clients.filter(churn_predit=False).count()

        avg_prediction = clients.aggregate(Avg("score_churn"))["score_churn__avg"] or 0
        taux_churn = (
            round(clients_churn / total_clients * 100, 1) if total_clients else 0
        )

        context = {
            "total_clients": total_clients,
            "clients_churn": clients_churn,
            "clients_non_churn": clients_non_churn,
            "avg_prediction": round(avg_prediction * 100, 1),
            "taux_churn": taux_churn,
            "has_data": total_clients > 0,
            "ml_models": ml_models,
            "has_session": False,  # Par défaut, sera mis à True si session existe
        }

        # Toujours charger la dernière session même si total_clients == 0
        from dashboard.models import AnalyseSession

        last_session = (
            AnalyseSession.objects.filter(agence=request.user.agence)
            .order_by("-date_analyse")
            .first()
        )
        if last_session:
            context.update(
                {
                    "last_session": last_session,
                    "has_session": True,
                    "seuil_optimal": (
                        last_session.seuil_optimal
                        if last_session.seuil_optimal
                        else 0.32
                    ),
                    "auc_roc": last_session.auc_roc if last_session.auc_roc else 0.8954,
                    "f1_score": (
                        last_session.f1_score if last_session.f1_score else 0.7797
                    ),
                    "recall": last_session.recall if last_session.recall else 0.92,
                }
            )
        elif total_clients > 0:
            # Des clients existent mais pas de session formelle :
            # on affiche quand même les résultats avec les métriques du metadata
            metriques = _metadata.get("metriques_test", {})
            seuil = _metadata.get("seuil_decision", {}).get("valeur", 0.32)
            context.update(
                {
                    "has_session": True,
                    "seuil_optimal": seuil,
                    "auc_roc": metriques.get("AUC_ROC", 0.8954),
                    "f1_score": metriques.get("F1", 0.7797),
                    "recall": metriques.get("Recall", 0.92),
                }
            )

    if request.user.role in ["admin", "super_admin"]:
        return render(request, "dashboard/accueil.html", context)

    if request.user.agence:
        return render(request, "dashboard/accueil.html", context)

    return redirect("accounts:assign_agence")


@login_required
def assign_agence(request):
    if request.method == "POST":
        form = AgenceForm(request.POST)
        if form.is_valid():
            request.user.agence = form.cleaned_data["agence"]
            request.user.save()
            return redirect("dashboard:accueil")
    else:
        form = AgenceForm()
    return render(request, "accounts/assign_agence.html", {"form": form})


def _read_uploaded_dataset(uploaded_file):
    uploaded_file.seek(0)
    ext = uploaded_file.name.split(".")[-1].lower()

    if ext in ["csv", "txt"]:
        uploaded_file.seek(0)
        # Read as bytes and decode to avoid bytes-like object error
        content = uploaded_file.read()
        if isinstance(content, bytes):
            content = content.decode("utf-8")
        import io

        return pd.read_csv(io.StringIO(content), sep=None, engine="python")
    if ext in ["tsv", "tab"]:
        uploaded_file.seek(0)
        content = uploaded_file.read()
        if isinstance(content, bytes):
            content = content.decode("utf-8")
        import io

        return pd.read_csv(io.StringIO(content), sep="\t")
    if ext in ["xlsx", "xls", "xlsm"]:
        uploaded_file.seek(0)
        return pd.read_excel(uploaded_file)

    raise ValueError("Format de fichier non supporté")


@login_required
@require_POST
def lancer_analyse(request):
    import logging

    logger = logging.getLogger(__name__)

    logger.info(
        f"[lancer_analyse] Début de la vue - user={request.user.username}, agence={request.user.agence}"
    )
    logger.info(f"[lancer_analyse] Headers Accept: {request.headers.get('Accept')}")

    if request.method == "POST":
        from learning.models import ClientChurn
        from dashboard.models import AnalyseSession

        methode = request.POST.get("methode")
        uploaded_file = request.FILES.get("csv_file")

        logger.info(
            f"[lancer_analyse] methode={methode}, fichier_recu={'oui' if uploaded_file else 'non'}"
        )

        if methode == "csv" and uploaded_file:
            from django.db.models import Q

            # Supprimer uniquement les clients mock si le vrai dataset est uploadé
            clients_to_delete = ClientChurn.objects.filter(
                Q(dataset__isnull=True) | Q(dataset__methode="mock"),
                agence=request.user.agence,
            )
            client_ids = list(clients_to_delete.values_list("id", flat=True))

            Recommandation.objects.filter(client_id__in=client_ids).delete()
            Notification.objects.filter(client_id__in=client_ids).delete()
            clients_to_delete.delete()

            try:
                df = _read_uploaded_dataset(uploaded_file)
                if df.empty:
                    raise ValueError("Le fichier est vide ou le format est invalide.")

                dataset, clients_crees = create_dataset_from_dataframe(
                    df, request.user.agence, request.user, uploaded_file=uploaded_file
                )
                messages.success(
                    request,
                    f"Dataset uploadé avec succès : {clients_crees} clients enregistrés.",
                )

            except Exception as e:
                import logging

                logger = logging.getLogger(__name__)
                logger.error(f"Erreur upload dataset : {str(e)}")
                if (
                    request.headers.get("X-Requested-With") == "XMLHttpRequest"
                    or request.headers.get("Accept") == "application/json"
                ):
                    return JsonResponse(
                        {
                            "success": False,
                            "error": f"Erreur lors de l'import du fichier : {str(e)}",
                        },
                        status=400,
                    )
                messages.error(
                    request,
                    f"Erreur lors de l'import du fichier : {str(e)}",
                )
                return redirect("dashboard:accueil")

        if methode == "mock":
            from django.db.models import Q

            # Supprimer uniquement les anciens clients mock (pas les vrais CSV)
            clients_to_delete = ClientChurn.objects.filter(
                Q(dataset__isnull=True) | Q(dataset__methode="mock"),
                agence=request.user.agence,
            )
            client_ids = list(clients_to_delete.values_list("id", flat=True))
            Recommandation.objects.filter(client_id__in=client_ids).delete()
            Notification.objects.filter(client_id__in=client_ids).delete()
            clients_to_delete.delete()

            # Toujours générer des mocks frais (logique identique à l'import CSV)
            try:
                from core.mock_data import generer_mock_data

                generer_mock_data(
                    agence_id=request.user.agence.id,
                    user_id=request.user.id,
                    nb_clients=50,
                )
                messages.info(request, "50 clients mock générés.")

            except Exception as e:
                import logging

                logger = logging.getLogger(__name__)
                logger.error(f"Erreur génération mock data: {str(e)}")
                if (
                    request.headers.get("X-Requested-With") == "XMLHttpRequest"
                    or request.headers.get("Accept") == "application/json"
                ):
                    return JsonResponse(
                        {
                            "success": False,
                            "error": f"Erreur lors de la génération des données mock: {str(e)}",
                        },
                        status=500,
                    )
                messages.error(
                    request,
                    f"Erreur lors de la génération des données mock: {str(e)}",
                )
                return redirect("dashboard:accueil")

        # BLOC PRINCIPAL DE PRÉDICTION ET TRAITEMENT
        try:
            # Traiter tous les clients pour les prédictions via l'API FastAPI
            from core.fastapi_service import (
                predict_batch_from_dataframe,
                check_fastapi_health,
            )

            # Seuils alignés sur pfe_final/churn_api/app/config.py
            # - Décision churn: 0.32
            SEUIL_CHURN = 0.32

            # Scoper les clients selon la méthode (mock = uniquement mocks, csv = tous les CSV)
            from django.db.models import Q
            if methode == "mock":
                clients = ClientChurn.objects.filter(
                    Q(dataset__methode="mock") | Q(dataset__isnull=True),
                    agence=request.user.agence,
                )
            else:
                clients = ClientChurn.objects.filter(dataset__agence=request.user.agence)

            logger.info(
                f"[lancer_analyse] Début de la prédiction - methode={methode} - nb_clients={clients.count()}"
            )

            # Essayer d'utiliser l'API FastAPI en priorité
            fastapi_available = check_fastapi_health()
            logger.info(f"[lancer_analyse] FastAPI disponible: {fastapi_available}")

            if not fastapi_available:
                # Alignement sur FastAPI : pas de fallback local (sinon incohérences entre pages)
                msg = (
                    "Le serveur FastAPI (localhost:8000) n'est pas disponible. "
                    "Démarre l'API puis relance l'analyse."
                )
                logger.error(f"[lancer_analyse] {msg}")
                if (
                    request.headers.get("X-Requested-With") == "XMLHttpRequest"
                    or request.headers.get("Accept") == "application/json"
                ):
                    return JsonResponse({"success": False, "error": msg}, status=503)
                messages.error(request, msg)
                return redirect("dashboard:accueil")

            if clients.count() > 0:
                try:
                    # Créer un DataFrame avec les données des clients pour l'API
                    # Utiliser _build_fastapi_payload_from_client pour garantir la cohérence
                    # avec les appels unitaires à /api/predict
                    from core.ml_service import _build_fastapi_payload_from_client

                    clients_data = []
                    for client in clients:
                        clients_data.append(_build_fastapi_payload_from_client(client))

                    df_clients = pd.DataFrame(clients_data)
                    api_result = predict_batch_from_dataframe(df_clients)

                    if api_result and "predictions" in api_result:
                        # Mettre à jour les clients avec les résultats de l'API
                        for client, pred in zip(
                            clients, api_result.get("predictions", [])
                        ):
                            # FastAPI returns the key `probabilite_churn` in batch predictions.
                            score = pred.get("probabilite_churn", 0)
                            ClientChurn.objects.filter(pk=client.pk).update(
                                score_churn=score,
                                churn_predit=score >= SEUIL_CHURN,
                            )
                        logger.info(
                            f"Prédictions effectuées via API FastAPI pour {clients.count()} clients"
                        )
                    else:
                        raise Exception("Résultat API invalide")

                except Exception as e:
                    logger.warning(
                        f"Erreur API FastAPI (batch), basculage sur /api/predict (unitaire) : {str(e)}"
                    )
                    # Basculer sur des prédictions unitaires via FastAPI en cas d'erreur batch
                    from core.ml_service import predict_churn_score_from_client

                    for client in clients:
                        try:
                            score = predict_churn_score_from_client(client)
                            if score is not None:
                                ClientChurn.objects.filter(pk=client.pk).update(
                                    score_churn=score,
                                    churn_predit=score >= SEUIL_CHURN,
                                )
                            else:
                                logger.warning(f"Prédiction FastAPI unitaire nulle pour client_id={client.client_id}")
                        except Exception as e:
                            logger.error(f"Erreur prédiction unitaire client {client.client_id}: {str(e)}")
            else:
                logger.info("[lancer_analyse] Aucun client à scorer (dataset vide).")

            from django.db.models import Avg, Q

            if methode == "mock":
                clients = ClientChurn.objects.filter(
                    Q(dataset__methode="mock") | Q(dataset__isnull=True),
                    agence=request.user.agence,
                )
            else:
                clients = ClientChurn.objects.filter(dataset__agence=request.user.agence)
            total_clients = clients.count()
            clients_churn = clients.filter(churn_predit=True).count()
            clients_non_churn = clients.filter(churn_predit=False).count()
            score_moyen = clients.aggregate(Avg("score_churn"))["score_churn__avg"] or 0

            # Calculer les valeurs SHAP pour les clients churn
            from core.ml_service import get_shap_explanation
            from core.notifications_engine import generer_recommandations_et_notifs

            shap_summary = []
            clients_churn_list = clients.filter(churn_predit=True)

            for client in clients_churn_list[:10]:  # Top 10 clients churn pour SHAP
                try:
                    shap_data = get_shap_explanation(client)
                    if shap_data and "features" in shap_data:
                        for feat in shap_data["features"][:5]:  # Top 5 features par client
                            shap_summary.append(
                                {
                                    "client_id": client.client_id,
                                    "feature": feat["feature"],
                                    "shap_value": feat["shap_value"],
                                    "direction": feat.get("direction", "vers_churn"),
                                }
                            )
                except Exception as e:
                    logger.warning(
                        f"Erreur SHAP pour client {client.client_id}: {str(e)}"
                    )

            # Générer les recommandations pour les clients churn
            total_recs_generees = 0
            for client in clients_churn_list:
                try:
                    nb_rec = generer_recommandations_et_notifs(
                        client,
                        request.user.agence,
                        createur=request.user,
                        force=True,  # Régénérer pour cette analyse
                    )
                    total_recs_generees += nb_rec
                except Exception as e:
                    logger.warning(
                        f"Erreur génération recommandations pour client {client.client_id}: {str(e)}"
                    )

            nb_recommandations = Recommandation.objects.filter(
                client__in=clients
            ).count()

            from dashboard.models import AnalyseSession

            # Charger les métriques du modèle ML depuis le metadata.json
            import json
            from pathlib import Path

            BASE_DIR = Path(__file__).parent.parent
            METADATA_PATH = (
                BASE_DIR / "pfe_final" / "churn_api" / "fastapi_artifacts" / "churn_metadata_v1.json"
            )

            ml_metrics = {
                "seuil_optimal": 0.25,
                "auc_roc": 0.8646,
                "f1_score": 0.7097,
                "recall": 0.88,
                "precision": 0.5946,
            }

            if METADATA_PATH.exists():
                with open(METADATA_PATH, "r", encoding="utf-8") as f:
                    metadata = json.load(f)
                    metriques = metadata.get("metriques_test", {})
                    ml_metrics["seuil_optimal"] = metadata.get("seuil_decision", {}).get("valeur", 0.32)
                    ml_metrics["auc_roc"] = metriques.get("AUC_ROC", 0.8954)
                    ml_metrics["f1_score"] = metriques.get("F1", 0.7797)
                    ml_metrics["recall"] = metriques.get("Recall", 0.92)
                    ml_metrics["precision"] = metriques.get("Precision", 0.6765)

            analyse_session = AnalyseSession.objects.create(
                agence=request.user.agence,
                lancee_par=request.user,
                methode=methode,
                nb_clients_total=total_clients,
                nb_clients_churn=clients_churn,
                nb_clients_non_churn=clients_non_churn,
                score_churn_moyen=round(score_moyen * 100, 2),
                nb_recommandations_generees=nb_recommandations,
                seuil_optimal=ml_metrics["seuil_optimal"],
                auc_roc=ml_metrics["auc_roc"],
                f1_score=ml_metrics["f1_score"],
                recall=ml_metrics["recall"],
                precision=ml_metrics["precision"],
            )

            differences = analyse_session.get_differences_with_previous()

            titre = f"Analyse terminée - {total_clients} clients analysés"

            if differences:
                contenu = (
                    f"L'analyse a détecté {clients_churn} client(s) en churn "
                    f"({differences['churn_diff']:+d} vs précédent). "
                    f"Score moyen: {round(score_moyen * 100, 1)}% ({differences['score_moyen_diff']:+.1f}%)."
                )
            else:
                contenu = (
                    f"L'analyse a détecté {clients_churn} client(s) en churn. "
                    f"Score moyen: {round(score_moyen * 100, 1)}%. "
                    f"Consultez la liste des clients pour voir les recommandations."
                )

            Notification.objects.create(
                destinataire=request.user,
                type_notif="alerte_churn",
                titre=titre,
                contenu=contenu,
                lien="/clients/",
            )

            if (
                request.headers.get("X-Requested-With") == "XMLHttpRequest"
                or request.headers.get("Accept") == "application/json"
            ):
                taux_churn = (
                    round(clients_churn / total_clients * 100, 1)
                    if total_clients
                    else 0
                )

                # Récupérer les recommandations pour l'affichage
                recommandations = []
                if nb_recommandations > 0:
                    recs = Recommandation.objects.filter(
                        client__in=clients_churn_list
                    ).select_related("client")[:10]
                    recommandations = [
                        {
                            "client_id": rec.client.client_id,
                            "client_nom": rec.client.nom,
                            "type": rec.type_recommandation,
                            "priorite": rec.statut,  # Utiliser statut comme priorité
                            "message": rec.contenu,  # Utiliser contenu au lieu de message
                        }
                        for rec in recs
                    ]

                return JsonResponse(
                    {
                        "total": total_clients,
                        "churn": clients_churn,
                        "non_churn": clients_non_churn,
                        "score_moyen": round(score_moyen * 100, 1),
                        "taux_churn": taux_churn,
                        "seuil_optimal": float(ml_metrics["seuil_optimal"]),
                        "auc_roc": float(ml_metrics["auc_roc"]),
                        "f1_score": float(ml_metrics["f1_score"]),
                        "recall": float(ml_metrics["recall"]),
                        "shap_values": shap_summary,
                        "recommandations": recommandations,
                        "nb_recommandations": nb_recommandations,
                    }
                )

        except Exception as e:
            logger.error(f"[lancer_analyse] ERREUR GLOBALE : {str(e)}", exc_info=True)
            if (
                request.headers.get("X-Requested-With") == "XMLHttpRequest"
                or request.headers.get("Accept") == "application/json"
            ):
                return JsonResponse(
                    {"success": False, "error": f"Erreur lors de l'analyse : {str(e)}"},
                    status=500,
                )
            messages.error(request, f"Erreur lors de l'analyse : {str(e)}")
            return redirect("dashboard:accueil")

    return redirect("dashboard:accueil")


@login_required
@require_POST
def train_models(request):
    return JsonResponse(
        {
            "status": "disabled",
            "message": "Le modèle est déjà entraîné (Optuna v3: AUCROC 0.8646, F1 0.717, Recall 0.76). Utilisez l'analyse directe.",
        }
    )


@login_required
def liste_clients(request):
    from django.db.models.functions import Coalesce

    # Pour les admins : afficher tous les clients de leur ville
    if request.user.role in ["admin", "super_admin"]:
        admin_ville = (
            request.user.admin_ville.ville
            if hasattr(request.user, "admin_ville")
            else None
        )
        if not admin_ville:
            return render(
                request, "dashboard/erreur.html", {"message": "Aucune ville assignée."}
            )
        clients_list = ClientChurn.objects.filter(
            dataset__agence__ville=admin_ville
        ).order_by("-score_churn", "id")
    else:
        # Pour les agents/chefs : afficher les clients de leur agence
        if not request.user.agence:
            return render(
                request, "dashboard/erreur.html", {"message": "Aucune agence associée."}
            )
        clients_list = ClientChurn.objects.filter(
            dataset__agence=request.user.agence
        ).order_by("-score_churn", "id")

    context = {
        "clients_json": json.dumps(
            list(
                clients_list.annotate(
                    anciennete_mois_safe=Coalesce("anciennete_mois", 0),
                    nb_reclamations_safe=Coalesce("nb_reclamations", 0),
                ).values(
                    "id",
                    "client_id",
                    "nom",
                    "anciennete_mois_safe",
                    "nb_reclamations_safe",
                    "score_churn",
                    "churn_predit",
                )
            ),
            cls=DjangoJSONEncoder,
        ),
        "kpis": {
            "total": clients_list.count(),
            "churn": clients_list.filter(churn_predit=True).count(),
            "non_churn": clients_list.filter(churn_predit=False).count(),
        },
    }
    return render(request, "dashboard/clients.html", context)


@login_required
def fiche_client(request, client_id):
    from core.ml_service import get_fastapi_prediction_details
    from core.notifications_engine import generer_recommandations_et_notifs

    client = get_object_or_404(ClientChurn, id=client_id, agence=request.user.agence)
    score_pct = round(client.score_churn * 100, 1)
    if client.churn_predit:
        score_color = "#dc3545"
        risque_label = "Churn"
        header_gradient = "linear-gradient(135deg, #8b0000, #dc3545)"
    else:
        score_color = "#00b464"
        risque_label = "Non-churn"
        header_gradient = "linear-gradient(135deg, #004d2a, #00b464)"

    # ── SHAP : récupérer la vraie sortie FastAPI (/api/predict) ──────────────
    shap_payload = get_fastapi_prediction_details(client)
    shap_error = None
    shap_waterfall = []
    shap_features = []  # on garde aussi un format "liste" pour l'UI

    if shap_payload and shap_payload.get("features_explicatives"):
        try:
            base_value = float(shap_payload.get("valeur_base_shap") or 0)
            proba = float(shap_payload.get("probabilite_churn") or 0)

            feats = shap_payload.get("features_explicatives", [])[:6]
            cumul = base_value
            points = [base_value, proba]
            segments = []

            # Normaliser les largeurs de barres SHAP pour qu'elles tiennent dans 0-100%
            max_shap = max(abs(float(f.get("shap_value") or 0)) for f in feats) or 1.0

            for f in feats:
                shap_val = float(f.get("shap_value") or 0)
                start = cumul
                end = cumul + shap_val
                cumul = end
                points.extend([start, end])
                segments.append(
                    {
                        "feature": f.get("feature", "Inconnu"),
                        "interpretation": f.get("interpretation", ""),
                        "shap_value": shap_val,
                        "start": start,
                        "end": end,
                    }
                )

                # Normaliser la largeur par rapport au max (max = 100%)
                width_norm = min(round((abs(shap_val) / max_shap) * 100, 1), 100.0)

                shap_features.append(
                    {
                        "feature": f.get("feature", "Inconnu"),
                        "valeur": shap_val,
                        "valeur_abs": abs(shap_val),
                        "width_percent": width_norm,
                        "description": f.get(
                            "interpretation", f.get("feature", "Inconnu")
                        ),
                    }
                )

            # Reste des features (non affichées) : on l'ajoute pour que le waterfall retombe sur proba
            autres = proba - cumul
            if abs(autres) > 1e-6:
                start = cumul
                end = cumul + autres
                points.extend([start, end])
                segments.append(
                    {
                        "feature": "Autres facteurs",
                        "interpretation": "Contribution cumulée des autres variables",
                        "shap_value": float(autres),
                        "start": start,
                        "end": end,
                    }
                )

            axis_min = min(points + [0.0])
            axis_max = max(points + [1.0])
            if axis_max - axis_min < 1e-9:
                axis_max = axis_min + 1.0

            def _scale(x: float) -> float:
                return (x - axis_min) / (axis_max - axis_min)

            for seg in segments:
                s = _scale(seg["start"])
                e = _scale(seg["end"])
                left = min(s, e) * 100
                width = abs(e - s) * 100
                shap_waterfall.append(
                    {
                        "feature": seg["feature"],
                        "interpretation": seg["interpretation"],
                        "shap_value": seg["shap_value"],
                        "left_percent": round(left, 2),
                        "width_percent": round(width, 2),
                        "is_positive": seg["shap_value"] >= 0,
                    }
                )

            shap_meta = {
                "base_value": round(base_value, 4),
                "probabilite": round(proba, 4),
                "axis_min": round(axis_min, 4),
                "axis_max": round(axis_max, 4),
            }
        except Exception as e:
            shap_error = f"Erreur diagramme SHAP: {str(e)}"
            shap_meta = None
    else:
        # Fallback : calculer SHAP localement si FastAPI n'est pas disponible
        shap_error = "FastAPI indisponible — SHAP calculé localement."
        try:
            from core.ml_service import get_shap_explanation
            local_shap = get_shap_explanation(client)
            if local_shap and local_shap.get("features"):
                feats = local_shap["features"]
                max_shap = max(abs(f["shap_value"]) for f in feats) or 1.0
                for f in feats:
                    shap_val = f["shap_value"]
                    width_norm = min(round((abs(shap_val) / max_shap) * 100, 1), 100.0)
                    shap_features.append({
                        "feature": f["feature"],
                        "valeur": shap_val,
                        "valeur_abs": abs(shap_val),
                        "width_percent": width_norm,
                        "description": f.get("interpretation", f["feature"]),
                    })
                shap_meta = {
                    "base_value": local_shap.get("base_value", 0),
                    "probabilite": client.score_churn,
                }
                shap_error = None
        except Exception as e:
            shap_error = f"SHAP indisponible: {str(e)}"
            shap_meta = None

    today = timezone.now().date()
    Recommandation.objects.filter(
        client=client, echeance__lt=today, statut="active"
    ).update(statut="expiree")
    recs_actives = Recommandation.objects.filter(client=client, statut="active")
    # Seuil "actionnable" aligné sur FastAPI (>= 0.32 = risque au moins moyen)
    if not recs_actives.exists() and client.score_churn >= 0.32:
        # Recommandations automatiques (règles métier) + notifications aux agents concernés
        generer_recommandations_et_notifs(
            client, request.user.agence, createur=request.user
        )
    recommandations_actives = Recommandation.objects.filter(
        client=client, statut="active"
    ).order_by("type_recommandation")
    recommandations_a_valider_completion = Recommandation.objects.filter(
        client=client, statut="completee_agent"
    ).order_by("-date_modification")
    recommandations_archivees = Recommandation.objects.filter(
        client=client, statut__in=["completee", "retiree", "expiree"]
    ).order_by("-echeance")

    # Recommandations en attente de validation (pour le chef)
    from dashboard.models import RejetRecommandation

    recommandations_en_attente = Recommandation.objects.filter(
        client=client, statut="en_attente_validation"
    ).order_by("type_recommandation")

    # Rejets en attente de validation (pour le chef)
    rejets_en_attente = RejetRecommandation.objects.filter(
        recommandation__client=client, statut="en_attente"
    ).order_by("-date_demande")

    # Réclamations du client
    from learning.models import Reclamation

    reclamations = Reclamation.objects.filter(client=client).order_by("-date_creation")

    return render(
        request,
        "dashboard/fiche_client.html",
        {
            "client": client,
            "score_pct": score_pct,
            "score_color": score_color,
            "risque_label": risque_label,
            "header_gradient": header_gradient,
            "shap_features": shap_features,
            "shap_waterfall": shap_waterfall,
            "shap_meta": shap_meta,
            "shap_error": shap_error,
            "recommandations_actives": recommandations_actives,
            "recommandations_a_valider_completion": recommandations_a_valider_completion,
            "recommandations_archivees": recommandations_archivees,
            "recommandations_en_attente": recommandations_en_attente,
            "rejets_en_attente": rejets_en_attente,
            "reclamations": reclamations,
        },
    )


@login_required
def fiche_client_pdf(request, client_id):
    from learning.models import ClientChurn

    client = get_object_or_404(ClientChurn, id=client_id, agence=request.user.agence)
    score_pct = int(client.score_churn * 100)
    risque_label = (
        "ÉLEVÉ"
        if client.score_churn >= 0.60
        else "MODÉRÉ" if client.score_churn >= 0.32 else "FAIBLE"
    )

    # Récupérer les features SHAP depuis le modèle learning
    from learning.models import ShapValeur

    shap_features = list(client.shap_valeurs.all()[:10])

    context = {
        "client": client,
        "score_pct": score_pct,
        "risque_label": risque_label,
        "shap_features": shap_features,
        "recommandations_actives": Recommandation.objects.filter(
            client=client, statut="active"
        ),
        "recommandations_archivees": Recommandation.objects.filter(
            client=client
        ).exclude(statut="active"),
    }
    return render(request, "dashboard/fiche_client_pdf.html", context)


@login_required
def export_rapport_pdf(request):
    from dashboard.models import Recommandation
    from learning.models import ClientChurn
    from django.utils import timezone
    from django.db.models import Avg

    agence = request.user.agence
    clients = ClientChurn.objects.filter(dataset__agence=agence)
    total = clients.count()

    context = {
        "agence": agence,
        "user": request.user,
        "today": timezone.now(),
        "total": total,
        "eleve": clients.filter(score_churn__gte=0.60).count(),
        "moyen": clients.filter(score_churn__gte=0.32, score_churn__lt=0.60).count(),
        "faible": clients.filter(score_churn__lt=0.32).count(),
        "taux_churn": (
            round((clients.filter(churn_predit=True).count() / total) * 100, 1)
            if total > 0
            else 0
        ),
        "score_moyen": round(
            (clients.aggregate(Avg("score_churn"))["score_churn__avg"] or 0) * 100, 1
        ),
        "top_clients": clients.filter(score_churn__gte=0.60).order_by("-score_churn")[
            :10
        ],
        "recommandations": Recommandation.objects.filter(
            client__dataset__agence=agence, statut="active"
        )[:20],
    }

    html = render_to_string("dashboard/rapport_pdf.html", context)

    if not settings.PDFKIT_CONFIG:
        from django.contrib import messages

        messages.error(request, "wkhtmltopdf non installé.")
        return redirect("dashboard:dashboard_global")

    options = {
        "page-size": "A4",
        "encoding": "UTF-8",
        "no-outline": None,
        "margin-top": "15mm",
        "margin-bottom": "15mm",
        "margin-left": "15mm",
        "margin-right": "15mm",
        "footer-right": "Page [page] sur [topage]",
        "footer-font-size": "9",
    }

    try:
        pdf = pdfkit.from_string(
            html, False, configuration=settings.PDFKIT_CONFIG, options=options
        )
        response = HttpResponse(pdf, content_type="application/pdf")
        response["Content-Disposition"] = (
            f'attachment; filename="rapport_{agence.code}_{timezone.now().strftime("%Y%m%d")}.pdf"'
        )
        return response
    except Exception as e:
        from django.contrib import messages

        messages.error(request, f"Erreur PDF : {str(e)}")
        return redirect("dashboard:dashboard_global")


@login_required
def reinitialiser_dashboard(request):
    """Réinitialise le dashboard en supprimant tous les clients et analyses de l'agence"""
    if request.method != "POST":
        return JsonResponse(
            {"success": False, "error": "Méthode non autorisée"}, status=405
        )

    try:
        from learning.models import ClientChurn
        from dashboard.models import AnalyseSession, Recommandation

        # Supprimer tous les clients de l'agence
        clients_supprimes = ClientChurn.objects.filter(
            dataset__agence=request.user.agence
        ).delete()[0]

        # Supprimer toutes les analyses de l'agence
        analyses_supprimees = AnalyseSession.objects.filter(
            agence=request.user.agence
        ).delete()[0]

        # Supprimer toutes les recommandations de l'agence
        recs_supprimees = Recommandation.objects.filter(
            client__dataset__agence=request.user.agence
        ).delete()[0]

        return JsonResponse(
            {
                "success": True,
                "clients_supprimes": clients_supprimes,
                "analyses_supprimees": analyses_supprimees,
                "recs_supprimees": recs_supprimees,
            }
        )
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)


@login_required
def generer_mock(request):
    from core.mock_data import generer_mock_data

    generer_mock_data(
        agence_id=request.user.agence.id, user_id=request.user.id, nb_clients=50
    )

    # Calculer les scores basés sur les règles métier
    clients = ClientChurn.objects.filter(dataset__agence=request.user.agence)
    for client in clients:
        # Score basé sur réclamations et retards de paiement (avec valeurs par défaut)
        nb_reclamations = client.nb_reclamations or 0
        retards_paiement = client.retards_paiement or 0
        score = min(0.3 + (nb_reclamations * 0.1) + (retards_paiement * 0.15), 0.95)
        client.score_churn = round(score, 2)
        # Seuils alignés sur FastAPI (pfe_final/churn_api/app/config.py)
        client.churn_predit = score >= 0.32
        client.save(update_fields=["score_churn", "churn_predit"])

    return redirect("dashboard:clients")


@login_required
def dashboard_global(request):
    if request.user.role in ["admin", "super_admin"]:
        return redirect("accounts:gestion_comptes")

    agence = request.user.agence
    if not agence:
        return redirect("dashboard:accueil")

    clients = ClientChurn.objects.filter(dataset__agence=agence)

    if not clients.exists():
        return render(request, "dashboard/dashboard_global.html", {"empty": True})

    total = clients.count()
    churn = clients.filter(churn_predit=True).count()
    non_churn = clients.filter(churn_predit=False).count()
    taux_churn = round(churn / total * 100, 1) if total else 0
    score_moyen = round(
        (clients.aggregate(avg=Avg("score_churn"))["avg"] or 0) * 100, 1
    )

    # Recommandations
    recs = Recommandation.objects.filter(client__in=clients)
    recs_actives = recs.filter(statut="active").count()
    recs_a_valider = recs.filter(statut="completee_agent").count()
    recs_completees = recs.filter(statut="completee").count()
    recs_marketing = recs.filter(
        type_recommandation="marketing", statut="active"
    ).count()
    recs_commercial = recs.filter(
        type_recommandation="commercial", statut="active"
    ).count()
    recs_technique = recs.filter(
        type_recommandation="technique", statut="active"
    ).count()

    # Calculer le taux de complétion
    total_rec = recs_actives + recs_a_valider + recs_completees
    taux_completion = (
        round(recs_completees / total_rec * 100, 1) if total_rec > 0 else 0
    )

    top_clients = (
        clients.filter(score_churn__gte=0.60)
        .annotate(
            score_pct=ExpressionWrapper(
                F("score_churn") * 100, output_field=FloatField()
            )
        )
        .order_by("-score_churn")[:5]
    )

    donut_data = {
        "labels": ["Churn", "Non-churn"],
        "data": [churn, non_churn],
        "colors": ["#ef4444", "#10b981"],
    }

    recs_data = {
        "labels": ["Marketing", "Commercial", "Technique"],
        "actives": [
            recs.filter(type_recommandation="marketing", statut="active").count(),
            recs.filter(type_recommandation="commercial", statut="active").count(),
            recs.filter(type_recommandation="technique", statut="active").count(),
        ],
        "completees": [
            recs.filter(type_recommandation="marketing", statut="completee").count(),
            recs.filter(type_recommandation="commercial", statut="completee").count(),
            recs.filter(type_recommandation="technique", statut="completee").count(),
        ],
    }

    today = timezone.now()
    debut_semaine = today - timezone.timedelta(days=today.weekday())
    debut_semaine_prec = debut_semaine - timezone.timedelta(weeks=1)
    fin_semaine_prec = debut_semaine

    semaine_actuelle = clients.filter(date_prediction__gte=debut_semaine).count()
    semaine_precedente = clients.filter(
        date_prediction__gte=debut_semaine_prec,
        date_prediction__lt=fin_semaine_prec,
    ).count()
    evolution = (
        round((semaine_actuelle - semaine_precedente) / semaine_precedente * 100, 1)
        if semaine_precedente > 0
        else 0
    )

    # Importance des features — SHAP globales depuis le vrai modèle ML
    shap_global = []
    try:
        import pandas as pd
        from pathlib import Path

        shap_csv = Path("pfe_final/churn_api/fastapi_artifacts/shap_importance_v1.csv")
        if shap_csv.exists():
            df_shap = pd.read_csv(shap_csv.absolute())
            # Prendre le top 10 des features les plus influentes
            top10 = df_shap.nsmallest(10, "rang_shap")
            for _, row in top10.iterrows():
                feat_name = str(row["feature"])
                # Nettoyer les noms encodés (One-Hot Encoding)
                feat_clean = feat_name.replace("plan_tarifaire_", "").replace("_", " ")
                shap_global.append({
                    "feature": feat_clean,
                    "importance_moyenne": float(row["importance"]),
                    "importance_pct": float(row["importance_pct"]),
                    "impact": "positif" if float(row["importance"]) > 0.01 else "neutre",
                })
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Impossible de charger les importances SHAP: {e}")
        # Fallback sur des données métier réelles
        if clients.exists():
            avg_reclamations = (
                clients.aggregate(avg_rec=models.Avg("nb_reclamations"))["avg_rec"] or 0
            )
            avg_retards = (
                clients.aggregate(avg_ret=models.Avg("retards_paiement"))["avg_ret"] or 0
            )
            avg_score = (
                clients.aggregate(avg_score=models.Avg("score_churn"))["avg_score"] or 0
            )
            shap_global = [
                {"feature": "Réclamations", "importance_moyenne": min(avg_reclamations / 5, 1.0), "importance_pct": 25, "impact": "positif"},
                {"feature": "Retards paiement", "importance_moyenne": min(avg_retards / 4, 1.0), "importance_pct": 20, "impact": "positif"},
                {"feature": "Score churn moyen", "importance_moyenne": avg_score, "importance_pct": 15, "impact": "positif"},
                {"feature": "Ancienneté", "importance_moyenne": 0.3, "importance_pct": 10, "impact": "neutre"},
                {"feature": "Consommation", "importance_moyenne": 0.25, "importance_pct": 8, "impact": "neutre"},
            ]

    context = {
        "empty": False,
        "agence": agence,
        "today": today,
        "total": total,
        "taux_churn": taux_churn,
        "churn": churn,
        "non_churn": non_churn,
        "score_moyen": score_moyen,
        "recs_actives": recs_actives,
        "recs_completees": recs_completees,
        "taux_completion": taux_completion,
        "recs_marketing": recs_marketing,
        "recs_commercial": recs_commercial,
        "recs_technique": recs_technique,
        "top_clients": top_clients,
        "donut_data": donut_data,
        "recs_data": recs_data,
        "semaine_actuelle": semaine_actuelle,
        "semaine_precedente": semaine_precedente,
        "evolution": evolution,
        "shap_global": shap_global,
    }

    return render(request, "dashboard/dashboard_global.html", context)


@login_required
def historique_analyses_view(request):
    filter_type = request.GET.get("filter", "all")  # all, mock, real

    analyses = (
        AnalyseSession.objects.filter(agence=request.user.agence, supprimee=False)
        .select_related("lancee_par")
        .order_by("-date_analyse")
    )

    # Filtrer par type
    if filter_type == "mock":
        analyses = analyses.filter(methode="mock")
    elif filter_type == "real":
        analyses = analyses.exclude(methode="mock")

    analyses_with_diff = []
    for analyse in analyses:
        diff = analyse.get_differences_with_previous()
        analyses_with_diff.append(
            {
                "analyse": analyse,
                "diff": diff,
            }
        )

    mois_fr = {
        1: "Janvier",
        2: "Février",
        3: "Mars",
        4: "Avril",
        5: "Mai",
        6: "Juin",
        7: "Juillet",
        8: "Août",
        9: "Septembre",
        10: "Octobre",
        11: "Novembre",
        12: "Décembre",
    }
    groupes = {}
    for item in analyses_with_diff:
        dt = item["analyse"].date_analyse
        cle = dt.strftime("%Y-%m")
        if cle not in groupes:
            groupes[cle] = {
                "label": f"{mois_fr[dt.month]} {dt.year}",
                "analyses": [],
            }
        groupes[cle]["analyses"].append(item)

    groupes = dict(sorted(groupes.items(), reverse=True))

    last_analyse = analyses.first()

    context = {
        "groupes": groupes,
        "last_analyse": last_analyse,
        "has_data": analyses.exists(),
        "filter_type": filter_type,
    }

    return render(request, "dashboard/historique_analyses.html", context)


@login_required
@require_POST
def supprimer_definitivement_analyse(request, analyse_id):
    import logging
    from django.contrib import messages

    logger = logging.getLogger(__name__)

    analyse = get_object_or_404(
        AnalyseSession, id=analyse_id, agence=request.user.agence
    )

    # Log audit suppression définitive
    logger.warning(
        f"ANALYSE_SUPPRESSION_DEFINITIVE: "
        f"user={request.user.username}({request.user.id}), "
        f"analyse_id={analyse.id}, "
        f"agence={analyse.agence.nom}, "
        f"methode={analyse.methode}, "
        f"nb_clients={analyse.nb_clients_total}"
    )

    analyse.delete()
    messages.success(request, "Analyse supprimée définitivement.")

    return redirect("dashboard:corbeille_analyses")


@login_required
@require_POST
def supprimer_analyses_mois(request, mois_cle):
    from django.contrib import messages
    from django.utils import timezone

    analyses = AnalyseSession.objects.filter(
        agence=request.user.agence, date_analyse__startswith=mois_cle, supprimee=False
    )
    count = analyses.count()
    analyses.update(supprimee=True, date_suppression=timezone.now())
    messages.success(request, f"{count} analyse(s) supprimée(s).")
    return redirect("dashboard:historique_analyses")


@login_required
def corbeille_analyses(request):
    analyses = AnalyseSession.objects.filter(
        agence=request.user.agence, supprimee=True
    ).order_by("-date_suppression")

    mois_fr = {
        1: "Janvier",
        2: "Février",
        3: "Mars",
        4: "Avril",
        5: "Mai",
        6: "Juin",
        7: "Juillet",
        8: "Août",
        9: "Septembre",
        10: "Octobre",
        11: "Novembre",
        12: "Décembre",
    }
    groupes = {}
    for analyse in analyses:
        dt = analyse.date_analyse
        cle = dt.strftime("%Y-%m")
        if cle not in groupes:
            groupes[cle] = {
                "label": f"{mois_fr[dt.month]} {dt.year}",
                "analyses": [],
            }
        groupes[cle]["analyses"].append(analyse)

    groupes = dict(sorted(groupes.items(), reverse=True))

    context = {
        "groupes": groupes,
        "has_data": analyses.exists(),
    }

    return render(request, "dashboard/corbeille_analyses.html", context)


@login_required
@require_POST
def restaurer_analyse(request, analyse_id):
    from django.contrib import messages

    analyse = get_object_or_404(
        AnalyseSession, id=analyse_id, agence=request.user.agence, supprimee=True
    )
    analyse.supprimee = False
    analyse.date_suppression = None
    analyse.save()
    messages.success(request, "Analyse restaurée.")
    return redirect("dashboard:corbeille_analyses")


@login_required
@require_POST
def bulk_restaurer_analyses(request):
    from django.contrib import messages

    analyse_ids = request.POST.getlist("analyse_ids")
    count = 0
    if analyse_ids:
        count = AnalyseSession.objects.filter(
            id__in=analyse_ids, agence=request.user.agence, supprimee=True
        ).update(supprimee=False, date_suppression=None)
    messages.success(request, f"{count} analyse(s) restaurée(s).")
    return redirect("dashboard:corbeille_analyses")


@login_required
@require_POST
def bulk_supprimer_definitivement_analyses(request):
    from django.contrib import messages

    analyse_ids = request.POST.getlist("analyse_ids")
    count = 0
    if analyse_ids:
        count = AnalyseSession.objects.filter(
            id__in=analyse_ids, agence=request.user.agence, supprimee=True
        ).delete()[0]
    messages.success(request, f"{count} analyse(s) supprimée(s) définitivement.")
    return redirect("dashboard:corbeille_analyses")


@login_required
def kpi_api_view(request):
    """API endpoint pour récupérer les KPIs actuels en JSON"""
    from django.http import JsonResponse
    from django.db.models import Avg
    from learning.models import ClientChurn

    clients = ClientChurn.objects.filter(dataset__agence=request.user.agence)
    total = clients.count()
    churn = clients.filter(churn_predit=True).count()
    non_churn = clients.filter(churn_predit=False).count()
    taux_churn = round(churn / total * 100, 1) if total > 0 else 0
    score_moyen = (clients.aggregate(Avg("score_churn"))["score_churn__avg"] or 0) * 100

    return JsonResponse(
        {
            "total_clients": total,
            "churn_count": churn,
            "non_churn_count": non_churn,
            "taux_churn": taux_churn,
            "score_moyen": round(score_moyen, 1),
        }
    )


@login_required
def notifications_api_view(request):
    from django.http import JsonResponse

    notifs = (
        Notification.objects.filter(
            destinataire=request.user, lu=False, archive=False, supprimee=False
        )
        .select_related("client", "recommandation")
        .order_by("-date_creation")[:15]
    )

    notif_data = []
    for notif in notifs:
        notif_data.append(
            {
                "id": notif.id,
                "titre": notif.titre,
                "contenu": (
                    notif.contenu[:55] + "..."
                    if len(notif.contenu) > 55
                    else notif.contenu
                ),
                "type_notif": notif.type_notif,
                "date_creation": notif.date_creation.strftime("%d/%m/%Y %H:%M"),
                "lu": notif.lu,
            }
        )

    return JsonResponse(
        {"nb_notifications": notifs.count(), "notifications": notif_data}
    )


@login_required
def notifications_view(request):
    user = request.user

    notifs = Notification.objects.filter(
        destinataire=user, archive=False, supprimee=False
    ).select_related("client", "recommandation")
    nb_non_lues = notifs.filter(lu=False).count()

    counts = {}
    for notif in notifs:
        counts[notif.type_notif] = counts.get(notif.type_notif, 0) + 1

    return render(
        request,
        "dashboard/notifications.html",
        {
            "notifications": notifs,
            "nb_notifs": notifs.count(),
            "nb_non_lues": nb_non_lues,
            "notif_counts": counts,
        },
    )


@login_required
def notification_detail_view(request, notif_id):
    notif = get_object_or_404(Notification, id=notif_id, destinataire=request.user)

    if not notif.lu:
        notif.lu = True
        notif.save(update_fields=["lu"])

    return render(request, "dashboard/notification_detail.html", {"notif": notif})


@login_required
def notifications_archivees_view(request):
    notifs = Notification.objects.filter(
        destinataire=request.user, archive=True, supprimee=False
    ).order_by("-date_creation")
    return render(
        request, "dashboard/notifications_archivees.html", {"notifications": notifs}
    )


@login_required
@require_POST
def completer_rec(request, rec_id):
    from dashboard.models import Notification
    from accounts.models import User

    # Alignement avec le workflow : l'agent marque "terminée" → le chef confirme.
    rec = get_object_or_404(
        Recommandation,
        id=rec_id,
        statut="active",
        client__agence=request.user.agence,
    )

    note = request.POST.get("note", "")
    rec.statut = "completee_agent"
    rec.assignee_a = request.user
    rec.note_agent = note
    rec.save()
    messages.success(
        request,
        "Recommandation marquée comme terminée. En attente de validation du chef d'agence.",
    )

    # Notifier le chef d'agence
    if request.user.agence:
        chef = User.objects.filter(
            agence=request.user.agence, role="chef_agence", statut="actif"
        ).first()
        if chef:
            Notification.objects.create(
                destinataire=chef,
                type_notif="validation_requise",
                titre=f"Validation complétion — {rec.client.nom}",
                contenu=(
                    f"L'agent {request.user.username} a marqué comme terminée une recommandation "
                    f"pour {rec.client.nom} ({rec.client.client_id})."
                ),
                lien=f"/clients/{rec.client.id}/#recommandations",
                client=rec.client,
                recommandation=rec,
            )

    return redirect(f"/clients/{rec.client.id}/#recommandations")


@login_required
@require_POST
def valider_completion_recommandation(request, rec_id):
    """
    Le chef valide/refuse la complétion proposée par un agent (statut=completee_agent).
    Si acceptée → completee (et le taux de complétion augmente).
    Si refusée → retour à active.
    """
    from core.notifications_engine import confirmer_completion

    rec = get_object_or_404(
        Recommandation, id=rec_id, client__dataset__agence=request.user.agence
    )

    if request.user.role != "chef_agence":
        messages.error(request, "Seul le chef d'agence peut valider la complétion.")
        return redirect(f"/clients/{rec.client.id}/#recommandations")

    if rec.statut != "completee_agent":
        messages.error(
            request, "Cette recommandation n'est pas en attente de validation."
        )
        return redirect(f"/clients/{rec.client.id}/#recommandations")

    action = request.POST.get("action")  # accepter/refuser
    note = request.POST.get("note", "").strip()

    if action == "accepter":
        confirmer_completion(rec, request.user, accepte=True, note=note)
        messages.success(request, "Complétion validée. La recommandation est clôturée.")
    elif action == "refuser":
        confirmer_completion(rec, request.user, accepte=False, note=note)
        messages.success(
            request, "Complétion refusée. La recommandation revient en actif."
        )
    else:
        messages.error(request, "Action invalide.")

    return redirect(f"/clients/{rec.client.id}/#recommandations")


@login_required
@require_POST
def action_recommandation(request, rec_id):
    rec = get_object_or_404(
        Recommandation,
        id=rec_id,
        client__agence=request.user.agence,
    )
    action = request.POST.get("action")

    if action == "completer" and rec.statut == "active":
        return completer_rec(request, rec_id)
    if action in ["retirer"] and request.user.role == "chef_agence":
        rec.statut = "retiree"
        rec.modifiee_par = request.user
        rec.save()
        messages.success(request, "Recommandation retirée.")

    return redirect(f"/clients/{rec.client.id}/#recommandations")


@login_required
def marquer_lu(request):
    Notification.objects.filter(
        destinataire=request.user, lu=False, archive=False
    ).update(lu=True)
    return redirect(request.META.get("HTTP_REFERER", "/"))


@login_required
@require_POST
def supprimer_notification(request, notif_id):
    notif = get_object_or_404(Notification, id=notif_id, destinataire=request.user)
    notif.supprimee = True
    notif.date_suppression = timezone.now()
    notif.save(update_fields=["supprimee", "date_suppression"])
    return redirect(request.META.get("HTTP_REFERER", "/"))


@login_required
@require_POST
def restaurer_notification(request, notif_id):
    notif = get_object_or_404(
        Notification, id=notif_id, destinataire=request.user, supprimee=True
    )
    notif.supprimee = False
    notif.date_suppression = None
    notif.save(update_fields=["supprimee", "date_suppression"])
    return redirect(request.META.get("HTTP_REFERER", "/"))


@login_required
def notifications_supprimees_view(request):
    notifs = Notification.objects.filter(
        destinataire=request.user, supprimee=True
    ).order_by("-date_suppression")
    return render(
        request, "dashboard/notifications_supprimees.html", {"notifications": notifs}
    )


@login_required
@require_POST
def supprimer_definitivement_notification(request, notif_id):
    notif = get_object_or_404(
        Notification, id=notif_id, destinataire=request.user, supprimee=True
    )
    notif.delete()
    return redirect(request.META.get("HTTP_REFERER", "/"))


@login_required
@require_POST
def bulk_delete_notifications(request):
    from django.contrib import messages

    notif_ids = request.POST.getlist("notif_ids")
    count = 0
    if notif_ids:
        count = Notification.objects.filter(
            id__in=notif_ids, destinataire=request.user, supprimee=False
        ).update(supprimee=True, date_suppression=timezone.now())
    messages.success(request, f"{count} notification(s) supprimée(s).")
    return redirect(request.META.get("HTTP_REFERER", "/"))


@login_required
@require_POST
def bulk_restore_notifications(request):
    from django.contrib import messages

    notif_ids = request.POST.getlist("notif_ids")
    count = 0
    if notif_ids:
        count = Notification.objects.filter(
            id__in=notif_ids, destinataire=request.user, supprimee=True
        ).update(supprimee=False, date_suppression=None)
    messages.success(request, f"{count} notification(s) restaurée(s).")
    return redirect(request.META.get("HTTP_REFERER", "/"))


@login_required
@require_POST
def bulk_hard_delete_notifications(request):
    from django.contrib import messages

    notif_ids = request.POST.getlist("notif_ids")
    count = 0
    if notif_ids:
        count = Notification.objects.filter(
            id__in=notif_ids, destinataire=request.user, supprimee=True
        ).delete()[0]
    messages.success(request, f"{count} notification(s) supprimée(s) définitivement.")
    return redirect(request.META.get("HTTP_REFERER", "/"))


@login_required
@require_POST
def archiver_notification(request, notif_id):
    notif = get_object_or_404(Notification, id=notif_id, destinataire=request.user)
    notif.archive = True
    notif.save(update_fields=["archive"])
    return redirect(request.META.get("HTTP_REFERER", "/"))


@login_required
@require_POST
def desarchiver_notification(request, notif_id):
    notif = get_object_or_404(Notification, id=notif_id, destinataire=request.user)
    notif.archive = False
    notif.save(update_fields=["archive"])
    return redirect(request.META.get("HTTP_REFERER", "/"))


@login_required
@require_POST
def marquer_lu_notification(request, notif_id):
    notif = get_object_or_404(Notification, id=notif_id, destinataire=request.user)
    notif.lu = True
    notif.save(update_fields=["lu"])
    return redirect(request.META.get("HTTP_REFERER", "/"))


@login_required
@require_POST
def creer_recommandation_agent(request, client_id):
    client = get_object_or_404(
        ClientChurn, id=client_id, dataset__agence=request.user.agence
    )

    if request.user.role not in ["agent_marketing", "agent_commercial", "chef_agence"]:
        messages.error(
            request, "Vous n'avez pas les droits pour créer une recommandation."
        )
        return redirect(f"/clients/{client.id}/#recommandations")

    type_rec = request.POST.get("type_recommandation")
    contenu = request.POST.get("contenu", "").strip()
    echeance = request.POST.get("echeance")

    if not contenu:
        messages.error(request, "Le contenu de la recommandation est obligatoire.")
        return redirect(f"/clients/{client.id}/#recommandations")

    if not type_rec:
        if request.user.role == "agent_marketing":
            type_rec = "marketing"
        elif request.user.role == "agent_commercial":
            type_rec = "commercial"
        else:
            type_rec = "technique"

    # Si c'est un agent, soumettre à validation du chef
    if request.user.role in ["agent_marketing", "agent_commercial"]:
        chef = User.objects.filter(
            agence=request.user.agence, role="chef_agence", statut="actif"
        ).first()
        if not chef:
            messages.error(
                request,
                "Aucun chef d'agence disponible pour valider votre recommandation.",
            )
            return redirect(f"/clients/{client.id}/#recommandations")

        rec = Recommandation.objects.create(
            client=client,
            type_recommandation=type_rec,
            contenu=contenu,
            echeance=echeance,
            statut="en_attente_validation",
            generee_par_systeme=False,
            cree_par=request.user,
        )

        # Notifier le chef d'agence
        Notification.objects.create(
            destinataire=chef,
            type_notif="validation_requise",
            titre=f"Validation recommandation — {client.nom}",
            contenu=f"{request.user.username} a créé une recommandation pour le client {client.nom} ({client.client_id}) : {contenu[:100]}...",
            lien=f"/clients/{client.id}/#recommandations",
            client=client,
            recommandation=rec,
            lu=False,
        )

        messages.success(
            request, "Recommandation soumise à validation du chef d'agence."
        )
    else:
        # Le chef peut créer directement
        rec = Recommandation.objects.create(
            client=client,
            type_recommandation=type_rec,
            contenu=contenu,
            echeance=echeance,
            statut="active",
            generee_par_systeme=False,
            cree_par=request.user,
        )

        messages.success(request, "Recommandation créée avec succès.")

    return redirect(f"/clients/{client.id}/#recommandations")


@login_required
@require_POST
def rejeter_recommandation(request, rec_id):
    """Vue pour qu'un agent puisse rejeter une recommandation avec explication"""
    from dashboard.models import RejetRecommandation

    rec = get_object_or_404(
        Recommandation, id=rec_id, client__agence=request.user.agence
    )

    if request.user.role not in ["agent_marketing", "agent_commercial", "chef_agence"]:
        messages.error(
            request, "Vous n'avez pas les droits pour rejeter une recommandation."
        )
        return redirect(f"/clients/{rec.client.id}/#recommandations")

    if rec.statut != "active":
        messages.error(
            request, "Seules les recommandations actives peuvent être rejetées."
        )
        return redirect(f"/clients/{rec.client.id}/#recommandations")

    # La demande de rejet (suppression) s'applique surtout aux recommandations automatiques.
    if not rec.generee_par_systeme:
        messages.error(
            request,
            "Le rejet avec suppression est réservé aux recommandations automatiques. "
            "Pour une recommandation manuelle, demandez au chef d'agence de la retirer.",
        )
        return redirect(f"/clients/{rec.client.id}/#recommandations")

    explication = request.POST.get("explication", "").strip()

    if not explication:
        messages.error(
            request, "L'explication est obligatoire pour rejeter une recommandation."
        )
        return redirect(f"/clients/{rec.client.id}/#recommandations")

    # Créer la demande de rejet
    rejet = RejetRecommandation.objects.create(
        recommandation=rec,
        demandeur=request.user,
        explication=explication,
        statut="en_attente",
    )

    # Notifier le chef d'agence
    chef = User.objects.filter(
        agence=request.user.agence, role="chef_agence", statut="actif"
    ).first()
    if chef:
        Notification.objects.create(
            destinataire=chef,
            type_notif="validation_requise",
            titre=f"Rejet de recommandation — {rec.client.nom}",
            contenu=f"{request.user.username} demande de rejeter la recommandation pour {rec.client.nom} ({rec.client.client_id}). Raison : {explication[:100]}...",
            lien=f"/clients/{rec.client.id}/#recommandations",
            client=rec.client,
            recommandation=rec,
            lu=False,
        )

    messages.success(request, "Votre demande de rejet a été soumise au chef d'agence.")
    return redirect(f"/clients/{rec.client.id}/#recommandations")


@login_required
@require_POST
def valider_creation_recommandation(request, rec_id):
    """Vue pour que le chef valide la création d'une recommandation"""
    rec = get_object_or_404(
        Recommandation, id=rec_id, client__dataset__agence=request.user.agence
    )

    if request.user.role != "chef_agence":
        messages.error(
            request, "Seul le chef d'agence peut valider les recommandations."
        )
        return redirect(f"/clients/{rec.client.id}/#recommandations")

    if rec.statut != "en_attente_validation":
        messages.error(
            request, "Cette recommandation n'est pas en attente de validation."
        )
        return redirect(f"/clients/{rec.client.id}/#recommandations")

    action = request.POST.get("action")  # "accepter" ou "refuser"
    note = request.POST.get("note", "").strip()

    if action == "accepter":
        rec.statut = "active"
        rec.modifiee_par = request.user
        rec.save()

        # Notifier l'agent qui a créé la recommandation
        if rec.cree_par:
            Notification.objects.create(
                destinataire=rec.cree_par,
                type_notif="validation_acceptee",
                titre=f"Recommandation acceptée — {rec.client.nom}",
                contenu=f"Votre recommandation pour {rec.client.nom} ({rec.client.client_id}) a été acceptée par le chef d'agence.",
                lien=f"/clients/{rec.client.id}/#recommandations",
                client=rec.client,
                recommandation=rec,
                lu=False,
            )

        messages.success(request, "Recommandation acceptée et notifiée à l'agent.")
    elif action == "refuser":
        rec.statut = "retiree"
        rec.modifiee_par = request.user
        rec.save()

        # Notifier l'agent qui a créé la recommandation
        if rec.cree_par:
            message_refus = f"Votre recommandation pour {rec.client.nom} ({rec.client.client_id}) a été refusée."
            if note:
                message_refus += f" Note : {note}"
            Notification.objects.create(
                destinataire=rec.cree_par,
                type_notif="validation_refusee",
                titre=f"Recommandation refusée — {rec.client.nom}",
                contenu=message_refus,
                lien=f"/clients/{rec.client.id}/#recommandations",
                client=rec.client,
                recommandation=rec,
                lu=False,
            )

        messages.success(request, "Recommandation refusée et notifiée à l'agent.")
    else:
        messages.error(request, "Action invalide.")
        return redirect(f"/clients/{rec.client.id}/#recommandations")

    return redirect(f"/clients/{rec.client.id}/#recommandations")


@login_required
@require_POST
def valider_rejet_recommandation(request, rejet_id):
    """Vue pour que le chef valide un rejet de recommandation"""
    from dashboard.models import RejetRecommandation

    rejet = get_object_or_404(
        RejetRecommandation,
        id=rejet_id,
        recommandation__client__dataset__agence=request.user.agence,
    )

    if request.user.role != "chef_agence":
        messages.error(request, "Seul le chef d'agence peut valider les rejets.")
        return redirect(f"/clients/{rejet.recommandation.client.id}/#recommandations")

    if rejet.statut != "en_attente":
        messages.error(request, "Ce rejet n'est pas en attente de validation.")
        return redirect(f"/clients/{rejet.recommandation.client.id}/#recommandations")

    action = request.POST.get("action")  # "accepter" ou "refuser"
    note_validation = request.POST.get("note_validation", "").strip()

    if action == "accepter":
        rejet.statut = "accepte"
        rejet.valide_par = request.user
        rejet.date_validation = timezone.now()
        rejet.note_validation = note_validation
        rejet.save()

        # Supprimer définitivement la recommandation
        rejet.recommandation.delete()

        # Notifier l'agent que le rejet a été accepté
        Notification.objects.create(
            destinataire=rejet.demandeur,
            type_notif="validation_acceptee",
            titre=f"Rejet accepté — {rejet.recommandation.client.nom}",
            contenu=f"Votre demande de rejet pour {rejet.recommandation.client.nom} ({rejet.recommandation.client.client_id}) a été acceptée. La recommandation a été supprimée.",
            lien=f"/clients/{rejet.recommandation.client.id}/#recommandations",
            client=rejet.recommandation.client,
            lu=False,
        )

        messages.success(request, "Rejet accepté et recommandation supprimée.")
    elif action == "refuser":
        rejet.statut = "refuse"
        rejet.valide_par = request.user
        rejet.date_validation = timezone.now()
        rejet.note_validation = note_validation
        rejet.save()

        # Notifier l'agent que le rejet a été refusé et qu'il doit exécuter la tâche
        message_refus = f"Votre demande de rejet pour {rejet.recommandation.client.nom} ({rejet.recommandation.client.client_id}) a été refusée. Vous devez exécuter cette recommandation."
        if note_validation:
            message_refus += f" Note du chef : {note_validation}"
        Notification.objects.create(
            destinataire=rejet.demandeur,
            type_notif="validation_refusee",
            titre=f"Rejet refusé — {rejet.recommandation.client.nom}",
            contenu=message_refus,
            lien=f"/clients/{rejet.recommandation.client.id}/#recommandations",
            client=rejet.recommandation.client,
            recommandation=rejet.recommandation,
            lu=False,
        )

        messages.success(
            request, "Rejet refusé. L'agent a été notifié d'exécuter la tâche."
        )
    else:
        return redirect("dashboard:accueil")


# ============================================================================
# VUES D'ADMINISTRATION
# ============================================================================


@login_required
def administration_view(request):
    """
    Vue d'administration pour gérer les comptes et les tables.
    Accessible uniquement aux chefs d'agence, admins ville et superadmins.
    """

    # Vérifier les permissions
    if not _can_manage_tables(request.user):
        messages.error(
            request, "Vous n'avez pas les permissions d'accéder à l'administration."
        )
        return redirect("dashboard:accueil")

    # Récupérer les utilisateurs à gérer uniquement si l'utilisateur peut gérer les comptes
    if _can_manage_users(request.user):
        if request.user.is_superuser:
            # Superuser voit tous les utilisateurs sauf lui-même
            users = User.objects.filter(is_superuser=False).select_related("agence")
        else:
            # Admin ville voit uniquement les utilisateurs de sa ville
            admin_ville = getattr(request.user, "admin_ville", None)
            if admin_ville and admin_ville.ville:
                users = User.objects.filter(agence__ville=admin_ville.ville).exclude(
                    id=request.user.id
                )
            else:
                users = User.objects.none()
    else:
        users = User.objects.none()

    # Statistiques des tables
    from learning.models import ClientChurn
    from dashboard.models import Notification, AnalyseSession, Recommandation

    stats = {
        "clients": ClientChurn.objects.count(),
        "notifications": Notification.objects.count(),
        "analyses": AnalyseSession.objects.count(),
        "recommandations": Recommandation.objects.count(),
        "users": User.objects.count(),
    }

    context = {
        "users": users,
        "stats": stats,
        "user_count": users.count(),
        "can_manage_users": _can_manage_users(request.user),
    }

    return render(request, "dashboard/administration.html", context)


@login_required
def toggle_user_active(request, user_id):
    """Active ou désactive un compte utilisateur."""
    from accounts.models import User

    if not _can_manage_users(request.user):
        messages.error(request, "Permission refusée.")
        return redirect("dashboard:administration")

    try:
        target_user = User.objects.get(id=user_id)

        # Vérifier que l'utilisateur ne modifie pas un superuser
        if target_user.is_superuser:
            messages.error(request, "Impossible de modifier un superutilisateur.")
            return redirect("dashboard:administration")

        # Admin ville ne peut modifier que les utilisateurs de sa ville
        if request.user.role == "admin":
            admin_ville = getattr(request.user, "admin_ville", None)
            if not admin_ville or not admin_ville.ville:
                messages.error(
                    request, "Impossible de vérifier la ville de l'administrateur."
                )
                return redirect("dashboard:administration")
            if not target_user.agence or target_user.agence.ville != admin_ville.ville:
                messages.error(
                    request, "Cet utilisateur n'appartient pas à votre ville."
                )
                return redirect("dashboard:administration")

        # Toggle le statut
        target_user.is_active = not target_user.is_active
        target_user.save()

        status = "activé" if target_user.is_active else "désactivé"
        messages.success(
            request, f"Compte de {target_user.email} {status} avec succès."
        )

    except User.DoesNotExist:
        messages.error(request, "Utilisateur non trouvé.")

    return redirect("dashboard:administration")


@login_required
def vider_table(request):
    """Vide une table spécifique de la base de données."""
    from django.http import JsonResponse

    if not _can_manage_tables(request.user):
        return JsonResponse({"success": False, "error": "Permission refusée"})

    if request.method == "POST":
        table_name = request.POST.get("table")

        try:
            count = 0

            if table_name == "clients":
                from learning.models import ClientChurn

                count = ClientChurn.objects.count()
                ClientChurn.objects.all().delete()
                message = f"{count} clients supprimés."

            elif table_name == "notifications":
                from dashboard.models import Notification

                count = Notification.objects.count()
                Notification.objects.all().delete()
                message = f"{count} notifications supprimées."

            elif table_name == "recommandations":
                from dashboard.models import Recommandation

                count = Recommandation.objects.count()
                Recommandation.objects.all().delete()
                message = f"{count} recommandations supprimées."

            elif table_name == "analyses":
                from dashboard.models import AnalyseSession

                count = AnalyseSession.objects.count()
                AnalyseSession.objects.all().delete()
                message = f"{count} sessions d'analyse supprimées."

            elif table_name == "evenements_cdr":
                from learning.models import EvenementCDR

                count = EvenementCDR.objects.count()
                EvenementCDR.objects.all().delete()
                message = f"{count} événements CDR supprimés."

            elif table_name == "interactions":
                from learning.models import InteractionDigitale

                count = InteractionDigitale.objects.count()
                InteractionDigitale.objects.all().delete()
                message = f"{count} interactions digitales supprimées."

            elif table_name == "all":
                # Vider toutes les tables (sauf users)
                from learning.models import (
                    ClientChurn,
                    EvenementCDR,
                    InteractionDigitale,
                    ValeursSHAPClient,
                )
                from dashboard.models import (
                    Notification,
                    AnalyseSession,
                    Recommandation,
                )

                counts = {
                    "clients": ClientChurn.objects.count(),
                    "evenements_cdr": EvenementCDR.objects.count(),
                    "interactions": InteractionDigitale.objects.count(),
                    "shap": ValeursSHAPClient.objects.count(),
                    "notifications": Notification.objects.count(),
                    "analyses": AnalyseSession.objects.count(),
                    "recommandations": Recommandation.objects.count(),
                }

                ClientChurn.objects.all().delete()
                EvenementCDR.objects.all().delete()
                InteractionDigitale.objects.all().delete()
                ValeursSHAPClient.objects.all().delete()
                Notification.objects.all().delete()
                AnalyseSession.objects.all().delete()
                Recommandation.objects.all().delete()

                total = sum(counts.values())
                message = f"Toutes les tables vidées ({total} enregistrements)."

            else:
                return JsonResponse({"success": False, "error": "Table inconnue"})

            return JsonResponse({"success": True, "message": message, "count": count})

        except Exception as e:
            return JsonResponse({"success": False, "error": str(e)})

    return JsonResponse({"success": False, "error": "Méthode non autorisée"})


@login_required
def reset_database(request):
    """Réinitialise complètement la base de données (supprime tout sauf superusers)."""
    from django.http import JsonResponse

    if not request.user.is_superuser:
        return JsonResponse(
            {"success": False, "error": "Permission refusée - Superuser requis"}
        )

    if request.method == "POST":
        try:
            from accounts.models import User
            from learning.models import (
                ClientChurn,
                EvenementCDR,
                InteractionDigitale,
                ValeursSHAPClient,
            )
            from dashboard.models import Notification, AnalyseSession, Recommandation

            # Compter avant suppression
            stats = {
                "clients": ClientChurn.objects.count(),
                "evenements_cdr": EvenementCDR.objects.count(),
                "interactions": InteractionDigitale.objects.count(),
                "shap": ValeursSHAPClient.objects.count(),
                "notifications": Notification.objects.count(),
                "analyses": AnalyseSession.objects.count(),
                "recommandations": Recommandation.objects.count(),
                "users": User.objects.filter(is_superuser=False).count(),
            }

            # Supprimer dans l'ordre (respecter les contraintes FK)
            Recommandation.objects.all().delete()
            Notification.objects.all().delete()
            ValeursSHAPClient.objects.all().delete()
            InteractionDigitale.objects.all().delete()
            EvenementCDR.objects.all().delete()
            AnalyseSession.objects.all().delete()
            ClientChurn.objects.all().delete()

            # Supprimer les utilisateurs non-superuser
            User.objects.filter(is_superuser=False).delete()

            total = sum(stats.values())

            return JsonResponse(
                {
                    "success": True,
                    "message": f"Base de données réinitialisée ({total} enregistrements supprimés)",
                    "stats": stats,
                }
            )

        except Exception as e:
            return JsonResponse({"success": False, "error": str(e)})

    return JsonResponse({"success": False, "error": "Méthode non autorisée"})


@login_required
def shap_explanation(request, client_id):
    from learning.models import ClientChurn
    from core.ml_service import get_shap_explanation

    try:
        client = get_object_or_404(ClientChurn, id=client_id)

        if (
            client.dataset.agence != request.user.agence
            and not request.user.is_superuser
        ):
            return JsonResponse({"error": "Accès non autorisé"}, status=403)

        shap_data = get_shap_explanation(client)

        if shap_data is None:
            return JsonResponse(
                {"error": "Impossible de générer l'explication SHAP"}, status=500
            )

        return JsonResponse(shap_data)

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)
