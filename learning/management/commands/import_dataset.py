import pandas as pd
import numpy as np
from datetime import datetime
from django.core.management.base import BaseCommand
from django.db import transaction
from learning.models import Dataset, ClientChurn
from accounts.models import Agence, User
from pathlib import Path

# Importer les fonctions de preprocessing du churn_pfe
from core.ml_service import pretraiter_dataframe, load_ml_model


class Command(BaseCommand):
    help = "Importe un dataset CSV réel avec preprocessing ML"

    def add_arguments(self, parser):
        parser.add_argument(
            "--file",
            type=str,
            help="Chemin vers le fichier CSV à importer",
            default="churn_pfe/dataset(s)/dataset_selected_features_clean_v3.csv",
        )
        parser.add_argument(
            "--agence", type=str, help="Nom de l'agence", default="Agence Kairouan"
        )
        parser.add_argument(
            "--user",
            type=str,
            help="Username de l'utilisateur qui charge",
            default="admin",
        )

    def handle(self, *args, **options):  # Charger le modèle ML
        load_ml_model()
        file_path = Path(options["file"])
        if not file_path.exists():
            self.stdout.write(self.style.ERROR(f"Fichier non trouvé: {file_path}"))
            return

        try:
            agence = Agence.objects.get(nom=options["agence"])
        except Agence.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f'Agence non trouvée: {options["agence"]}')
            )
            return

        try:
            user = User.objects.get(username=options["user"])
        except User.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f'Utilisateur non trouvé: {options["user"]}')
            )
            return

        self.stdout.write(f"Chargement du dataset: {file_path}")

        # Lire le CSV
        df = pd.read_csv(file_path)

        # Appliquer le preprocessing ML
        self.stdout.write("Application du preprocessing ML...")
        df_processed = pretraiter_dataframe(df.copy())

        # Créer le dataset
        with transaction.atomic():
            dataset = Dataset.objects.create(
                nom=f"Dataset réel - {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                methode="csv",
                agence=agence,
                charge_par=user,
                nb_clients=len(df),
                actif=True,
            )

            # Importer les clients
            clients_crees = 0
            for idx, row in df.iterrows():
                try:
                    # Convertir les dates
                    date_naissance = None
                    if pd.notna(row.get("date_naissance")):
                        try:
                            date_naissance = pd.to_datetime(
                                row["date_naissance"]
                            ).date()
                        except:
                            pass

                    date_debut = None
                    if pd.notna(row.get("date_debut_abonnement")):
                        try:
                            date_debut = pd.to_datetime(
                                row["date_debut_abonnement"]
                            ).date()
                        except:
                            pass

                    date_consentement = None
                    if pd.notna(row.get("date_consentement")):
                        try:
                            date_consentement = pd.to_datetime(
                                row["date_consentement"]
                            ).date()
                        except:
                            pass

                    # Créer le client
                    client = ClientChurn.objects.create(
                        dataset=dataset,
                        # Infos client
                        client_id=str(row.get("client_id", f"client_{idx}")),
                        nom=row.get("nom_client", ""),
                        genre_client=row.get("genre_client", ""),
                        date_naissance=date_naissance,
                        telephone=str(row.get("num_tel_mobile", "")),
                        email=row.get("adresse_email", ""),
                        adresse_physique=row.get("adresse_physique", ""),
                        identifiant_national=str(row.get("identifiant_national", "")),
                        # Dates et statut
                        date_debut_abonnement=date_debut,
                        statut_actif=bool(row.get("statut_actif", True)),
                        date_consentement=date_consentement,
                        consentement_marketing=bool(
                            row.get("consentement_marketing", False)
                        ),
                        optout_marketing=bool(row.get("optout_marketing", False)),
                        # Tenure
                        tenure_jours=int(row.get("tenure_jours", 0)),
                        tenure_mois=float(row.get("tenure_mois", 0)),
                        # Profil contractuel
                        type_abonnement=row.get("type_abonnement", "prepaye"),
                        plan_tarifaire=row.get("plan_tarifaire", ""),
                        facture_moyenne_mensuelle=float(
                            row.get("facture_moyenne_mensuelle", 0)
                        ),
                        moyen_paiement=row.get("moyen_paiement", ""),
                        # Usage télécom
                        nb_appels=int(row.get("nb_appels", 0)),
                        duree_appel_totale_sec=int(
                            row.get("duree_appel_totale_sec", 0)
                        ),
                        duree_appel_moyenne_sec=float(
                            row.get("duree_appel_moyenne_sec", 0)
                        ),
                        sms_total=int(row.get("sms_total", 0)),
                        data_totale_mb=float(row.get("data_totale_gb", 0))
                        * 1024,  # Convertir GB en MB
                        nb_evenements_data_cdr=int(
                            row.get("nb_evenements_data_cdr", 0)
                        ),
                        # Tendance
                        data_mois_M=(
                            float(row.get("data_mois_M", 0))
                            if pd.notna(row.get("data_mois_M"))
                            else None
                        ),
                        data_mois_M1=(
                            float(row.get("data_mois_M1", 0))
                            if pd.notna(row.get("data_mois_M1"))
                            else None
                        ),
                        tendance_data=float(row.get("tendance_data_pct", 0)),
                        # Engagement digital
                        nb_sessions=int(row.get("nb_sessions", 0)),
                        duree_session_moyenne_sec=float(
                            row.get("duree_session_moyenne_sec", 0)
                        ),
                        recence_session_jours=(
                            int(row.get("recence_session_jours", 0))
                            if pd.notna(row.get("recence_session_jours"))
                            else None
                        ),
                        taux_cookies=float(row.get("taux_cookies", 0)),
                        # Qualité et satisfaction
                        zone_reseau_principale=row.get("zone_reseau_principale", ""),
                        qualite_signal_dominante=row.get(
                            "qualite_signal_dominante", ""
                        ),
                        score_qualite_zone=float(row.get("score_qualite_zone", 0)),
                        satisfaction_client=(
                            float(row.get("satisfaction_client", 0))
                            if pd.notna(row.get("satisfaction_client"))
                            else None
                        ),
                        score_frustration=float(row.get("score_frustration", 0)),
                        # Autres
                        nb_reclamations=(
                            int(row.get("nb_reclamations", 0))
                            if pd.notna(row.get("nb_reclamations"))
                            else None
                        ),
                        reclamation_manquante=bool(
                            row.get("reclamation_manquante", False)
                        ),
                        recence_cdr_jours=(
                            int(row.get("recence_cdr_jours", 0))
                            if pd.notna(row.get("recence_cdr_jours"))
                            else None
                        ),
                    )

                    clients_crees += 1

                    if clients_crees % 100 == 0:
                        self.stdout.write(f"{clients_crees} clients importés...")

                except Exception as e:
                    self.stdout.write(
                        self.style.WARNING(f"Erreur pour client {idx}: {str(e)}")
                    )
                    continue

            self.stdout.write(
                self.style.SUCCESS(
                    f"Dataset importé avec succès: {clients_crees} clients créés"
                )
            )
            self.stdout.write(f"ID du dataset: {dataset.id}")
