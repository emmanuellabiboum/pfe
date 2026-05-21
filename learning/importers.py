# import pandas as pd  # Déplacé dans les fonctions
from django.core.files.uploadedfile import UploadedFile
from learning.models import Dataset, ClientChurn


def _parse_bool(value, default=False):
    import pandas as pd

    if pd.isna(value):
        return default
    if isinstance(value, bool):
        return value
    value_str = str(value).strip().lower()
    return value_str in ["1", "true", "t", "yes", "y", "oui", "vrai", "on"]


def _parse_int(value, default=0):
    import pandas as pd

    if pd.isna(value):
        return default
    try:
        return int(float(value))
    except Exception:
        return default


def _parse_float(value, default=0.0):
    import pandas as pd

    if pd.isna(value):
        return default
    try:
        return float(value)
    except Exception:
        return default


def _first_present(row, *names, default=None):
    import pandas as pd

    for name in names:
        if name in row and pd.notna(row.get(name)):
            return row.get(name)
    return default


def _parse_name(row, idx):
    value = _first_present(row, "nom_client", "nom", "client_nom", "name")
    if value is None or str(value).strip() == "":
        client_id = _first_present(row, "client_id", "id_client", "id", default=idx + 1)
        return f"Client_{client_id}"
    return str(value).strip()


def _parse_nb_reclamations(row):
    import pandas as pd

    value = _first_present(
        row,
        "nb_reclamations",
        "nombre_reclamations",
        "reclamations",
        "nb_reclamation",
    )
    if value is not None:
        return _parse_int(value)

    if _parse_bool(row.get("reclamation_manquante", False), default=False):
        return None

    score_frustration = _first_present(row, "score_frustration")
    satisfaction = _first_present(row, "satisfaction_client")
    if score_frustration is not None and satisfaction is not None:
        satisfaction_f = _parse_float(satisfaction, default=0)
        denom = 6 - satisfaction_f
        if denom > 0:
            return max(
                0, int(round(_parse_float(score_frustration, default=0) / denom))
            )

    return None


def _parse_date(value):
    import pandas as pd

    if pd.isna(value) or value is None:
        return None
    try:
        return pd.to_datetime(value).date()
    except Exception:
        return None


def create_dataset_from_dataframe(df, agence, user, uploaded_file: UploadedFile = None):
    import pandas as pd

    if uploaded_file is not None:
        uploaded_file.seek(0)

    # Conserver les anciens datasets CSV historiques en les désactivant.
    Dataset.objects.filter(agence=agence, methode="csv", actif=True).update(actif=False)

    dataset = Dataset.objects.create(
        nom=f"Dataset uploadé - {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}",
        methode="csv",
        agence=agence,
        charge_par=user,
        nb_clients=len(df),
        actif=True,
    )

    if uploaded_file is not None:
        # Éviter les doublons de fichiers : supprimer l'ancien fichier s'il existe
        if dataset.fichier:
            dataset.fichier.delete(save=False)
        dataset.fichier.save(uploaded_file.name, uploaded_file, save=True)

    clients_crees = 0
    clients_list = []
    erreurs_import = []

    for idx, row in df.iterrows():
        try:
            date_naissance = _parse_date(row.get("date_naissance"))
            date_debut = _parse_date(row.get("date_debut_abonnement"))
            date_consentement = _parse_date(row.get("date_consentement"))

            client = ClientChurn.objects.create(
                dataset=dataset,
                client_id=str(
                    _first_present(
                        row, "client_id", "id_client", "id", default=f"client_{idx}"
                    )
                ),
                nom=_parse_name(row, idx),
                genre_client=row.get("genre_client", ""),
                date_naissance=date_naissance,
                telephone=str(row.get("num_tel_mobile", "")),
                email=row.get("adresse_email", ""),
                adresse_physique=row.get("adresse_physique", ""),
                identifiant_national=str(row.get("identifiant_national", "")),
                date_debut_abonnement=date_debut,
                statut_actif=_parse_bool(row.get("statut_actif", True), default=True),
                date_consentement=date_consentement,
                consentement_marketing=_parse_bool(
                    row.get("consentement_marketing", False), default=False
                ),
                optout_marketing=_parse_bool(
                    row.get("optout_marketing", False), default=False
                ),
                tenure_jours=_parse_int(row.get("tenure_jours", 0)),
                tenure_mois=_parse_float(row.get("tenure_mois", 0)),
                type_abonnement=row.get("type_abonnement", ""),
                plan_tarifaire=row.get("plan_tarifaire", ""),
                facture_moyenne_mensuelle=_parse_float(
                    row.get("facture_moyenne_mensuelle", 0)
                ),
                moyen_paiement=row.get("moyen_paiement", ""),
                nb_appels=_parse_int(row.get("nb_appels", 0)),
                duree_appel_totale_sec=_parse_int(row.get("duree_appel_totale_sec", 0)),
                duree_appel_moyenne_sec=_parse_float(
                    row.get("duree_appel_moyenne_sec", 0)
                ),
                sms_total=_parse_int(row.get("sms_total", 0)),
                data_totale_mb=_parse_float(
                    row.get("data_totale_gb", row.get("data_moyenne_gb", 0))
                )
                * 1024,
                nb_evenements_data_cdr=_parse_int(row.get("nb_evenements_total", 0)),
                data_mois_M=(
                    _parse_float(row.get("data_mois_M", None))
                    if pd.notna(row.get("data_mois_M"))
                    else None
                ),
                data_mois_M1=(
                    _parse_float(row.get("data_mois_M1", None))
                    if pd.notna(row.get("data_mois_M1"))
                    else None
                ),
                tendance_data=_parse_float(row.get("tendance_data_pct", 0)),
                nb_sessions=_parse_int(row.get("nb_sessions", 0)),
                duree_session_moyenne_sec=_parse_float(
                    row.get("duree_session_moyenne_sec", 0)
                ),
                recence_session_jours=(
                    _parse_int(row.get("recence_session_jours", None))
                    if pd.notna(row.get("recence_session_jours"))
                    else None
                ),
                taux_cookies=_parse_float(row.get("taux_cookies", 0)),
                zone_reseau_principale=row.get("zone_reseau_principale", ""),
                qualite_signal_dominante=row.get("qualite_signal_dominante", ""),
                score_qualite_zone=_parse_float(row.get("score_qualite_zone", 0)),
                satisfaction_client=(
                    _parse_float(row.get("satisfaction_client", 0))
                    if pd.notna(row.get("satisfaction_client"))
                    else None
                ),
                score_frustration=_parse_float(row.get("score_frustration", 0)),
                nb_reclamations=_parse_nb_reclamations(row),
                reclamation_manquante=_parse_bool(
                    row.get("reclamation_manquante", False), default=False
                ),
                recence_cdr_jours=(
                    _parse_int(row.get("recence_cdr_jours", None))
                    if pd.notna(row.get("recence_cdr_jours"))
                    else None
                ),
                anciennete_mois=_parse_int(row.get("tenure_mois", 0)),
                consommation_moyenne=_parse_float(
                    row.get("data_moyenne_gb", row.get("data_totale_gb", 0))
                )
                * 1024,
                retards_paiement=0,
                nb_services=1,
                flag_offre_data=(
                    1
                    if _parse_float(
                        row.get("data_moyenne_gb", row.get("data_totale_gb", 0))
                    )
                    > 0
                    else 0
                ),
                flag_offre_voix=(
                    1 if _parse_float(row.get("duree_appel_moyenne_sec", 0)) > 0 else 0
                ),
                data_mois_m_manquante=1 if pd.isna(row.get("data_mois_M")) else 0,
                data_mois_m1_manquante=1 if pd.isna(row.get("data_mois_M1")) else 0,
            )
            clients_list.append(client)
            clients_crees += 1
        except Exception as e:
            if len(erreurs_import) < 5:
                erreurs_import.append(f"Ligne {idx + 1}: {str(e)}")
            continue

    if clients_crees == 0:
        details = (
            " | ".join(erreurs_import)
            if erreurs_import
            else "Aucun client valide trouvé."
        )
        raise ValueError(f"Import CSV échoué: 0 client créé. Détails: {details}")

    dataset.nb_clients = clients_crees
    dataset.save(update_fields=["nb_clients"])

    # NOTE : les prédictions ML ne sont PAS faites ici pendant l'import.
    # L'import est instantané ; les scores sont calculés plus tard par
    # lancer_analyse() qui appelle l'API FastAPI en batch (beaucoup plus rapide
    # que 300 requêtes unitaires).
    # Les clients auront score_churn=0 et churn_predit=False (ou RGS-90 si
    # recence_cdr_jours est renseigné) jusqu'au lancement de l'analyse.

    return dataset, clients_crees
