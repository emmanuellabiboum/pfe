"""
Audit de Qualité des Données — Fonctions de validation et correction
Basé sur les recommandations du rapport d'audit (RGS-90)
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass


@dataclass
class DataQualityReport:
    """Rapport d'audit de qualité des données"""
    total_rows: int
    anomalies_detected: int
    corrections_applied: int
    contradictions: List[Dict]
    nan_summary: Dict[str, int]
    zero_structural_flags: Dict[str, float]
    
    def to_dict(self) -> Dict:
        return {
            'total_rows': self.total_rows,
            'anomalies_detected': self.anomalies_detected,
            'corrections_applied': self.corrections_applied,
            'taux_anomalie': round(self.anomalies_detected / self.total_rows * 100, 1) if self.total_rows else 0,
            'contradictions': self.contradictions,
            'nan_summary': self.nan_summary,
            'zero_structural_flags': self.zero_structural_flags,
        }


class DataQualityAuditor:
    """
    Auditeur de qualité des données selon les standards RGS-90.
    Gère les incohérences, NaN, et zéros structurels.
    """
    
    SEUIL_INACTIVITE_JOURS = 90  # Standard INTT RGS90
    
    def __init__(self, df: pd.DataFrame):
        self.df = df.copy()
        self.original_shape = df.shape
        self.corrections_log = []
        
    def calculer_duree_appel_moyenne(self) -> pd.Series:
        """
        A — Calcule la durée moyenne d'appel avec gestion division par zéro.
        
        Règle: duree_appel_moyenne_sec = duree_appel_totale_sec / nb_appels
        Si nb_appels = 0 → duree_appel_moyenne_sec = 0 (par convention)
        """
        result = self.df.apply(
            lambda row: (
                row['duree_appel_totale_sec'] / row['nb_appels'] 
                if row['nb_appels'] > 0 else 0
            ),
            axis=1
        )
        
        # Log des corrections
        zero_appels = (self.df['nb_appels'] == 0).sum()
        if zero_appels > 0:
            self.corrections_log.append({
                'type': 'calcul_duree_moyenne',
                'description': f'{zero_appels} clients avec nb_appels=0, durée moyenne forcée à 0',
                'rows_affected': int(zero_appels)
            })
        
        return result
    
    def detecter_contradictions_statut(self) -> pd.DataFrame:
        """
        B — Détecte les contradictions entre statut_actif et churn.
        
        Contradictions:
        - statut_actif=True avec churn=1 (30 cas typiques)
        - statut_actif=False avec churn=0 (46 cas typiques)
        
        Note: Ces contradictions sont conceptuellement normales car
        statut_actif = administratif, churn = comportemental (RGS-90)
        """
        contradictions = []
        
        # Type 1: Actif admin mais churné comportemental
        mask1 = (self.df['statut_actif'] == True) & (self.df['churn'] == 1)
        if mask1.any():
            contradictions.append({
                'type': 'actif_admin_churn_comportemental',
                'description': 'statut_actif=True avec churn=1',
                'count': int(mask1.sum()),
                'explication': 'Client actif contractuellement mais inactif depuis >90j (RGS-90)',
                'action': 'Exclure statut_actif des features (variable administrative)'
            })
        
        # Type 2: Inactif admin mais non-churné
        mask2 = (self.df['statut_actif'] == False) & (self.df['churn'] == 0)
        if mask2.any():
            contradictions.append({
                'type': 'inactif_admin_non_churn',
                'description': 'statut_actif=False avec churn=0',
                'count': int(mask2.sum()),
                'explication': 'Client inactif contractuellement mais avec activité récente',
                'action': 'Exclure statut_actif des features (variable administrative)'
            })
        
        return pd.DataFrame(contradictions)
    
    def traiter_valeurs_manquantes(self) -> Tuple[pd.DataFrame, List[str]]:
        """
        C — Stratégie de traitement des NaN avec flags binaires.
        
        Stratégie retenue: Conservation des NaN avec ajout de flags sentinelles.
        Le NaN porte une information comportementale.
        
        Flags ajoutés:
        - data_manquante (0/1)
        - satisfaction_manquante (0/1)
        - reclamation_manquante (0/1)
        """
        df_processed = self.df.copy()
        flags_created = []
        
        # Colonnes à traiter avec leurs stratégies
        nan_columns = {
            'data_totale_mb': 'data_manquante',
            'satisfaction_client': 'satisfaction_manquante',
            'nb_reclamations': 'reclamation_manquante',
            'facture_moyenne_mensuelle': None,  # Médiane par groupe
            'score_frustration': None,  # 0 (valeur neutre)
            'tendance_data_pct': None,  # Médiane globale
            'ratio_data_voix': None,  # Médiane globale
            'ratio_sms_appels': None,  # Médiane globale
        }
        
        for col, flag_name in nan_columns.items():
            if col in df_processed.columns:
                nan_count = df_processed[col].isna().sum()
                
                if nan_count > 0:
                    # Créer le flag si applicable
                    if flag_name:
                        df_processed[flag_name] = df_processed[col].isna().astype(int)
                        flags_created.append(flag_name)
                    
                    # Appliquer l'imputation appropriée
                    if col == 'facture_moyenne_mensuelle':
                        # Médiane par type_abonnement
                        df_processed[col] = df_processed.groupby('type_abonnement')[col].transform(
                            lambda x: x.fillna(x.median())
                        )
                    elif col == 'score_frustration':
                        # 0 = valeur neutre (absence de réclamation)
                        df_processed[col] = df_processed[col].fillna(0)
                    elif col in ['tendance_data_pct', 'ratio_data_voix', 'ratio_sms_appels']:
                        # Médiane globale (robuste aux outliers)
                        df_processed[col] = df_processed[col].fillna(df_processed[col].median())
                    
                    self.corrections_log.append({
                        'type': 'imputation_nan',
                        'column': col,
                        'rows_affected': int(nan_count),
                        'strategy': 'median' if col != 'score_frustration' else 'zero_neutral',
                        'flag_created': flag_name
                    })
        
        return df_processed, flags_created
    
    def corriger_incoherences_plan_tarifaire(self) -> pd.DataFrame:
        """
        D — Correction des incohérences plan tarifaire / consommation.
        
        Cas 1: Offre Classique avec data > 0 → data_forcé_à_0
        Cas 2: Offre Classique avec data NaN → data_forcé_à_0
        """
        df_corrected = self.df.copy()
        corrections = []
        
        if 'plan_tarifaire' in df_corrected.columns and 'data_totale_mb' in df_corrected.columns:
            # Cas 1 & 2: Offre Classique avec data non-nulle ou NaN
            mask_classique = df_corrected['plan_tarifaire'] == 'Classique'
            mask_data_non_zero = (df_corrected['data_totale_mb'] > 0) | (df_corrected['data_totale_mb'].isna())
            
            to_correct = mask_classique & mask_data_non_zero
            if to_correct.any():
                count = to_correct.sum()
                df_corrected.loc[to_correct, 'data_totale_mb'] = 0
                corrections.append({
                    'type': 'correction_offre_classique',
                    'description': f'{count} clients Offre Classique avec data>0 ou NaN → data=0',
                    'rows_affected': int(count),
                    'regle': 'Offre Classique = voix/SMS uniquement, data structurellement nulle'
                })
        
        self.corrections_log.extend(corrections)
        return df_corrected
    
    def calculer_zeros_structurels(self) -> Dict[str, float]:
        """
        F — Calcule la proportion de zéros structurels par variable.
        
        Ces zéros reflètent l'inéligibilité fonctionnelle à certains services
        selon le type d'offre souscrite.
        """
        zero_stats = {}
        
        variables_a_verifier = [
            'data_moyenne_gb',
            'ratio_data_voix',
            'duree_appel_moyenne_sec',
            'data_totale_mb',
            'nb_appels',
        ]
        
        for var in variables_a_verifier:
            if var in self.df.columns:
                zero_pct = (self.df[var] == 0).mean() * 100
                zero_stats[var] = round(zero_pct, 1)
        
        return zero_stats
    
    def ajouter_flags_offre(self) -> pd.DataFrame:
        """
        Ajoute les flags d'offre pour capturer l'information structurelle.
        
        Flags:
        - flag_offre_data: 1 si l'offre inclut la data
        - flag_offre_voix: 1 si l'offre inclut la voix
        """
        df = self.df.copy()
        
        if 'plan_tarifaire' in df.columns:
            # Définir les offres avec data/voix
            offres_avec_data = ['Confort', 'Premium', 'Illimité', 'Data+']
            offres_avec_voix = ['Classique', 'Confort', 'Premium', 'Illimité']
            
            df['flag_offre_data'] = df['plan_tarifaire'].isin(offres_avec_data).astype(int)
            df['flag_offre_voix'] = df['plan_tarifaire'].isin(offres_avec_voix).astype(int)
            
            self.corrections_log.append({
                'type': 'flags_offre',
                'flags_created': ['flag_offre_data', 'flag_offre_voix'],
                'description': 'Flags structurels ajoutés pour éviter le biais dans les statistiques'
            })
        
        return df
    
    def verifier_doublons(self) -> Dict:
        """
        E — Vérification des doublons sur client_id.
        """
        if 'client_id' not in self.df.columns:
            return {'doublons_detectes': 0, 'lignes_uniques': len(self.df)}
        
        total = len(self.df)
        uniques = self.df['client_id'].nunique()
        doublons = total - uniques
        
        return {
            'doublons_detectes': int(doublons),
            'lignes_uniques': int(uniques),
            'total_lignes': total,
            'unicite_verifiee': doublons == 0
        }
    
    def run_full_audit(self) -> Tuple[pd.DataFrame, DataQualityReport]:
        """
        Exécute l'audit complet de qualité des données.
        
        Returns:
            Tuple: (DataFrame corrigé, Rapport d'audit)
        """
        # 1. Vérifier les doublons
        doublons_info = self.verifier_doublons()
        
        # 2. Traiter les valeurs manquantes
        df_clean, flags = self.traiter_valeurs_manquantes()
        self.df = df_clean  # Mettre à jour pour les étapes suivantes
        
        # 3. Corriger les incohérences plan tarifaire
        df_clean = self.corriger_incoherences_plan_tarifaire()
        self.df = df_clean
        
        # 4. Ajouter les flags d'offre
        df_clean = self.ajouter_flags_offre()
        self.df = df_clean
        
        # 5. Calculer la durée moyenne (si colonnes présentes)
        if 'duree_appel_totale_sec' in df_clean.columns and 'nb_appels' in df_clean.columns:
            df_clean['duree_appel_moyenne_sec'] = self.calculer_duree_appel_moyenne()
        
        # 6. Détecter les contradictions
        contradictions_df = self.detecter_contradictions_statut()
        
        # 7. Calculer les zéros structurels
        zero_stats = self.calculer_zeros_structurels()
        
        # 8. Compter les NaN restants
        nan_summary = {}
        for col in df_clean.columns:
            nan_count = df_clean[col].isna().sum()
            if nan_count > 0:
                nan_summary[col] = int(nan_count)
        
        # Générer le rapport
        report = DataQualityReport(
            total_rows=len(df_clean),
            anomalies_detected=sum(c.get('rows_affected', 0) for c in self.corrections_log),
            corrections_applied=len(self.corrections_log),
            contradictions=contradictions_df.to_dict('records') if not contradictions_df.empty else [],
            nan_summary=nan_summary,
            zero_structural_flags=zero_stats
        )
        
        return df_clean, report


# Fonctions utilitaires simples pour l'API

def audit_dataframe(df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict]:
    """
    Fonction simple d'audit qualité des données.
    
    Usage:
        df_clean, report = audit_dataframe(df)
    """
    auditor = DataQualityAuditor(df)
    df_clean, report = auditor.run_full_audit()
    return df_clean, report.to_dict()


def calculer_recence_cdr(date_dernier_evenement, date_extraction) -> int:
    """
    Calcule la récence CDR selon le standard RGS-90.
    
    Args:
        date_dernier_evenement: Date du dernier événement CDR
        date_extraction: Date d'extraction des données
    
    Returns:
        Nombre de jours depuis le dernier événement
    """
    delta = date_extraction - date_dernier_evenement
    return delta.days


def definir_churn(recence_cdr_jours: int, seuil: int = 90) -> int:
    """
    Définit le churn selon la règle RGS-90.
    
    Règle: churn = 1 si recence >= 90 jours, sinon 0
    
    Args:
        recence_cdr_jours: Nombre de jours depuis dernier événement
        seuil: Seuil d'inactivité (défaut: 90 jours)
    
    Returns:
        1 si churné, 0 sinon
    """
    return 1 if recence_cdr_jours >= seuil else 0
