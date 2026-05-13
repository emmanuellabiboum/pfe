# =============================================================================
# tests_manuels/diagnostic_dataset.py
# Investigation des règles métier dans le dataset original
# =============================================================================

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd

# ⚠️ ADAPTE LE CHEMIN à ton dataset original
CHEMIN_DATASET = r"C:\pfe_final\dataset_modeling.csv"  # ← à remplacer par le bon chemin

print("=" * 70)
print("  DIAGNOSTIC DU DATASET — RÈGLES MÉTIER")
print("=" * 70)

df = pd.read_csv(CHEMIN_DATASET)
print(f"\nTotal observations : {len(df)}")
print(f"Taux churn global   : {df['churn'].mean():.2%}")

# =============================================================================
# Règle 1 : Mapping plan_tarifaire ↔ flag_offre_data / flag_offre_voix
# =============================================================================
print("\n" + "-" * 70)
print("RÈGLE 1 : Plan tarifaire vs flags d'offres")
print("-" * 70)

if "plan_tarifaire" in df.columns:
    crosstab = pd.crosstab(
        df["plan_tarifaire"],
        [df["flag_offre_data"], df["flag_offre_voix"]],
        margins=True,
    )
    print("\nCroisement plan × (flag_data, flag_voix) :")
    print(crosstab)

# =============================================================================
# Règle 2 : Mapping plan_tarifaire ↔ type_abonnement
# =============================================================================
print("\n" + "-" * 70)
print("RÈGLE 2 : Plan tarifaire vs type d'abonnement")
print("-" * 70)

if "type_abonnement" in df.columns:
    crosstab2 = pd.crosstab(df["plan_tarifaire"], df["type_abonnement"], margins=True)
    print("\nCroisement plan × type_abonnement :")
    print(crosstab2)

# =============================================================================
# Règle 3 : Cohérence flag_offre_data=0 → data_moyenne_gb=0
# =============================================================================
print("\n" + "-" * 70)
print("RÈGLE 3 : flag_offre_data=0 doit impliquer data_moyenne_gb=0")
print("-" * 70)

if "flag_offre_data" in df.columns and "data_moyenne_gb" in df.columns:
    incoherent = df[(df["flag_offre_data"] == 0) & (df["data_moyenne_gb"] > 0)]
    print(f"  Lignes incoherentes : {len(incoherent)} / {len(df)}")
    if len(incoherent) > 0:
        print(f"  → REGLE NON RESPECTEE dans le dataset original !")
        print(f"  Exemples :")
        print(incoherent[["plan_tarifaire", "flag_offre_data", "data_moyenne_gb"]].head())
    else:
        print(f"  → REGLE RESPECTEE dans le dataset original")

# =============================================================================
# Règle 4 : Cohérence consentement_marketing vs optout_marketing
# =============================================================================
print("\n" + "-" * 70)
print("RÈGLE 4 : consentement_marketing vs optout_marketing")
print("-" * 70)

if "consentement_marketing" in df.columns and "optout_marketing" in df.columns:
    crosstab3 = pd.crosstab(
        df["consentement_marketing"],
        df["optout_marketing"],
        margins=True,
    )
    print("\nCroisement consentement × optout :")
    print(crosstab3)

    incoherent_marketing = df[
        (df["consentement_marketing"] == True) & (df["optout_marketing"] == True)
    ]
    print(f"\n  Lignes (consentement=1 ET optout=1) : {len(incoherent_marketing)}")

# =============================================================================
# Règle 5 : Bornes des scores
# =============================================================================
print("\n" + "-" * 70)
print("RÈGLE 5 : Bornes des scores numériques")
print("-" * 70)

for col in ["score_frustration", "score_qualite_zone", "tendance_data_pct",
            "ratio_data_voix"]:
    if col in df.columns:
        print(f"  {col:25} : min={df[col].min():.3f}, "
              f"max={df[col].max():.3f}, mean={df[col].mean():.3f}")

# =============================================================================
# Vérification du mélange train/test (Constat 1)
# =============================================================================
print("\n" + "-" * 70)
print("INVESTIGATION CONSTAT 1 : Le dataset 300 obs contient-il train+test ?")
print("-" * 70)

print(f"  Si tu as utilisé un split 70/30 stratifié sur {len(df)} obs,")
print(f"  → train = {int(len(df) * 0.7)} obs, test = {int(len(df) * 0.3)} obs")
print(f"  → Le dataset complet à 300 obs contient effectivement train+test")
print(f"  → C'est NORMAL que le modèle voie 'mieux' les données qu'il a apprises")

print("\n" + "=" * 70)
print("  FIN DU DIAGNOSTIC")
print("=" * 70)