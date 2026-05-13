"""
generator.py — Générateur de données synthétiques Tunisie Télécom
Usage :
    python generator.py --n_clients 500 --churn_rate 0.30 --output dataset.csv
    python generator.py --n_clients 300 --seed 42 --output dataset.csv --format sql
"""

import argparse
import datetime
import numpy as np
import pandas as pd
from pathlib import Path


# ══════════════════════════════════════════════════════════════════════════════
# 1. PARAMÈTRES EN LIGNE DE COMMANDE
# ══════════════════════════════════════════════════════════════════════════════

def parse_arguments():
    """
    Définit et lit les paramètres d'entrée du script.
    Tous les paramètres ont une valeur par défaut pour un usage simple.
    """
    parser = argparse.ArgumentParser(
        description="Générateur de données synthétiques clients Tunisie Télécom",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    parser.add_argument(
        "--n_clients", type=int, default=300,
        help="Nombre de clients à générer"
    )
    parser.add_argument(
        "--churn_rate", type=float, default=0.27,
        help="Taux de churn cible (entre 0.0 et 1.0). "
             "Contrôle le seuil d'inactivité CDR appliqué."
    )
    parser.add_argument(
        "--seed", type=int, default=42,
        help="Graine aléatoire pour la reproductibilité"
    )
    parser.add_argument(
        "--output", type=str, default="dataset_pfe_genere.csv",
        help="Chemin du fichier de sortie (CSV ou SQLite selon --format)"
    )
    parser.add_argument(
        "--format", type=str, choices=["csv", "sql"], default="csv",
        help="Format d'export : 'csv' (défaut) ou 'sql' (SQLite)"
    )
    parser.add_argument(
        "--start_date", type=str, default="2020-01-01",
        help="Date de début des abonnements (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--extraction_date", type=str, default="2025-01-01",
        help="Date d'extraction / date de référence (YYYY-MM-DD)"
    )

    return parser.parse_args()


# ══════════════════════════════════════════════════════════════════════════════
# 2. GÉNÉRATION DES CLIENTS (TABLE DE BASE)
# ══════════════════════════════════════════════════════════════════════════════

def generate_base_clients(n_clients, start_date, date_extraction):
    """
    Génère les informations de base de chaque client :
    identité, abonnement, préférences marketing.

    Paramètres
    ----------
    n_clients       : int — nombre de clients
    start_date      : pd.Timestamp — date de début des abonnements
    date_extraction : pd.Timestamp — date de référence

    Retourne
    --------
    pd.DataFrame — table clients de base
    """

    # ── Facture mensuelle par segment tarifaire (distribution continue) ──────
    def generer_facture():
        segment = np.random.choice([0, 1, 2], p=[0.70, 0.20, 0.10])
        bornes = [(5, 25), (30, 60), (70, 160)]
        return np.round(np.random.uniform(*bornes[segment]), 2)

    # ── Cohérence âge / date d'abonnement ────────────────────────────────────
    start_birth = pd.to_datetime("1945-01-01")
    end_birth   = pd.to_datetime("2007-01-01")
    diff_days   = (end_birth - start_birth).days

    dates_abo = [
        start_date + pd.Timedelta(days=np.random.randint(0, 1461))
        for _ in range(n_clients)
    ]

    dates_naissance = []
    for date_abo in dates_abo:
        while True:
            dn = start_birth + pd.Timedelta(days=np.random.randint(0, diff_days))
            if (date_abo - dn).days / 365.25 >= 18:
                dates_naissance.append(dn)
                break

    # ── Variables pré-calculées ───────────────────────────────────────────────
    satisfaction_initiale = np.random.randint(1, 6, n_clients)
    statut_actif = np.random.choice([True, False], n_clients, p=[0.7, 0.3])
    consentement = np.random.choice([True, False], n_clients, p=[0.6, 0.4])
    optout = [
        np.random.choice([True, False], p=[0.2, 0.8]) if c else False
        for c in consentement
    ]

    clients = pd.DataFrame({
        "client_id"            : range(1, n_clients + 1),
        "nom_client"           : [f"Client_{i}" for i in range(1, n_clients + 1)],
        "genre_client"         : np.random.choice(["Homme", "Femme"], n_clients),
        "date_naissance"       : dates_naissance,
        "adresse_email"        : [
            f"client_{i}@{np.random.choice(['gmail.com','outlook.fr','yahoo.com','tunisietelecom.tn'])}"
            for i in range(1, n_clients + 1)
        ],
        "num_tel_mobile"       : [
            f"+216{np.random.choice([2,4,5,9])}{np.random.randint(1000000, 9999999)}"
            for _ in range(n_clients)
        ],
        "adresse_physique"     : [f"Adresse_{i}" for i in range(1, n_clients + 1)],
        "identifiant_national" : [
            f"{np.random.randint(0, 2)}{np.random.randint(1000000, 9999999):07d}"
            for _ in range(n_clients)
        ],
        "type_abonnement"      : np.random.choice(
            ["Offre Prépayée", "Offre à Facture"], n_clients, p=[0.85, 0.15]
        ),
        "plan_tarifaire"       : np.random.choice(
            ["Offre Classique", "Forfait Mobile (Mixte)", "Forfait Illimité"],
            n_clients, p=[0.70, 0.20, 0.10]
        ),
        "date_debut_abonnement": dates_abo,
        "statut_actif"         : statut_actif,
        "moyen_paiement"       : np.random.choice(
            ["ticket_recharge", "especes", "prelevement_bancaire"],
            n_clients, p=[0.75, 0.15, 0.10]
        ),
        "facture_moyenne_mensuelle": [generer_facture() for _ in range(n_clients)],
        "satisfaction_client"  : [
            s if actif else np.random.randint(1, 3)
            for s, actif in zip(satisfaction_initiale, statut_actif)
        ],
        "date_consentement"    : [
            d + pd.Timedelta(days=np.random.randint(0, 365)) if c else pd.NaT
            for d, c in zip(dates_abo, consentement)
        ],
        "consentement_marketing": consentement,
        "optout_marketing"      : optout,
    })

    clients["tenure_jours"] = (date_extraction - clients["date_debut_abonnement"]).dt.days
    clients["tenure_mois"]  = (clients["tenure_jours"] / 30.44).astype(int)

    return clients


# ══════════════════════════════════════════════════════════════════════════════
# 3. GÉNÉRATION DES ÉVÉNEMENTS CDR (USAGE TÉLÉCOM)
# ══════════════════════════════════════════════════════════════════════════════

def generate_cdr_events(clients, date_extraction):
    """
    Génère les événements d'usage télécom (appels, SMS, data mobile)
    et les agrège par client.

    Retourne
    --------
    tuple : (usage_brut, resume_usage) — événements bruts + agrégation par client
    """
    plan_config = {
        "Offre Classique"        : {"lambda_base": 20, "data_mu": 1.5},
        "Forfait Mobile (Mixte)" : {"lambda_base": 30, "data_mu": 2.0},
        "Forfait Illimité"       : {"lambda_base": 45, "data_mu": 2.8},
    }

    events = []
    for _, c in clients.iterrows():
        config = plan_config[c.plan_tarifaire]
        n_ev = np.random.poisson(
            config["lambda_base"] if c.statut_actif
            else max(1, config["lambda_base"] // 5)
        )

        delta_max = max(1, (date_extraction - c.date_debut_abonnement).days)

        for _ in range(n_ev):
            timestamp = c.date_debut_abonnement + pd.to_timedelta(
                np.random.randint(0, delta_max), unit="d"
            )
            timestamp += pd.to_timedelta(np.random.randint(0, 86400), unit="s")

            type_ev = np.random.choice(["appel", "sms", "donnee_mobile"], p=[0.4, 0.3, 0.3])

            if type_ev != "donnee_mobile":
                dest = f"+216{np.random.choice([2,4,5,9])}{np.random.randint(1000000, 9999999)}"
            else:
                dest = "INTERNET"

            ev = {
                "client_id"         : c.client_id,
                "date_heure"        : timestamp,
                "type_evenement"    : type_ev,
                "numero_source"     : c.num_tel_mobile,
                "numero_destination": dest,
                "duree_appel_sec"   : int(np.random.exponential(180)) if type_ev == "appel" else 0,
                "sms_compte"        : 1 if type_ev == "sms" else 0,
                "data_mb"           : np.round(
                    np.random.lognormal(config["data_mu"], 1.0), 2
                ) if type_ev == "donnee_mobile" else 0,
            }
            events.append(ev)

    usage = pd.DataFrame(events).sort_values("date_heure").reset_index(drop=True)

    # ── Agrégation ────────────────────────────────────────────────────────────
    resume = usage.groupby("client_id").agg(
        duree_appel_totale_sec  = ("duree_appel_sec", "sum"),
        duree_appel_moyenne_sec = ("duree_appel_sec", lambda x: (x[x>0].sum()/(x>0).sum()) if (x>0).any() else 0),
        nb_appels               = ("duree_appel_sec", lambda x: (x>0).sum()),
        sms_total               = ("sms_compte",      "sum"),
        data_totale_mb          = ("data_mb",          "sum"),
        data_moyenne_mb         = ("data_mb",          lambda x: (x[x>0].sum()/(x>0).sum()) if (x>0).any() else 0),
        nb_evenements_data_cdr  = ("type_evenement",  lambda x: (x=="donnee_mobile").sum()),
        nb_evenements_total     = ("type_evenement",  "count"),
        date_dernier_evenement  = ("date_heure",       "max"),
    ).reset_index()

    resume["recence_cdr_jours"] = (date_extraction - resume["date_dernier_evenement"]).dt.days
    resume = resume.drop(columns=["date_dernier_evenement"])

    return usage, resume


# ══════════════════════════════════════════════════════════════════════════════
# 4. GÉNÉRATION DES SESSIONS INTERNET
# ══════════════════════════════════════════════════════════════════════════════

def generate_sessions(clients, date_extraction):
    """
    Génère les sessions applicatives (MyTT, navigateur mobile)
    et les agrège par client.
    """
    dispositifs   = [("Android","Android 13"),("Android","Android 12"),
                     ("iOS","iOS 17"),("iOS","iOS 16"),("FeaturePhone","Proprietary")]
    p_dispositifs = [0.42, 0.28, 0.08, 0.05, 0.17]

    def get_navigateur(t):
        if t == "iOS":          return np.random.choice(["Safari","Chrome"], p=[0.70,0.30])
        if t == "FeaturePhone": return "Navigateur intégré"
        return np.random.choice(["Chrome","Samsung Browser"], p=[0.75,0.25])

    def get_version_mytt(t):
        if t == "FeaturePhone": return "Non applicable"
        return np.random.choice(["3.1.0","3.0.5","2.9.0"], p=[0.65,0.25,0.10])

    catalogue = ["google.com","facebook.com","tunisietelecom.tn",
                 "tayara.tn","youtube.com","instagram.com","tiktok.com"]

    rows = []
    for _, c in clients.iterrows():
        n_sess  = max(1, np.random.poisson(8 if c.statut_actif else 2))
        consent = clients.loc[clients.client_id == c.client_id, "consentement_marketing"].values[0]
        delta   = max(1, (date_extraction - c.date_debut_abonnement).days)

        for _ in range(n_sess):
            idx_d  = np.random.choice(len(dispositifs), p=p_dispositifs)
            type_app, sys_exp = dispositifs[idx_d]
            ts     = c.date_debut_abonnement + pd.Timedelta(days=int(np.random.randint(0, delta)))
            duree  = int(np.clip(np.random.lognormal(5.2, 1.1), 30, 7200))
            n_dom  = np.random.randint(1, min(6, len(catalogue)+1))
            domaines = ";".join(np.random.choice(catalogue, n_dom, replace=False))
            p_cookie = 0.80 if consent else 0.35

            rows.append({
                "client_id"            : c.client_id,
                "date_heure_session"   : ts,
                "adresse_IP"           : f"197.{np.random.randint(0,5)}.{np.random.randint(0,255)}.{np.random.randint(1,255)}",
                "type_appareil"        : type_app,
                "systeme_exploitation" : sys_exp,
                "version_app_MyTT"     : get_version_mytt(type_app),
                "duree_session_sec"    : duree,
                "historique_domaines"  : domaines,
                "navigateur"           : get_navigateur(type_app),
                "cookies_acceptes"     : np.random.choice([True,False], p=[p_cookie, 1-p_cookie]),
            })

    sessions = pd.DataFrame(rows).sort_values("date_heure_session").reset_index(drop=True)

    resume = sessions.groupby("client_id").agg(
        nb_sessions               = ("duree_session_sec", "count"),
        duree_session_moyenne_sec = ("duree_session_sec", "mean"),
        duree_session_totale_sec  = ("duree_session_sec", "sum"),
        taux_cookies              = ("cookies_acceptes",  "mean"),
        date_derniere_session     = ("date_heure_session","max"),
    ).reset_index()

    resume["recence_session_jours"] = (date_extraction - resume["date_derniere_session"]).dt.days
    resume = resume.drop(columns=["date_derniere_session"])

    return resume


# ══════════════════════════════════════════════════════════════════════════════
# 5. GÉNÉRATION DES LOCALISATIONS
# ══════════════════════════════════════════════════════════════════════════════

def generate_locations(clients, date_extraction):
    """
    Génère les points de connexion géolocalisés et les agrège par client.
    """
    zones_config = {
        "URBAIN"   : {"lat":(35.8,37.2),"lon":(9.8,10.8), "p_signal":[0.60,0.35,0.05]},
        "SUBURBAIN": {"lat":(34.5,35.8),"lon":(8.5,10.5), "p_signal":[0.30,0.50,0.20]},
        "RURAL"    : {"lat":(30.0,34.5),"lon":(7.5, 9.5), "p_signal":[0.10,0.40,0.50]},
    }

    rows = []
    for _, c in clients.iterrows():
        zone  = np.random.choice(["URBAIN","SUBURBAIN","RURAL"], p=[0.60,0.30,0.10])
        cfg   = zones_config[zone]
        n_loc = max(1, np.random.poisson(6 if c.statut_actif else 2))
        delta = max(1, (date_extraction - c.date_debut_abonnement).days)

        plan_eff = c.plan_tarifaire
        if zone == "RURAL" and plan_eff == "Forfait Illimité":
            plan_eff = np.random.choice(["Forfait Mobile (Mixte)","Offre Classique"], p=[0.4,0.6])

        for _ in range(n_loc):
            rows.append({
                "client_id"            : c.client_id,
                "date_heure_connexion" : c.date_debut_abonnement + pd.Timedelta(days=int(np.random.randint(0, delta))),
                "latitude_connexion"   : np.round(np.random.uniform(*cfg["lat"]), 6),
                "longitude_connexion"  : np.round(np.random.uniform(*cfg["lon"]), 6),
                "zone_reseau"          : zone,
                "qualite_signal"       : np.random.choice(["Excellent","Bon","Faible"], p=cfg["p_signal"]),
                "plan_effectif_zone"   : plan_eff,
            })

    locations = pd.DataFrame(rows).sort_values("date_heure_connexion").reset_index(drop=True)

    resume = locations.groupby("client_id").agg(
        zone_reseau_principale   = ("zone_reseau",          lambda x: x.mode()[0]),
        qualite_signal_dominante = ("qualite_signal",       lambda x: x.mode()[0]),
        latitude_moyenne         = ("latitude_connexion",   "mean"),
        longitude_moyenne        = ("longitude_connexion",  "mean"),
    ).reset_index()

    return resume


# ══════════════════════════════════════════════════════════════════════════════
# 6. ASSEMBLAGE DU DATASET FINAL + RÈGLE CHURN
# ══════════════════════════════════════════════════════════════════════════════

def assemble_dataset(clients, resume_usage, resume_sessions, resume_locations,
                     usage_brut, date_extraction, seuil_inactivite=90):
    """
    Fusionne toutes les tables, impute les NaN, applique la règle churn
    et ajoute les features engineerées.
    """
    df = (clients
          .merge(resume_usage,     on="client_id", how="left")
          .merge(resume_sessions,  on="client_id", how="left")
          .merge(resume_locations, on="client_id", how="left"))

    # ── Imputation des NaN post-merge ─────────────────────────────────────────
    cols_zero_usage    = ["duree_appel_totale_sec","duree_appel_moyenne_sec","nb_appels",
                          "sms_total","data_totale_mb","data_moyenne_mb",
                          "nb_evenements_total","nb_evenements_data_cdr"]
    cols_zero_sessions = ["nb_sessions","duree_session_moyenne_sec",
                          "duree_session_totale_sec","taux_cookies","recence_session_jours"]

    df[cols_zero_usage]    = df[cols_zero_usage].fillna(0)
    df[cols_zero_sessions] = df[cols_zero_sessions].fillna(0)
    df["recence_cdr_jours"] = df["recence_cdr_jours"].fillna(df["tenure_jours"])

    # ── Règle churn métier ────────────────────────────────────────────────────
    df["churn"] = (df["recence_cdr_jours"] >= seuil_inactivite).astype(int)

    # ── Cohérence offre / consommation ───────────────────────────────────────
    mask_classique = df["plan_tarifaire"] == "Offre Classique"
    df.loc[mask_classique, ["data_totale_mb","data_moyenne_mb","nb_evenements_data_cdr"]] = 0

    mask_illimite = df["plan_tarifaire"] == "Forfait Illimité"
    df.loc[mask_illimite, ["nb_appels","duree_appel_totale_sec","duree_appel_moyenne_sec","sms_total"]] = 0

    df["nb_evenements_total"] = df["nb_appels"] + df["sms_total"] + df["nb_evenements_data_cdr"]

    return df


# ══════════════════════════════════════════════════════════════════════════════
# 7. DONNÉES MANQUANTES (SIMULATION DES IMPERFECTIONS RÉELLES)
# ══════════════════════════════════════════════════════════════════════════════

def introduce_missing_data(df):
    """
    Introduit des NaN réalistes selon des mécanismes MCAR et MAR.
    Ajoute des colonnes indicatrices pour les NaN informatifs.
    """
    # Facture et data : MCAR (7%)
    for i, col in enumerate(["facture_moyenne_mensuelle", "data_totale_mb"]):
        idx = df.sample(frac=0.07, random_state=42+i).index
        df.loc[idx, col] = np.nan

    # Satisfaction : MAR lié au statut (3% actifs, 15% inactifs)
    prob_nan_sat = np.where(df["statut_actif"], 0.03, 0.15)
    masque = np.random.binomial(1, prob_nan_sat).astype(bool)
    df.loc[df[masque].index, "satisfaction_client"] = np.nan

    # GPS : NaN purs (5%) + coordonnées aberrantes (2%)
    df.loc[df.sample(frac=0.05, random_state=50).index,
           ["latitude_moyenne","longitude_moyenne"]] = np.nan
    df.loc[df.sample(frac=0.02, random_state=51).index,
           ["latitude_moyenne","longitude_moyenne"]] = 0.0

    # Colonnes indicatrices
    df["data_manquante"]         = df["data_totale_mb"].isna().astype(int)
    df["satisfaction_manquante"] = df["satisfaction_client"].isna().astype(int)

    return df


# ══════════════════════════════════════════════════════════════════════════════
# 8. RÉCLAMATIONS
# ══════════════════════════════════════════════════════════════════════════════

def generate_reclamations(df):
    """
    Génère le nombre de réclamations par client selon satisfaction et statut.
    """
    lambda_map = {1: 4.0, 2: 3.0, 3: 2.0, 4: 1.0, 5: 0.3}

    def generer(s, actif):
        if pd.isna(s):
            return np.nan
        lam = lambda_map[int(s)]
        if not actif:
            lam = min(lam * 1.5, 6.0)
        return np.random.poisson(lam)

    df["nb_reclamations"] = [
        generer(s, a) for s, a in zip(df["satisfaction_client"], df["statut_actif"])
    ]
    df.loc[df.sample(frac=0.10, random_state=60).index, "nb_reclamations"] = np.nan
    df["reclamation_manquante"] = df["nb_reclamations"].isna().astype(int)

    return df


# ══════════════════════════════════════════════════════════════════════════════
# 9. FEATURE ENGINEERING
# ══════════════════════════════════════════════════════════════════════════════

def add_engineered_features(df, usage_brut, date_extraction):
    """
    Ajoute les 5 features engineerées : tendance data, ratios d'usage,
    score qualité zone, score de frustration.
    """
    # ── tendance_data_pct ─────────────────────────────────────────────────────
    cdr_data = usage_brut[usage_brut["type_evenement"] == "donnee_mobile"].copy()
    cdr_data["annee_mois"] = cdr_data["date_heure"].dt.to_period("M")
    data_par_mois = (cdr_data.groupby(["client_id","annee_mois"])["data_mb"]
                     .sum().reset_index().sort_values(["client_id","annee_mois"]))

    def extraire_M_M1(group):
        t = group.sort_values("annee_mois")
        if len(t) == 0:   return pd.Series({"data_mois_M": 0.0, "data_mois_M1": 0.0})
        if len(t) == 1:   return pd.Series({"data_mois_M": t["data_mb"].iloc[-1], "data_mois_M1": 0.0})
        return pd.Series({"data_mois_M": t["data_mb"].iloc[-1], "data_mois_M1": t["data_mb"].iloc[-2]})

    data_trend = (data_par_mois.groupby("client_id")
                  .apply(extraire_M_M1).reset_index())
    df = df.merge(data_trend, on="client_id", how="left")
    df[["data_mois_M","data_mois_M1"]] = df[["data_mois_M","data_mois_M1"]].fillna(0.0)

    def calc_tendance(row):
        M, M1 = row["data_mois_M"], row["data_mois_M1"]
        if M == 0 and M1 == 0: return 0.0
        if M1 == 0 and M > 0:  return np.nan
        return round((M - M1) / M1 * 100, 2)

    df["tendance_data_pct"] = df.apply(calc_tendance, axis=1)
    mask_cl = df["plan_tarifaire"] == "Offre Classique"
    df.loc[mask_cl, ["data_mois_M","data_mois_M1","tendance_data_pct"]] = 0.0

    # ── ratio_sms_appels ──────────────────────────────────────────────────────
    def calc_sms_appels(row):
        sms, app = row["sms_total"], row["nb_appels"]
        if app == 0 and sms == 0: return 0.0
        if app == 0 and sms > 0:  return np.nan
        return round(sms / app, 4)

    df["ratio_sms_appels"] = df.apply(calc_sms_appels, axis=1)

    # ── ratio_data_voix ───────────────────────────────────────────────────────
    def calc_data_voix(row):
        data  = row["data_totale_mb"] if not pd.isna(row["data_totale_mb"]) else 0.0
        duree = row["duree_appel_totale_sec"]
        if duree == 0 and data == 0: return 0.0
        if duree == 0 and data > 0:  return np.nan
        return round(data / duree, 6)

    df["ratio_data_voix"] = df.apply(calc_data_voix, axis=1)

    # ── score_qualite_zone ────────────────────────────────────────────────────
    score_zone   = {"URBAIN": 3, "SUBURBAIN": 2, "RURAL": 1}
    score_signal = {"Excellent": 3, "Bon": 2, "Faible": 1}
    df["score_qualite_zone"] = df.apply(
        lambda r: score_zone.get(r["zone_reseau_principale"], np.nan) *
                  score_signal.get(r["qualite_signal_dominante"], np.nan), axis=1
    )

    # ── score_frustration ─────────────────────────────────────────────────────
    df["score_frustration"] = df["nb_reclamations"] * (6 - df["satisfaction_client"])

    return df


# ══════════════════════════════════════════════════════════════════════════════
# 10. INJECTION DES BIAIS MÉTIER
# ══════════════════════════════════════════════════════════════════════════════

def inject_business_biases(df, churn_rate_cible):
    """
    Force des corrélations métier réalistes qui renforcent
    la cohérence entre les features et le churn.

    Biais injectés :
    - Biais 1 : data faible → augmente la probabilité de churn
    - Biais 2 : réclamations élevées + satisfaction basse → churn
    - Biais 3 : ajuste le seuil d'inactivité pour atteindre le churn_rate cible
    """
    print(f"\n[Biais Métier] Taux de churn avant injection : {df['churn'].mean():.1%}")
    print(f"[Biais Métier] Taux cible                    : {churn_rate_cible:.1%}")

    # ── Biais 1 : faible consommation data → augmentation risque churn ────────
    # Les clients avec data_totale_mb très faible (1er décile) et actifs CDR
    # voient leur recence_cdr_jours légèrement augmentée (simulation du signal avant churn)
    seuil_data_faible = df["data_totale_mb"].quantile(0.15)
    mask_data_faible  = (
        (df["data_totale_mb"].fillna(0) < seuil_data_faible) &
        (df["data_totale_mb"].fillna(0) > 0) &
        (df["churn"] == 0)
    )
    # On augmente la recence de 20-40 jours pour ~30% de ces clients
    candidats_b1 = df[mask_data_faible].sample(frac=0.30, random_state=100).index
    df.loc[candidats_b1, "recence_cdr_jours"] += np.random.randint(20, 45, len(candidats_b1))

    # ── Biais 2 : score_frustration élevé → recence augmentée ────────────────
    score_seuil = df["score_frustration"].quantile(0.80)
    mask_frustration = (
        (df["score_frustration"].fillna(0) >= score_seuil) &
        (df["churn"] == 0)
    )
    candidats_b2 = df[mask_frustration].sample(frac=0.25, random_state=101).index
    df.loc[candidats_b2, "recence_cdr_jours"] += np.random.randint(15, 35, len(candidats_b2))

    # ── Recalcul du churn après biais ────────────────────────────────────────
    # (seuil fixe 90 jours, la recence augmentée peut basculer des clients en churn)
    df["churn"] = (df["recence_cdr_jours"] >= 90).astype(int)
    print(f"[Biais Métier] Taux de churn après biais 1&2 : {df['churn'].mean():.1%}")

    # ── Biais 3 : ajustement fin du taux de churn vers la cible ──────────────
    taux_actuel = df["churn"].mean()
    diff = churn_rate_cible - taux_actuel

    if abs(diff) > 0.01:   # on n'ajuste que si l'écart est > 1 point
        if diff > 0:
            # Trop peu de churn → faire basculer des actifs à forte recence
            actifs = df[df["churn"] == 0].sort_values("recence_cdr_jours", ascending=False)
            n_a_basculer = int(abs(diff) * len(df))
            idx_basculer = actifs.head(n_a_basculer).index
            df.loc[idx_basculer, "recence_cdr_jours"] = 90
        else:
            # Trop de churn → réduire recence de quelques churners à faible recence
            churnes = df[df["churn"] == 1].sort_values("recence_cdr_jours")
            n_a_retirer = int(abs(diff) * len(df))
            idx_retirer = churnes.head(n_a_retirer).index
            df.loc[idx_retirer, "recence_cdr_jours"] = 85

        df["churn"] = (df["recence_cdr_jours"] >= 90).astype(int)

    print(f"[Biais Métier] Taux de churn final           : {df['churn'].mean():.1%}")
    return df


# ══════════════════════════════════════════════════════════════════════════════
# 11. EXPORT (CSV ou SQLite)
# ══════════════════════════════════════════════════════════════════════════════

def export_dataset(df, output_path, format_sortie, args):
    """
    Exporte le dataset au format demandé et génère un fichier de métadonnées.
    """
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    if format_sortie == "csv":
        df.to_csv(output, index=False, encoding="utf-8-sig")
        print(f"\n✓ Export CSV       : {output}")
        print(f"  Taille           : {output.stat().st_size / 1024:.1f} Ko")

    elif format_sortie == "sql":
        import sqlite3
        db_path = output.with_suffix(".db")
        conn = sqlite3.connect(db_path)

        # Table principale ML-ready (sans colonnes administratives)
        cols_admin = ["nom_client","adresse_email","num_tel_mobile",
                      "adresse_physique","identifiant_national"]
        df_ml = df.drop(columns=[c for c in cols_admin if c in df.columns])
        df_ml.to_sql("clients_ml", conn, if_exists="replace", index=False)

        # Table complète pour référence
        df.to_sql("clients_complet", conn, if_exists="replace", index=False)
        conn.close()
        print(f"\n✓ Export SQLite    : {db_path}")
        print(f"  Tables           : clients_ml, clients_complet")

    # ── Fichier de métadonnées ────────────────────────────────────────────────
    meta_path = output.with_name(output.stem + "_metadata.txt")
    with open(meta_path, "w", encoding="utf-8") as f:
        f.write("=" * 55 + "\n")
        f.write("MÉTADONNÉES — Dataset synthétique PFE Tunisie Télécom\n")
        f.write("=" * 55 + "\n\n")
        f.write(f"Date de génération   : {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
        f.write(f"Seed aléatoire       : {args.seed}\n")
        f.write(f"Nombre de clients    : {len(df)}\n")
        f.write(f"Nombre de features   : {df.shape[1]}\n")
        f.write(f"Taux de churn cible  : {args.churn_rate:.1%}\n")
        f.write(f"Taux de churn réel   : {df['churn'].mean():.1%}\n")
        f.write(f"Période simulée      : {args.start_date} → {args.extraction_date}\n")
        f.write(f"Format d'export      : {format_sortie.upper()}\n\n")
        f.write("Colonnes du dataset  :\n")
        for col in df.columns:
            nan_pct = df[col].isna().mean() * 100
            f.write(f"  - {col:<40} (NaN : {nan_pct:.1f}%)\n")
    print(f"✓ Métadonnées      : {meta_path}")


# ══════════════════════════════════════════════════════════════════════════════
# 12. POINT D'ENTRÉE PRINCIPAL
# ══════════════════════════════════════════════════════════════════════════════

def main():
    args = parse_arguments()

    # ── Initialisation de la graine aléatoire ────────────────────────────────
    np.random.seed(args.seed)
    print(f"\n{'='*55}")
    print(f"  Générateur PFE Tunisie Télécom")
    print(f"{'='*55}")
    print(f"  Clients        : {args.n_clients}")
    print(f"  Churn cible    : {args.churn_rate:.1%}")
    print(f"  Seed           : {args.seed}")
    print(f"  Format         : {args.format.upper()}")
    print(f"  Sortie         : {args.output}")
    print(f"{'='*55}\n")

    start_date      = pd.to_datetime(args.start_date)
    date_extraction = pd.to_datetime(args.extraction_date)

    # ── Pipeline de génération ────────────────────────────────────────────────
    print("[1/7] Génération des clients de base...")
    clients = generate_base_clients(args.n_clients, start_date, date_extraction)

    print("[2/7] Génération des événements CDR...")
    usage_brut, resume_usage = generate_cdr_events(clients, date_extraction)

    print("[3/7] Génération des sessions internet...")
    resume_sessions = generate_sessions(clients, date_extraction)

    print("[4/7] Génération des localisations...")
    resume_locations = generate_locations(clients, date_extraction)

    print("[5/7] Assemblage et règle churn...")
    df = assemble_dataset(clients, resume_usage, resume_sessions,
                          resume_locations, usage_brut, date_extraction)

    print("[6/7] Données manquantes + réclamations + features...")
    df = introduce_missing_data(df)
    df = generate_reclamations(df)
    df = add_engineered_features(df, usage_brut, date_extraction)

    print("[6.5/7] Injection des biais métier...")
    df = inject_business_biases(df, args.churn_rate)

    print("[7/7] Export...")
    export_dataset(df, args.output, args.format, args)

    # ── Résumé final ──────────────────────────────────────────────────────────
    print(f"\n{'='*55}")
    print(f"  ✓ Génération terminée")
    print(f"  Dimensions      : {df.shape}")
    print(f"  Taux de churn   : {df['churn'].mean():.1%}  "
          f"({df['churn'].sum()} churné / {(df['churn']==0).sum()} actif)")
    print(f"{'='*55}\n")


if __name__ == "__main__":
    main()
