# =============================================================================
# tests_manuels/diagnostic_modalites.py
# Investigation approfondie des transformations de modalités
# =============================================================================
#
# Objectif : comprendre quel nettoyage le notebook a appliqué entre :
#   - Le CSV original (avec accents et parenthèses)
#   - Le get_dummies final (sans accents, avec underscores)
#
# Sans cette compréhension, /api/predict/batch sur un CSV brut produirait
# des prédictions silencieusement biaisées.

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd

# ⚠️ ADAPTE LE CHEMIN à ton dataset original (le même que diagnostic_dataset.py)
CHEMIN_DATASET =  r"C:\pfe_final\dataset_modeling.csv"  # ← à remplacer

print("=" * 70)
print("  DIAGNOSTIC MODALITÉS — TRANSFORMATIONS APPLIQUÉES")
print("=" * 70)

df = pd.read_csv(CHEMIN_DATASET)

# =============================================================================
# 1. Modalités EXACTES dans le dataset original
# =============================================================================
print("\n--- 1. Modalités exactes dans le dataset original ---\n")

cols_categorielles = [
    "genre_client",
    "type_abonnement",
    "plan_tarifaire",
    "moyen_paiement",
    "zone_reseau_principale",
    "qualite_signal_dominante",
]

for col in cols_categorielles:
    if col in df.columns:
        modalites = sorted(df[col].dropna().unique().tolist())
        print(f"  {col:<28} :")
        for m in modalites:
            # Affiche aussi la longueur et les codes ASCII des caractères
            # spéciaux pour repérer accents et caractères invisibles
            print(f"      {repr(m):<40}  (len={len(m)})")
        print()


# =============================================================================
# 2. Test de get_dummies SANS nettoyage
# =============================================================================
print("\n--- 2. Colonnes générées par get_dummies SANS nettoyage ---\n")

df_dummies_brut = pd.get_dummies(
    df[cols_categorielles[:-1]],  # exclut qualite_signal (ordinal)
    columns=cols_categorielles[:-1],
    drop_first=True,
    dtype=int,
)
print("  Colonnes générées (extraits) :")
for col in df_dummies_brut.columns[:15]:
    print(f"      {repr(col)}")
if len(df_dummies_brut.columns) > 15:
    print(f"      ... ({len(df_dummies_brut.columns)} colonnes au total)")


# =============================================================================
# 3. Test de get_dummies APRÈS nettoyage manuel
# =============================================================================
print("\n--- 3. Colonnes générées APRÈS nettoyage des modalités ---\n")

import unicodedata

def nettoyer_modalite(s: str) -> str:
    """Reproduit ce que le notebook a probablement fait."""
    if not isinstance(s, str):
        return s
    # Suppression des accents
    s_sans_accents = "".join(
        c for c in unicodedata.normalize("NFD", s)
        if unicodedata.category(c) != "Mn"
    )
    # Remplacement des parenthèses par underscores
    s_clean = s_sans_accents.replace("(", "").replace(")", "").replace(" ", "_")
    # On simplifie pour matcher 'Forfait_Mobile_Mixte' etc.
    # Note : ce n'est pas évident, à comparer avec ohe_columns
    return s_clean


df_test = df[cols_categorielles[:-1]].copy()
for col in df_test.columns:
    df_test[col] = df_test[col].apply(nettoyer_modalite)

df_dummies_clean = pd.get_dummies(
    df_test,
    columns=cols_categorielles[:-1],
    drop_first=True,
    dtype=int,
)
print("  Colonnes après nettoyage (extraits) :")
for col in df_dummies_clean.columns[:15]:
    print(f"      {repr(col)}")
if len(df_dummies_clean.columns) > 15:
    print(f"      ... ({len(df_dummies_clean.columns)} colonnes au total)")


# =============================================================================
# 4. Comparaison avec les colonnes attendues par le modèle
# =============================================================================
print("\n--- 4. Comparaison avec ohe_columns du modèle ---\n")

import json
import builtins

with builtins.open("fastapi_artifacts/preprocessing_params.json", "r", encoding="utf-8") as f:
    params = json.load(f)

ohe_attendues = set(params["ohe_columns"])
print(f"  Colonnes OHE attendues par le modèle : {len(ohe_attendues)}")
for c in sorted(ohe_attendues):
    print(f"      {c}")

print()

# Vérification : nos transformations matchent-elles ?
generees_brut  = set(df_dummies_brut.columns)
generees_clean = set(df_dummies_clean.columns)

print(f"\n  Strategie A (sans nettoyage)   : {len(generees_brut & ohe_attendues)} / {len(ohe_attendues)} colonnes matchent")
print(f"  Strategie B (avec nettoyage)   : {len(generees_clean & ohe_attendues)} / {len(ohe_attendues)} colonnes matchent")

manquantes_A = ohe_attendues - generees_brut
manquantes_B = ohe_attendues - generees_clean

if manquantes_A:
    print(f"\n  Strategie A — colonnes manquantes :")
    for c in sorted(manquantes_A):
        print(f"      {c}")

if manquantes_B:
    print(f"\n  Strategie B — colonnes manquantes :")
    for c in sorted(manquantes_B):
        print(f"      {c}")

if not manquantes_A:
    print("\n  ✓ Stratégie A (SANS nettoyage) suffit pour matcher le modèle")
elif not manquantes_B:
    print("\n  ✓ Stratégie B (AVEC nettoyage NFD + remplacement parens/espaces) matche")
else:
    print("\n  ⚠ Aucune stratégie ne matche complètement → besoin d'investigation manuelle")


# =============================================================================
# 5. Inspection manuelle d'un échantillon
# =============================================================================
print("\n--- 5. Inspection ligne par ligne sur 3 échantillons ---\n")

for i, row in df.head(3).iterrows():
    print(f"  Ligne {i} :")
    for col in cols_categorielles[:-1]:
        if col in df.columns:
            valeur_brute = row[col]
            valeur_clean = nettoyer_modalite(valeur_brute)
            print(f"      {col:<28} : {repr(valeur_brute):<30} → {repr(valeur_clean)}")
    print()


print("=" * 70)
print("  FIN DU DIAGNOSTIC MODALITES")
print("=" * 70)