"""
Service ML pour la prédiction de churn - Spécifications Audit RGS-90

Ce service charge le Voting Ensemble (LR+RF+XGB, poids 1:1:2) pour les prédictions,
et le composant XGBoost séparé pour SHAP.

Structure des modèles:
- ensemble_model.pkl: VotingClassifier (prédictions)
- xgb_shap_model.pkl: XGBoost (explications SHAP)
- ensemble_scaler.pkl: StandardScaler
- threshold.json: Seuil optimal (0.21)
- feature_names.json: Noms des features

Règle churn: recence_cdr_jours >= 90 jours (27.7%)
"""
import joblib
import json
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class MLService:
    """Service singleton pour les prédictions ML avec Voting Ensemble."""
    
    _instance = None
    _ensemble_model = None  # VotingClassifier (LR+RF+XGB)
    _xgb_shap_model = None  # Composant XGBoost pour SHAP
    _scaler = None  # StandardScaler
    _threshold = 0.21  # Seuil optimal (par défaut)
    _feature_names = None
    _models_dir = None
    
    # Modèles individuels (pour comparaison)
    _individual_models = {}
    _individual_scalers = {}
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """Initialise le service ML et charge les modèles."""
        if self._ensemble_model is None and not self._individual_models:
            self.load_models()
    
    def load_models(self):
        """
        Charge le Voting Ensemble et le composant XGBoost pour SHAP.

        Structure attendue:
        - ensemble_model.pkl: VotingClassifier
        - xgb_shap_model.pkl: XGBoost (TreeExplainer)
        - ensemble_scaler.pkl: StandardScaler
        - threshold.json: {'threshold': 0.21}
        - feature_names.json: ['feature1', 'feature2', ...]
        """
        try:
            self._models_dir = Path(__file__).parent.parent / "models"

            # Vérifier si le dossier models existe
            if not self._models_dir.exists():
                logger.warning(f"⚠️ Dossier models non trouvé: {self._models_dir}")
                logger.warning("Mode mock activé")
                return

            # 1. Charger le Voting Ensemble (prédictions)
            ensemble_path = self._models_dir / "ensemble_model.pkl"
            if ensemble_path.exists():
                self._ensemble_model = joblib.load(ensemble_path)
                logger.info(f"✅ Voting Ensemble chargé: {ensemble_path}")
            else:
                logger.warning(f"⚠️ Voting Ensemble non trouvé: {ensemble_path}")

            # 2. Charger le composant XGBoost (SHAP)
            xgb_path = self._models_dir / "xgb_shap_model.pkl"
            if xgb_path.exists():
                self._xgb_shap_model = joblib.load(xgb_path)
                logger.info(f"✅ XGBoost (SHAP) chargé: {xgb_path}")
            else:
                logger.warning(f"⚠️ XGBoost (SHAP) non trouvé: {xgb_path}")

            # 3. Charger le scaler
            scaler_path = self._models_dir / "ensemble_scaler.pkl"
            if scaler_path.exists():
                self._scaler = joblib.load(scaler_path)
                logger.info(f"✅ Scaler chargé: {scaler_path}")
            else:
                logger.warning(f"⚠️ Scaler non trouvé: {scaler_path}")

            # 4. Charger le seuil optimal
            threshold_path = self._models_dir / "threshold.json"
            if threshold_path.exists():
                with open(threshold_path, 'r') as f:
                    threshold_data = json.load(f)
                    self._threshold = threshold_data.get('threshold', 0.21)
                logger.info(f"✅ Seuil optimal chargé: {self._threshold:.2f}")
            else:
                logger.warning(f"⚠️ Threshold non trouvé, utilisation défaut: {self._threshold}")

            # 5. Charger les noms de features
            features_path = self._models_dir / "feature_names.json"
            if features_path.exists():
                with open(features_path, 'r') as f:
                    self._feature_names = json.load(f)
                logger.info(f"✅ {len(self._feature_names)} features chargées")
            else:
                # Fallback: features par défaut
                self._feature_names = [
                    'type_abonnement', 'facture_moyenne_mensuelle',
                    'nb_appels', 'data_totale_mb', 'sms_total',
                    'tendance_data', 'anciennete_mois',
                    'nb_sessions', 'taux_cookies',
                    'satisfaction_client', 'score_frustration', 'score_qualite_zone',
                    'nb_reclamations', 'reclamation_manquante',
                    'consommation_moyenne', 'retards_paiement', 'nb_services',
                ]
                logger.warning(f"⚠️ Feature names non trouvés, utilisation défaut ({len(self._feature_names)} features)")

            # 6. Charger les modèles individuels (optionnel, pour comparaison)
            individual_models = ['random_forest', 'xgboost', 'logistic_regression']
            for model_name in individual_models:
                model_path = self._models_dir / f"{model_name}_model.pkl"
                scaler_path = self._models_dir / f"{model_name}_scaler.pkl"
                if model_path.exists():
                    self._individual_models[model_name] = joblib.load(model_path)
                    if scaler_path.exists():
                        self._individual_scalers[model_name] = joblib.load(scaler_path)
                    logger.info(f"✅ Modèle individuel chargé: {model_name}")

        except Exception as e:
            logger.error(f"❌ Erreur chargement modèles: {e}")
            logger.warning("Mode mock activé")
    
    def get_ensemble_model(self):
        """Retourne le Voting Ensemble (pour prédictions)."""
        return self._ensemble_model
    
    def get_xgb_shap_model(self):
        """Retourne le composant XGBoost (pour SHAP TreeExplainer)."""
        return self._xgb_shap_model
    
    def get_threshold(self):
        """Retourne le seuil optimal de décision."""
        return self._threshold
    
    def get_scaler(self):
        """Retourne le StandardScaler."""
        return self._scaler
    
    def set_active_model(self, model_name):
        """
        Définit le modèle individuel actif (pour comparaison).
        
        Args:
            model_name: Nom du modèle ('random_forest', 'xgboost', 'logistic_regression', 'ensemble')
        """
        if model_name == 'ensemble' or model_name in self._individual_models:
            logger.info(f"Modèle sélectionné: {model_name}")
            return True
        else:
            logger.warning(f"Modèle {model_name} non disponible")
            return False
    
    def get_available_models(self):
        """Retourne la liste des modèles disponibles."""
        models = ['ensemble']  # Modèle principal
        models.extend(list(self._individual_models.keys()))
        return models
    
    def predict_churn(self, client_data, model_name='ensemble'):
        """
        Prédit le churn pour un client avec le Voting Ensemble.
        
        Args:
            client_data: Dictionnaire ou objet ClientChurn avec les features
            model_name: 'ensemble' (défaut) ou nom du modèle individuel
        
        Returns:
            float: Score de churn entre 0 et 1 (probabilité)
        """
        # Mode mock si pas de modèles
        if not self._ensemble_model and not self._individual_models:
            return self._mock_predict(client_data)
        
        try:
            # Préparer les features
            features = self._prepare_features(client_data)
            
            # Standardiser
            if self._scaler:
                features_scaled = self._scaler.transform([features])
            else:
                features_scaled = [features]
            
            # Utiliser le Voting Ensemble par défaut
            if model_name == 'ensemble' and self._ensemble_model:
                model = self._ensemble_model
            elif model_name in self._individual_models:
                model = self._individual_models[model_name]
                # Utiliser le scaler spécifique au modèle individuel
                if model_name in self._individual_scalers:
                    features_scaled = self._individual_scalers[model_name].transform([features])
            else:
                logger.warning(f"Modèle {model_name} non disponible, utilisation ensemble")
                model = self._ensemble_model
            
            # Prédiction (probabilité)
            if hasattr(model, 'predict_proba'):
                prediction = model.predict_proba(features_scaled)[0][1]
            else:
                prediction = float(model.predict(features_scaled)[0])
            
            return float(prediction)
            
        except Exception as e:
            logger.error(f"❌ Erreur prédiction: {e}")
            return self._mock_predict(client_data)
    
    def predict_batch(self, clients_data):
        """
        Prédit le churn pour plusieurs clients.
        
        Args:
            clients_data: Liste de dictionnaires ou objets ClientChurn
        
        Returns:
            list: Liste des scores de churn
        """
        if not self._models or not self._active_model:
            return [self._mock_predict(client) for client in clients_data]
        
        try:
            model = self._models[self._active_model]
            scaler = self._scalers.get(self._active_model)
            
            features_list = [self._prepare_features(client) for client in clients_data]
            
            if scaler:
                features_list = scaler.transform(features_list)
            
            if hasattr(model, 'predict_proba'):
                predictions = model.predict_proba(features_list)[:, 1]
            else:
                predictions = model.predict(features_list)
            
            return predictions.tolist()
            
        except Exception as e:
            logger.error(f"Erreur lors de la prédiction en lot: {e}")
            return [self._mock_predict(client) for client in clients_data]
    
    def _prepare_features(self, client_data):
        """
        Prépare les features pour le modèle (12 features du dataset généré).
        
        Args:
            client_data: Dictionnaire ou objet ClientChurn

        Returns:
            list: Liste des features dans l'ordre attendu par le modèle
        """
        if hasattr(client_data, 'anciennete_mois'):
            # C'est un objet ClientChurn
            nb_rec = client_data.nb_reclamations if client_data.nb_reclamations is not None else 0
            rec_manquante = client_data.reclamation_manquante
            satisfaction = client_data.satisfaction_client if client_data.satisfaction_client is not None else 3
            return [
                # Profil contractuel
                1 if client_data.type_abonnement == 'postpaye' else 0,  # type_abonnement encodé
                client_data.facture_moyenne_mensuelle,
                # Usage télécom
                client_data.nb_appels,
                client_data.data_totale_mb,
                client_data.sms_total,
                # Tendance
                client_data.tendance_data,
                client_data.anciennete_mois,
                # Engagement
                client_data.nb_sessions,
                client_data.taux_cookies,
                # Satisfaction
                satisfaction,
                client_data.score_frustration,
                client_data.score_qualite_zone,
                # Historique
                nb_rec,
                1 if rec_manquante else 0,
                client_data.consommation_moyenne,
                client_data.retards_paiement,
                client_data.nb_services,
            ]
        else:
            # C'est un dictionnaire
            nb_rec = client_data.get('nb_reclamations', 0)
            if nb_rec is None:
                nb_rec = 0
            rec_manquante = client_data.get('reclamation_manquante', False)
            satisfaction = client_data.get('satisfaction_client', 3)
            return [
                # Profil contractuel
                1 if client_data.get('type_abonnement') == 'postpaye' else 0,
                client_data.get('facture_moyenne_mensuelle', 0),
                # Usage télécom
                client_data.get('nb_appels', 0),
                client_data.get('data_totale_mb', 0),
                client_data.get('sms_total', 0),
                # Tendance
                client_data.get('tendance_data', 0),
                client_data.get('anciennete_mois', 0),
                # Engagement
                client_data.get('nb_sessions', 0),
                client_data.get('taux_cookies', 0),
                # Satisfaction
                satisfaction,
                client_data.get('score_frustration', 0),
                client_data.get('score_qualite_zone', 0),
                # Historique
                nb_rec,
                1 if rec_manquante else 0,
                client_data.get('consommation_moyenne', 0),
                client_data.get('retards_paiement', 0),
                client_data.get('nb_services', 0),
            ]
    
    def _mock_predict(self, client_data):
        """
        Prédiction mock pour le développement quand aucun modèle n'est chargé.
        
        Args:
            client_data: Dictionnaire ou objet ClientChurn
        
        Returns:
            float: Score de churn simulé
        """
        # Logique simple basée sur les features
        if hasattr(client_data, 'nb_reclamations'):
            reclamations = client_data.nb_reclamations
            retards = client_data.retards_paiement
        else:
            reclamations = client_data.get('nb_reclamations', 0)
            retards = client_data.get('retards_paiement', 0)
        
        # Plus de réclamations et de retards = plus de risque
        score = min(0.3 + (reclamations * 0.1) + (retards * 0.15), 0.95)
        return round(score, 2)
    
    def is_model_loaded(self):
        """Vérifie si le Voting Ensemble est chargé."""
        return self._ensemble_model is not None
    
    def get_feature_names(self):
        """Retourne les noms des features."""
        return self._feature_names


# Instance singleton
ml_service = MLService()
