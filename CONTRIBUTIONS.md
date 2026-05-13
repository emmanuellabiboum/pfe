# Guide de Contributions - Projet CHURN Tunisie Telecom

> **Objectif** : Coordonner le travail d'équipe en mode distant pour le développement du système de gestion du churn client.

---

## 🤝 Collaboration à Distance

Malheureusement chacun écrit sur sa partie. Puisqu'on ne vit pas ensemble. Du coup si on change les titre ça ira ?

---

## �️ Technologies Utilisées

Le projet utilise les technologies suivantes :

- **Backend** : Django (framework web Python) pour l'application principale
- **API** : FastAPI pour les services d'API REST
- **Base de données** : SQLite (db.sqlite3) pour le développement, potentiellement PostgreSQL en production
- **Machine Learning** : Scikit-learn, Pandas, NumPy pour les modèles de prédiction du churn
- **Visualisation** : Matplotlib, Seaborn pour l'analyse exploratoire (EDA)
- **Email** : Service SMTP pour l'OTP et les notifications
- **Frontend** : HTML/CSS/JavaScript avec templates Django
- **Tâches asynchrones** : Fonctions périodiques pour vérifications (recommandations expirées, rappels)
- **Génération de PDF** : wkhtmltopdf pour les rapports
- **Environnement** : Python virtualenv pour la gestion des dépendances

---
## 🔗 Endpoints API

### Endpoints Django (URLs principales)

- **Admin** : `/admin/` - Interface d'administration Django
- **Accounts** : `/accounts/` - Module d'authentification
  - `login/` - Connexion utilisateur
  - `inscription/` - Inscription utilisateur
  - `verify-otp/` - Vérification OTP
  - `assign-agence/` - Assignation d'agence
  - `reset-password/` - Réinitialisation mot de passe
  - `roles-disponibles/` - Rôles disponibles
  - `gestion-comptes/` - Gestion des comptes
  - `action-compte/<user_id>/` - Actions sur compte
  - `profile/` - Profil utilisateur

- **Dashboard** : `/` (racine) - Module principal
  - `clients/` - Liste des clients
  - `clients/<client_id>/` - Fiche client
  - `clients/<client_id>/shap/` - Explication SHAP
  - `clients/<client_id>/pdf/` - Fiche client PDF
  - `dashboard-global/` - Dashboard global
  - `dashboard-global/rapport-pdf/` - Rapport PDF
  - `notifications/` - Notifications
  - `notifications/api/` - API notifications
  - `kpi/api/` - API KPIs
  - `historique-analyses/` - Historique analyses
  - `lancer-analyse/` - Lancer analyse
  - `train-models/` - Entraîner modèles
  - `recommandations/<rec_id>/action/` - Action recommandation
  - `administration/` - Administration

### Endpoints FastAPI (Service ML)

- **Health** : `/health` - Vérification santé API
- **Model Info** : `/api/model/info` - Informations modèle
- **Predict** : `/api/predict` - Prédiction client unique
- **Predict Batch** : `/api/predict/batch` - Prédiction batch
- **Analyse** : `/api/analyse` - Analyse données

---

## 🏗️ Architecture et Intégration

### Flux d'Intégration Django - FastAPI - ML

Le système suit une architecture modulaire avec séparation des responsabilités :

1. **Django (Interface & Logique Métier)** :
   - Gère l'authentification et l'autorisation des utilisateurs
   - Fournit l'interface web (templates HTML/CSS/JS)
   - Gère la persistance des données (modèles Django, base SQLite)
   - Coordonne les workflows métier (notifications, recommandations, analyses)

2. **FastAPI (Service ML Externe)** :
   - Service REST API dédié aux prédictions ML
   - Fonctionne indépendamment de Django (port 8000 par défaut)
   - Reçoit les données via HTTP POST (JSON ou CSV)
   - Retourne les prédictions et analyses en JSON
   - Peut être déployé séparément pour la scalabilité

3. **ML intégré dans Django** :
   - Modèles chargés directement via joblib (churn_model_v1.pkl)
   - Prétraitement des données avec `ml_pipeline.py`
   - Explications SHAP pour l'interprétabilité
   - Utilisé pour les prédictions individuelles et explications

### Connexions et Flux de Données

- **Django → FastAPI** : Via `httpx` dans `core/fastapi_service.py`
  - Prédictions batch : `ClientChurn.objects.filter(score_churn__gt=0.7).values()` → DataFrame → CSV string → POST /api/predict/batch → JSON résultats → update ClientChurn
  - Prédiction unique : `fiche_client view` → `predict_single_client(features_dict)` → POST /api/predict → affichage immédiat
  - Analyse portefeuille : `lancer_analyse view` → `analyse_portefeuille_from_csv(csv_bytes)` → POST /api/analyse → sauvegarde AnalyseSession

- **ML Pipeline intégré** :
  - Chargement modèle : `load_ml_model()` charge `churn_model_v1.pkl` + metadata.json au démarrage
  - Prétraitement : `pretraiter_client()` applique `FEATURE_NAMES_ORDERED`, encoding, scaling
  - Prédiction : `ensemble_model.predict_proba()` avec seuil `metadata["seuil_optimal"]`
  - SHAP : `TreeExplainer(xgb_component).shap_values()` pour explications feature par feature

- **Persistance données** :
  - Clients : `ClientChurn` avec 25+ champs features + score_churn/proba calculés
  - Recommandations : `Recommandation` liée à ClientChurn, workflow status (pending → validated/rejected → completed)
  - Notifications : `Notification` par user, types : 'nouvelle_recommandation', 'validation_requise', 'alerte_churn'
  - Analyses : `AnalyseSession` stocke résultats JSON de FastAPI

### Workflows Métier Spécifiques

1. **Inscription Utilisateur** :
   - `inscription_view` crée User(status='pending') → email validation à supérieur → `action_compte_view` active compte

2. **Prédiction Churn** :
   - Batch : Vue `lancer_analyse` → appel synchrone FastAPI → update scores → notifications
   - Individuel : `fiche_client` → ML intégré → SHAP → recommandation suggérée

3. **Recommandations** :
   - Agent crée via `creer_recommandation_agent` → notification chef_agence → validation/rejet → notification agent

4. **Notifications** :
   - Temps réel via `notifications_api_view` (AJAX polling) + email via `notifications_engine.send_notification()`

### Avantages de cette Architecture

- **Séparation des préoccupations** : UI/logique vs ML
- **Scalabilité** : FastAPI peut être déployé sur des serveurs dédiés
- **Maintenance** : ML peut être mis à jour sans toucher Django
- **Testabilité** : Services indépendants plus faciles à tester
- **Performance** : Prédictions batch synchrones via API FastAPI

---

## 📋 Répartition des Modules

### Module `accounts` - Authentification & Utilisateurs
**Responsable** : [À compléter]

**Périmètre** :
- Gestion des utilisateurs avec rôles hiérarchiques (super_admin, admin_ville, chef_agence, agent_commercial, agent_marketing)
- Workflow d'inscription : création compte → validation par supérieur → activation
- Authentification à deux facteurs : mot de passe + OTP email
- Suivi des connexions (LoginActivity) et génération OTP (OTPCode)
- Gestion des comptes : activation/désactivation, réinitialisation mot de passe

**Modèles détaillés** :
- `User` : Hérite d'AbstractUser, champs supplémentaires : role (CharField choix), ville (ForeignKey Ville), agence (ForeignKey Agence), is_active (Bool)
- `OTPCode` : code (CharField), expiration (DateTime), user (ForeignKey User), used (Bool)
- `LoginActivity` : user (ForeignKey), timestamp (DateTime), ip_address (CharField), user_agent (TextField)
- `AdminVille` : user (OneToOne User), ville (ForeignKey Ville)

**Vues principales** :
- `login_view` : GET affiche formulaire, POST vérifie credentials et envoie OTP
- `verify_otp_view` : Valide code OTP, crée session utilisateur
- `inscription_view` : Crée User avec role, envoie email validation à supérieur
- `assign_agence` : Associe agent à agence (appel AJAX)
- `reset_password_view` : Génère token, envoie email reset
- `gestion_comptes_view` : Liste users par ville/agence, actions bulk
- `action_compte_view` : Active/désactive user spécifique
- `roles_disponibles` : Retourne JSON rôles disponibles selon hiérarchie

**Fichiers clés** :
- `accounts/models.py` - Définition modèles ci-dessus
- `accounts/views.py` - Logique vues détaillée
- `accounts/forms.py` - UserCreationForm, LoginForm, OTPForm
- `accounts/email_utils.py` - send_otp_email(), send_validation_email()
- `accounts/templates/accounts/` - login.html, inscription.html, profile.html

**Dépendances** :
- `core.models.Ville`, `core.models.Agence` (liens géographiques)
- `config.settings` (EMAIL_HOST, EMAIL_PORT pour SMTP)
- `core.otp_service` (génération codes sécurisés)

---

### Module `core` - Socle Commun
**Responsable** : [À compléter]

**Périmètre** :
- Modèles géographiques de base pour structuration hiérarchique
- Service OTP centralisé (génération codes 6 chiffres, expiration 10 min)
- Moteur de notifications temps réel (WebSocket + email)
- Pipeline ML unifié (prétraitement, features engineering)
- Intégration FastAPI pour prédictions externes
- Middleware d'authentification et logging
- Context processors pour variables globales (user, notifications)

**Modèles détaillés** :
- `Ville` : nom (CharField), code_postal (CharField), region (CharField)
- `Agence` : nom (CharField), ville (ForeignKey Ville), adresse (TextField), telephone (CharField)

**Services clés** :
- `otp_service.py` : generate_otp_code() → str 6 digits, verify_otp_code(code, user) → bool
- `notifications_engine.py` : send_notification(user, message, type), create_recommendation_notification(rec)
- `ml_pipeline.py` : pretraiter_dataframe(df) → df nettoyé, pretraiter_client(features_dict) → dict
- `ml_service.py` : load_ml_model() → bool, predict_churn_proba(features) → float, get_shap_explanation(features) → dict
- `fastapi_service.py` : predict_batch_from_dataframe(df) → dict, check_fastapi_health() → bool

**Middleware** :
- `middleware.py` : CustomMiddleware pour logging requêtes, gestion sessions

**Context Processors** :
- `context_processors.py` : user_context(request) → dict avec user info, notifications non lues

**Fichiers clés** :
- `core/models.py` - Ville, Agence
- `core/notifications_engine.py` - Logique notifications
- `core/otp_service.py` - Génération/vérification OTP
- `core/ml_pipeline.py` - Préparation données ML
- `core/ml_service.py` - Prédictions ML intégrées
- `core/model_config.py` - Hyperparamètres modèles
- `core/fastapi_service.py` - Client HTTP FastAPI
- `core/middleware.py` - Middleware personnalisé
- `core/context_processors.py` - Variables template globales

**Dépendances** :
- `accounts.models.User` (notifications, auth)
- `learning.models.ClientChurn` (ML pipeline)
- `learning.models.Recommandation` (notifications)

---

### Module `dashboard` - Interface & Visualisation
**Responsable** : [À compléter]

**Périmètre** :
- Interface web principale avec templates Bootstrap
- Dashboard KPIs : taux churn, recommandations actives, notifications
- Gestion recommandations : création, validation hiérarchique, rejet
- Système notifications : création, marquage lu, archivage, suppression
- Gestion analyses : historique, corbeille, restauration
- Administration : reset DB, toggle users, vider tables
- Génération PDF rapports avec wkhtmltopdf

**Modèles détaillés** :
- `Recommandation` : client (ForeignKey ClientChurn), agent (ForeignKey User), contenu (Text), status (CharField: pending/validation/rejected/completed), created_at/updated_at
- `Notification` : user (ForeignKey User), message (Text), type (CharField), is_read (Bool), created_at
- `RejetRecommandation` : recommandation (ForeignKey), motif (Text), rejeteur (ForeignKey User)
- `AnalyseSession` : user (ForeignKey), timestamp, type_analyse (CharField), resultats (JSONField)

**Vues principales** :
- `accueil` : Page d'accueil avec stats générales
- `liste_clients` : Pagination clients avec filtres (ville, agence, score_churn)
- `fiche_client` : Détails client + prédiction + recommandations
- `shap_explanation` : Graphique SHAP pour client spécifique
- `dashboard_global` : KPIs globaux + graphiques
- `notifications_view` : Liste notifications avec actions (marquer lu, archiver)
- `lancer_analyse` : Déclenche analyse batch via FastAPI
- `creer_recommandation_agent` : Formulaire création recommandation
- `action_recommandation` : Workflow validation/rejet hiérarchique
- `administration_view` : Interface admin pour gestion système

**Tâches périodiques** :
- `check_expired_recommendations` : Marque recommandations expirées et crée notifications
- `send_reminder_notifications` : Envoie rappels 3 jours avant échéance

**Templates clés** :
- `accueil.html` : Dashboard d'accueil
- `clients/liste.html` : Table clients avec DataTables
- `clients/fiche.html` : Détails client + actions
- `notifications/liste.html` : Notifications avec badges
- `administration/index.html` : Outils admin

**Fichiers clés** :
- `dashboard/views.py` - 15+ vues détaillées
- `dashboard/models.py` - Modèles métier dashboard
- `dashboard/urls.py` - 30+ patterns URL
- `dashboard/templates/dashboard/` - Templates HTML
- `dashboard/tasks.py` - Tâches asynchrones
- `dashboard/templatetags/dashboard_tags.py` - Filtres template (format_date, truncate_text)

**Dépendances** :
- `accounts.models.User` (auth, rôles)
- `learning.models.ClientChurn` (données clients)
- `core.models.Agence` (filtrage géographique)
- `core.notifications_engine` (envoi notifications)

---

### Module `learning` - Données Clients & ML
**Responsable** : [À compléter]

**Périmètre** :
- Modèles de données clients avec 25+ features pour prédiction churn
- Gestion datasets : upload CSV, validation, stockage
- Service ML intégré (prédictions individuelles)
- Génération données mock pour développement/tests
- Stockage valeurs SHAP pour explicabilité
- Import/export données via pandas

**Modèles détaillés** :
- `ClientChurn` : id_client (CharField), score_churn (Float), probabilite_churn (Float), + 25 features (tenure_mois, facture_moyenne, etc.)
- `EvenementCDR` : client (ForeignKey), type_event (CharField), timestamp, duree (Int)
- `InteractionDigital` : client (ForeignKey), type_interaction (CharField), timestamp, canal (CharField)
- `Reclamation` : client (ForeignKey), categorie (CharField), description (Text), status (CharField), date_creation
- `CampagneMarketing` : nom (CharField), cible (JSONField), date_debut/fin, budget (Float)
- `ShapValeur` : client (ForeignKey), feature (CharField), valeur_shap (Float), impact (CharField)

**Services clés** :
- `ml_service.py` : predict_churn(client_features) → dict, get_shap_values(client) → list
- `data_preparation.py` : clean_dataset(df) → df, feature_engineering(df) → df
- `importers.py` : import_csv(file_path) → bool, validate_data(df) → list erreurs
- `eda_reporter.py` : generate_report(df) → dict stats, plot_distributions(df) → figures

**Vues principales** :
- `upload_dataset` : Upload et validation CSV
- `list_datasets` : Gestion datasets stockés
- `client_detail` : Affichage données client brutes
- `generate_mock_data` : Création données fictives

**Fichiers clés** :
- `learning/models.py` - 7 modèles de données détaillés
- `learning/ml_service.py` - Prédictions ML intégrées
- `learning/data_preparation.py` - Nettoyage/features engineering
- `learning/eda_reporter.py` - Analyses exploratoires
- `learning/importers.py` - Import CSV/validation
- `learning/views.py` - Interface gestion données
- `learning/mock_data.py` - Génération données test

**Dépendances** :
- `accounts.models.User` (tracking uploads)
- `accounts.models.Agence` (filtrage données)
- `core.ml_service` (pipeline ML partagé)

---

## 🔗 Points d'Intégration Critiques

### 1. Entre `accounts` et `core`
- **User** utilise **Ville** et **Agence** (ForeignKey)
- **AdminVille** lie un User à une Ville
- **Validation hiérarchique** : un admin_ville valide les comptes de sa ville

**Protocole** :
- Toute modification des modèles Ville/Agence doit être communiquée à l'équipe `accounts`
- Les changements de rôles utilisateurs doivent être validés par l'équipe `core`

### 2. Entre `learning` et `dashboard`
- **ClientChurn** est affiché dans le dashboard
- **Recommandation** est liée à ClientChurn
- **AnalyseSession** résume les analyses faites sur les clients

**Protocole** :
- Les nouvelles features ML doivent être documentées pour l'affichage dashboard
- Les changements de structure ClientChurn impactent le dashboard

### 3. Entre `core` et `dashboard`
- **notifications_engine** alimente le système de notifications du dashboard
- **Agence** est utilisé pour filtrer les données par agence

**Protocole** :
- Les nouvelles notifications doivent être déclarées dans `NOTIF_TYPES` (dashboard/models.py)
- Le moteur de notifications doit connaître les types de notifications du dashboard

### 4. Entre `core` et `learning`
- **ml_service** et **ml_pipeline** utilisent les données de `learning`
- **model_config** définit les features attendues

**Protocole** :
- Les features ML doivent être cohérentes entre la configuration et les modèles
- Les changements de features doivent être synchronisés

---

## 🤝 Protocole de Collaboration

### Avant de commencer une tâche
1. **Vérifier les dépendances** : Est-ce que mon travail impacte d'autres modules ?
2. **Consulter le responsable** du module impacté
3. **Créer une branche** Git dédiée (ex: `feature/accounts-otp-email`)
4. **Documenter** dans ce fichier la tâche entreprise

### Pendant le développement
1. **Respecter les conventions** :
   - Nommage des variables en français (cohérent avec le projet)
   - Commentaires en français
   - Docstrings pour les fonctions importantes
2. **Tests locaux** : Vérifier que les intégrations fonctionnent
3. **Commits atomiques** : Un commit = une modification logique
4. **Messages de commit clairs** :
   ```
   [accounts] Ajout validation automatique pour super_admin
   [dashboard] Correction affichage notifications mobiles
   [learning] Ajout feature flag_offre_voix dans ClientChurn
   ```

### Avant de merger
1. **Tester l'intégration** avec les autres modules
2. **Vérifier les migrations** Django (si modèles modifiés)
3. **Mettre à jour** ce fichier CONTRIBUTIONS.md
4. **Faire relire** par un autre membre de l'équipe
5. **S'assurer** que les tests passent (`python manage.py test`)

### En cas de conflit
1. **Contacter** le responsable du module concerné
2. **Organiser** un point rapide (visio, appel)
3. **Documenter** la décision dans ce fichier
4. **Mettre à jour** l'ARCHITECTURE.md si besoin

---

## 📝 Suivi des Versions et Changements

### v1.0.0 - [Date à compléter]
**Nouveautés** :
- [ ] Module accounts fonctionnel avec OTP
- [ ] Module core avec Ville/Agence
- [ ] Module dashboard avec interface de base
- [ ] Module learning avec ClientChurn et prédictions

**Changements majeurs** :
- [ ] [Décrire les changements]

**Correctifs** :
- [ ] [Décrire les correctifs]

---

### v0.9.0 - [Date à compléter]
**Nouveautés** :
- [ ] ...

---

## ✅ Checklist d'Intégration (avant chaque merge)

### Pour le module `accounts`
- [ ] Les modèles User, OTPCode sont cohérents avec core.models
- [ ] Les vues d'authentification redirigent correctement vers le dashboard
- [ ] Le système de rôles est respecté dans les autres modules
- [ ] Les templates sont responsive
- [ ] Les emails OTP fonctionnent (SendGrid configuré)

### Pour le module `core`
- [ ] Ville et Agence sont correctement liés aux autres modèles
- [ ] Le moteur de notifications envoie les bonnes notifications
- [ ] Le service OTP est sécurisé
- [ ] La configuration ML est à jour avec les features de learning
- [ ] Les middleware sont testés

### Pour le module `dashboard`
- [ ] Les vues affichent correctement les données de learning
- [ ] Les recommandations sont liées aux bons clients
- [ ] Les notifications s'affichent en temps réel
- [ ] Les templates sont compatibles avec les données de accounts
- [ ] Les KPIs sont calculés correctement

### Pour le module `learning`
- [ ] ClientChurn a toutes les features nécessaires pour le ML
- [ ] Les prédictions sont stockées et accessibles par le dashboard
- [ ] Les données mock sont réalistes
- [ ] L'import CSV fonctionne
- [ ] Les valeurs SHAP sont calculées et stockées

---

## 🚀 Déploiement et Tests

### Environnement de développement
```bash
# Chaque développeur doit avoir :
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
```

### Tests d'intégration
```bash
# Lancer tous les tests
python manage.py test

# Tests spécifiques à un module
python manage.py test accounts
python manage.py test core
python manage.py test dashboard
python manage.py test learning
```

### Vérification des dépendances
```bash
# Vérifier que toutes les dépendances sont installées
pip check

# Mettre à jour requirements.txt si besoin
pip freeze > requirements.txt
```

---

## 📞 Contacts et Réunions

### Réunions d'équipe
- **Hebdomadaire** : [Jour et heure à définir]
- **Point quotidien** : [Optionnel, à définir]
- **Revue de code** : Avant chaque merge majeur

### Canaux de communication
- **GitHub Issues** : Pour le suivi des tâches
- **Discord/Slack** : Pour la communication instantanée
- **Email** : Pour les décisions importantes

### Responsables de module
| Module | Responsable | Contact |
|--------|-------------|---------|
| accounts | [À compléter] | [À compléter] |
| core | [À compléter] | [À compléter] |
| dashboard | [À compléter] | [À compléter] |
| learning | [À compléter] | [À compléter] |

---

## 📚 Ressources Utiles

- **ARCHITECTURE.md** : Vue d'ensemble de l'architecture
- **README.md** : Guide d'installation et d'utilisation
- **Documentation Django** : https://docs.djangoproject.com/
- **Documentation PostgreSQL** : https://www.postgresql.org/docs/

---

**Dernière mise à jour** : 08/05/2026

*Ce fichier est vivant et doit être mis à jour régulièrement par tous les contributeurs.*