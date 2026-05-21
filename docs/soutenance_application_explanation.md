# Application CHURN — Explication technique complète

Ce document décrit le fonctionnement de l'application CHURN et les éléments techniques utilisés. Il est spécialement conçu pour préparer la soutenance et maîtriser le projet de A à Z.

---

## 1. Vue d'ensemble de l'application

L'application est une plateforme Django qui gère les utilisateurs, les villes, les agences et les sessions d'analyse churn. Elle propose :

- une interface d'administration globale pour les super-admins
- une interface d'administration locale pour les admins de ville
- un dashboard d'agence pour les chefs d'agence et les agents
- un mécanisme d'analyse via import CSV ou données mock
- une logique de gestion des rôles et des permissions

La logique principale se trouve dans :

- `accounts/models.py` : définition des rôles utilisateurs et validation métier
- `core/models.py` : entités `Ville` et `Agence`
- `dashboard/views.py` : vues métier du dashboard
- `dashboard/models.py` : sessions d'analyse et recommandations
- `core/model_config.py` : configuration de modèle / fallback
- `dashboard/templates/dashboard/*.html` : affichage et navigation utilisateur

---

## 2. Architecture des données

### 2.1 `Ville` et `Agence`

Fichier : `core/models.py`

- `Ville` représente une zone géographique couverte par Tunisian Telecom.
  - attributs principaux : `nom`, `code`, `region`, `prioritaire`, `active`
  - `code` est généré automatiquement à partir du nom si absent.

- `Agence` est rattachée à une `Ville`.
  - attributs principaux : `nom`, `ville`, `adresse`, `telephone`, `code`, `active`
  - une agence a toujours une ville associée.

### 2.2 `User` et rôles

Fichier : `accounts/models.py`

Le modèle `User` hérite de `AbstractUser` et ajoute :

- `role` : rôle applicatif (`super_admin`, `admin`, `chef_agence`, `agent_marketing`, `agent_commercial`)
- `ville` : utilisée pour l'administration de ville
- `agence` : utilisée pour les utilisateurs liés à une agence
- `statut` : état du compte (`en_attente`, `actif`, `suspendu`)
- `telephone`, `date_demande`, `date_validation`, `tentatives_connexion`, `est_bloque`, `valide_par`

Règles métier importantes :

- `admin` et `super_admin` ne peuvent pas être rattachés à une `agence`.
- `chef_agence`, `agent_marketing`, `agent_commercial` doivent obligatoirement être rattachés à une `agence`.
- `super_admin` et `admin` sont automatiquement `actif` lors de la sauvegarde.

La méthode `clean()` vérifie ces contraintes et empêche la sauvegarde si elles sont violées.

### 2.3 `AdminVille`

Fichier : `accounts/models.py`

`AdminVille` est un modèle dédié qui relie un utilisateur à une ville.

- `user` : relation `OneToOne` vers `User`
- `ville` : relation vers `Ville`
- `date_nomination` et `actif`

Cette table est utilisée pour connaître la ville d'un admin de ville sans impacter la logique des agents rattachés aux agences.

Permissions ajoutées :

- `valider_chef_agence`
- `gerer_utilisateurs_ville`

---

## 3. Rôles et accès métier

### 3.1 `super_admin`

- accès global à l'administration et à toutes les villes.
- peut créer des villes.
- peut gérer toutes les agences et tous les utilisateurs.
- peut consulter l'historique de toutes les agences.
- implémenté dans `dashboard/views.py` via `request.user.role == "super_admin" or request.user.is_superuser`.

### 3.2 `admin` (Administrateur de ville)

- gère uniquement une ville donnée.
- ne voit que les agences de sa ville.
- ne peut pas accéder au dashboard global des agences hors de sa ville.
- ne peut pas créer de nouvelles villes.
- implémenté dans `dashboard/views.py` avec `admin_ville = request.user.admin_ville.ville`.

### 3.3 `chef_agence`

- rattaché à une agence.
- peut lancer une analyse dans son agence.
- visualise le dashboard de son agence.
- la logique de validation du rôle est contrôlée par `User.clean()` qui exige `agence`.

### 3.4 `agent_marketing` et `agent_commercial`

- usages métiers orientés consultation.
- ne peuvent pas accéder au tableau de bord KPI principal.
- sont redirigés vers `dashboard/accueil_agent.html`.

---

## 4. Flux principal et pages clés

### 4.1 Page d'accueil générale

Fichier : `dashboard/views.py`, fonction `accueil(request)`.

Comportement :

- si l'utilisateur est `admin` ou `super_admin`, il est redirigé vers `accounts:gestion_comptes`.
- si l'utilisateur est `agent_marketing` ou `agent_commercial`, il est rendu sur `dashboard/accueil_agent.html`.
- sinon, on charge des métriques et le dashboard principal.
- si l'utilisateur n'a pas d'agence, il est redirigé vers `accounts:assign_agence`.

#### Chargement des métriques ML

- le code cherche le fichier `pfe_final/churn_api/fastapi_artifacts/churn_metadata_v1.json`.
- si le fichier existe, on lit `metriques_test` et on construit la liste `ml_models`.
- si le fichier est absent, le code affiche maintenant un message clair via `metadata_warning`.

### 4.2 Page administration

Fichier : `dashboard/views.py`, fonction `administration(request)`.

Comportement :

- accessible uniquement par `super_admin` et `admin`.
- `super_admin` voit toutes les villes.
- `admin` voit uniquement sa ville (via `AdminVille`).
- la vue collecte les agences et les utilisateurs de chaque ville.
- elle passe à la template des synthèses : `total_villes`, `total_agences`, `total_users`, `total_en_attente`.

### 4.3 Affectation d'agence

Fichier : `dashboard/views.py`, fonction `assign_agence(request)`.

- si l'utilisateur a besoin d'une agence, il choisit une agence via `AgenceForm`.
- le formulaire utilise `core.models.Agence`.
- après validation, l'utilisateur est redirigé vers `dashboard:accueil`.

---

## 5. Données d'analyse et historique

### 5.1 `AnalyseSession`

Fichier : `dashboard/models.py`

Ce modèle stocke les résultats d'une analyse churn par agence :

- `agence`, `lancee_par`, `date_analyse`
- compteurs : `nb_clients_total`, `nb_clients_churn`, `nb_clients_non_churn`
- métriques de performance du modèle : `seuil_optimal`, `auc_roc`, `f1_score`, `recall`, `precision`
- métriques de volume et de génération : `score_churn_moyen`, `nb_recommandations_generees`
- `methode` : `mock`, `csv`, `api`
- `supprimee` et `date_suppression`
- `notes`

La méthode `get_differences_with_previous()` calcule les écarts par rapport à la session précédente pour montrer l'évolution entre deux runs.

### 5.2 Génération de données mock

Fichier : `dashboard/views.py`, fonction `generer_mock(request)`.

- seul le `chef_agence` peut générer des données mock (ou `super_admin`).
- la génération de mock appelle `core.mock_data.generer_mock_data(...)` avec 50 clients.
- le mode mock est protégé par `DEBUG=True` : il ne doit pas être utilisé en production.
- après génération des données, le code calcule un score churn simple via règles métier :
  - `score = min(0.3 + nb_reclamations*0.1 + retards_paiement*0.15, 0.95)`
  - `churn_predit = score >= 0.32`
- ces clients mock sont stockés dans la base et peuvent être analysés comme des clients réels.

### 5.3 Lancer une analyse réelle ou mock

Fichier : `dashboard/views.py`, fonction `lancer_analyse(request)`.

#### Droits d'accès

- seulement le `chef_agence` ou `super_admin` peut lancer une analyse.

#### Analyse CSV (`methode == "csv"`)

- si un fichier CSV est uploadé, il est lu par `_read_uploaded_dataset()`.
- le code accepte `csv`, `txt`, `tsv`, `tab`, `xlsx`, `xls`, `xlsm`.
- avant d’importer un nouveau dataset réel, le système supprime uniquement les anciens clients `mock` ou sans dataset pour cette agence.
- la conversion du DataFrame en dataset utilise `learning.importers.create_dataset_from_dataframe()`.
- ceci crée de nouveaux enregistrements `ClientChurn` et associe le dataset à l’agence.

#### Analyse mock (`methode == "mock"`)

- le système supprime d'abord les anciens clients mock existants pour l'agence.
- il régénère 50 clients mock frais via `core.mock_data.generer_mock_data()`.
- les clients mock sont stockés dans la base avec `dataset__methode = "mock"` ou `dataset` null.

#### Prédictions et FastAPI

- après import ou génération mock, la vue `lancer_analyse` construit un DataFrame de prédiction à partir des clients concernés.
- le service appelle l’API FastAPI via `core.fastapi_service.predict_batch_from_dataframe()`.
- la santé de FastAPI est vérifiée via `core.fastapi_service.check_fastapi_health()`.
- si FastAPI n’est pas disponible, le process s’arrête avec un message d’erreur et il n’y a pas de 
 local.
- la probabilité renvoyée par l’API est stockée dans `ClientChurn.score_churn`.
- la prédiction binaire `ClientChurn.churn_predit` est calculée avec le seuil `0.32`.

#### Différence entre mock et réel

- les clients mock sont traités via le même pipeline de scoring FastAPI que les clients réels.
- dans la vue, le filtrage distingue :
  - mock : `dataset__methode="mock"` ou `dataset__isnull=True`
  - réel : `dataset__agence=request.user.agence`
- cela garantit que les analyses mock et réelles peuvent être comparées sur le même dashboard.

### 5.4 Attribution des recommandations

Fichier : `core/notifications_engine.py`.

- les recommandations automatiques sont générées par `generer_recommandations_et_notifs(client, agence, createur=None)`.
- le moteur applique un jeu de règles métier sur chaque client churn : score critique, réclamations élevées, retards de paiement, ancienneté, consommation, etc.
- pour chaque règle satisfaite, il crée une `Recommandation` avec :
  - `type_recommandation` : `marketing`, `commercial` ou `technique`
  - `contenu` : texte métier dynamique construit à partir des attributs du client
  - `echeance` : date de fin (14 jours par défaut)
  - `statut = "active"`
  - `generee_par_systeme = True`
  - `clv_estimee` : estimation de la valeur client (binôme marketing/priorisation)
- le pipeline limite à 3 recommandations maximum par client et priorise selon la priorité métier puis l’estimation CLV.

#### Attribution aux agents

- la correspondance type → rôle est définie dans `ROLE_PAR_TYPE` :
  - `marketing` → `agent_marketing`
  - `commercial` → `agent_commercial`
  - `technique` → `chef_agence`
- après création, le moteur notifie automatiquement les utilisateurs actifs de l’agence disposant du rôle ciblé.
- chaque notification inclut un lien vers la fiche client et un résumé de la recommandation.

#### Flux de validation

- les recommandations système sont directement actives.
- les recommandations manuelles peuvent nécessiter validation du chef d’agence selon le parcours utilisé.
- la clôture effective passe par :
  - l’agent marque la recommandation comme terminée (`completee_agent`)
  - le chef d’agence valide ou refuse la complétion

### 5.5 Dashboard global et différences mock/réel

Fichier : `dashboard/views.py`, fonction `dashboard_global(request)`.

- cette page est le dashboard d'agence pour les `chef_agence` et les agents.
- elle affiche : total clients, taux de churn, recommandations, top clients et explications SHAP.
- elle prend les clients de l’agence uniquement : `ClientChurn.objects.filter(dataset__agence=agence)`.
- les analyses mock sont visibles de la même façon que les analyses réelles si elles sont stockées dans la même agence.

### 5.5 Historique des analyses

Fichier : `dashboard/views.py`, fonction `historique_analyses_view(request)`.

- affiche toutes les `AnalyseSession` non supprimées pour l’agence.
- permet un filtrage par type : `all`, `mock`, `real`.
- `mock` filtre `methode="mock"`.
- `real` exclut les sessions `methode="mock"`.
- les sessions sont groupées par mois et classées par date décroissante.
- chaque ligne de l’historique est cliquable et redirige vers la liste des clients associée à la session.
- la vue `liste_clients(request)` utilise désormais le paramètre `analyse_id` pour charger exactement les clients de cette session.
- le filtrage historique se fait sur le dataset de la session (`dataset__agence`, `dataset__methode`, `dataset__date_chargement__date`) plutôt que sur une date de prédiction globale.
- les anciens jeux de données restent historisés avec `dataset__actif=False` au lieu d’être supprimés, ce qui préserve l’historique des analyses et des clients.

### 5.6 Historique agence

Fichier : `dashboard/views.py`, fonction `historique_agence_view(request, agence_id)`.

- accessible par `super_admin` et `admin`.
- si l'utilisateur est `admin`, il ne peut consulter que les agences de sa ville.
- le template affiche les sessions d'analyse et les différences successives.

### 5.7 Axes du travail et améliorations invisibles

Cette partie rassemble les axes de travail principaux, y compris les modifications qui ne sont pas toujours visibles à l’écran.

- Navigation historique précise
  - l’historique redirige vers la liste de clients spécifique à une `AnalyseSession` via le paramètre `analyse_id`.
  - la vue `liste_clients` recharge les clients avec les mêmes métadonnées que la session : `dataset__agence`, `dataset__methode`, `dataset__date_chargement__date`.
  - cela évite les erreurs de filtre basées uniquement sur une date de chargement ou sur un groupe de clients plus large.
- Conservation de l’historique des datasets
  - les anciens jeux de données ne sont pas supprimés.
  - ils sont désactivés (`dataset.actif=False`) pour préserver l’historique et permettre des consultations rétroactives.
- Séparation mock vs réel
  - les données mock sont clairement distinguées des données réelles dans le pipeline.
  - le filtre utilise `dataset__methode="mock"` ou `dataset__isnull=True` pour mock, et `dataset__agence=request.user.agence` pour réel.
- Gestion du metadata et du fallback
  - le code ne présente plus de métriques de modèle si `churn_metadata_v1.json` est absent.
  - une alerte claire `metadata_warning` est affichée plutôt qu’un fallback silencieux.
  - `core/model_config.py` reste une base documentaire et technique, mais n’est pas utilisée comme source de vérité en production.
- Droits et sécurité métier
  - les rôles sont appliqués partout : `chef_agence`, `admin`, `super_admin`, `agent_marketing`, `agent_commercial`.
  - les vues sensibles sont protégées et les `admin` de ville ne voient que les données de leur ville.
- Robustesse et qualité
  - validation et manipulation sûre de `analyse_id` et `date` dans les URLs.
  - utilisation de `Coalesce` pour éviter les valeurs nulles sur `anciennete_mois`.
  - routes POST protégées avec `require_POST` et messages utilisateur clairs.
- Améliorations de l’expérience utilisateur
  - lignes d’historique cliquables et boutons de filtrage explicites.
  - en-tête de liste des clients affichant la date de la session sélectionnée.
  - messages d’erreur plus lisibles et retours explicites pour l’utilisateur.

---

## 6. Fallback technique du metadata

### 6.1 Ancien fonctionnement

Initialement, si `churn_metadata_v1.json` manquait, le code utilisait les valeurs de `core/model_config.py` comme fallback silencieux.

### 6.2 Fonctionnement actuel

Le code de `dashboard/views.py` a été modifié pour :

- détecter l'absence du fichier JSON
- ne plus injecter automatiquement des métriques statiques
- afficher un message clair `metadata_warning`
- n'afficher des métriques que si le metadata est bien présent
- ne pas faire de fallback de production lorsque le metadata est manquant : l’interface reste honnête et ne présente pas de résultats de modèle factices

### 6.3 Rôle de `core/model_config.py`

Ce fichier contient :

- `MODEL_METRICS` : métriques par défaut du modèle
- `MODEL_HYPERPARAMETERS` : hyperparamètres du modèle XGBoost
- `SHAP_FEATURES` : top 10 des variables expliquées
- `SHAP_INTERPRETATIONS` : interprétations de feature importances

Il est désormais utilisé comme documentation technique et base statique, mais pas comme fallback de production.

---

## 7. Template et interface

### 7.1 Dashboard agence

Template : `dashboard/templates/dashboard/accueil.html`

- affichage de l'état des clients churn/non-churn
- sélection de modèle ML
- zone de résultat interactive
- message d'avertissement si pas de données ou pas de metadata

### 7.2 Administration

Template : `dashboard/templates/dashboard/administration.html`

- page centrale de gestion des villes/agences/utilisateurs
- pour `super_admin`, actions sur toutes les villes
- pour `admin`, actions limitées à sa ville
- section KPI et onglets agences
- modals de création et modification

### 7.3 Historique agence

Template : `dashboard/templates/dashboard/historique_agence.html`

- affichage de l'historique par agence
- bouton de retour vers l'administration
- suppression du lien vers le dashboard global pour un `admin` de ville

---

## 8. Contrôle d'accès et droits dans le code

### 8.1 Vues protégées

Une grande partie du back-end utilise `@login_required`.

Exemples de contrôles supplémentaires :

- `accueil()` : redirection des agents marketing/commerciaux
- `administration()` : vérifie `super_admin` ou `admin`
- `historique_agence_view()` : restreint l'accès des `admin` à leur ville
- `assign_agence()` : formation et association à une agence

### 8.2 Permissions custom

`AdminVille.Meta.permissions` définit des permissions spécifiques, même si elles ne sont pas toutes exploitées directement dans le code :

- `valider_chef_agence`
- `gerer_utilisateurs_ville`

Ces permissions sont principalement utiles pour la future gestion fine des opérations.

---

## 9. Points techniques importants à maîtriser

### 9.1 Django ORM et relations

- `ForeignKey(Ville)` dans `Agence`
- `ForeignKey(Agence)` dans `User` et `AnalyseSession`
- `OneToOneField(User)` dans `AdminVille`
- `related_name` permet d'accéder aux objets liés depuis l'autre côté

### 9.2 Gestion des rôles

- rôle principal stocké dans `User.role`
- `is_superuser` utilisé pour le super admin technique
- `clean()` impose les contraintes métier
- l'attribut `statut` contrôle l'état du compte

### 9.3 Workflow de gestion

- création/utilisateur -> validation -> activation
- `admin` et `super_admin` active automatiquement le compte
- `chef_agence` / agents doivent être liés à une agence

### 9.4 Lecture des artifacts ML

- fichier JSON `churn_metadata_v1.json` lu depuis `pfe_final/churn_api/fastapi_artifacts`
- structure attendue : `modele`, `metriques_test`, `seuil_decision`
- si absent, message d'alerte visible plutôt que métriques fausses

### 9.5 Calculs et sessions

- `AnalyseSession` permet de mesurer l'évolution de churn agence par agence
- valeurs clé : `nb_clients_total`, `nb_clients_churn`, `score_churn_moyen`, `auc_roc`, `f1_score`, `recall`
- `get_differences_with_previous()` calcule les deltas entre sessions successives

---

## 10. Résumé pour la soutenance

1. **Comprendre les rôles** : `super_admin`, `admin`, `chef_agence`, `agent_marketing`, `agent_commercial`.
2. **Savoir où sont les règles** : `accounts/models.py` pour les rôles et la validation, `dashboard/views.py` pour les accès et la logique.
3. **Expliquer le fallback** : c'est un mécanisme d'affichage, pas une source de vérité. Le JSON de metadata est prioritaire.
4. **Montrer le workflow** : affectation d'agence, lancement d'analyse, historisation des sessions, vue administration.
5. **Maîtriser les pages** : `accueil`, `administration`, `historique_agence`, `accueil_agent`.

---

## 11. Fichiers clés à connaître

- `accounts/models.py`
- `accounts/forms.py`
- `core/models.py`
- `dashboard/views.py`
- `dashboard/models.py`
- `core/model_config.py`
- `dashboard/templates/dashboard/accueil.html`
- `dashboard/templates/dashboard/administration.html`
- `dashboard/templates/dashboard/historique_agence.html`

---

## 12. Annexes utiles

### Rôle du fichier `accounts/forms.py`

`AgenceForm` affiche un champ `ModelChoiceField` sur toutes les agences disponibles pour l'affectation d'un utilisateur.

### Lien avec la base de données

- `Ville` et `Agence` sont des entités métier de base.
- `User` connecte les utilisateurs aux agences/villes.
- `AnalyseSession` historise les résultats churn.

---

## 13. Conseils pour la soutenance

- Parle en termes de « niveau d'accès » : super-admin > admin de ville > chef d'agence > agents.
- Mentionne que le projet est conçu pour garder une séparation nette entre l'administration de ville et l'opérationnel d'agence.
- Explique le passage du metadata JSON vers le rendu UI comme un point d'intégration entre le back-end Django et la partie ML/FastAPI.
- Si on te demande un point technique, cite la restriction métier `admin` ne peut pas avoir d'agence et `chef_agence` doit en avoir une.

---

Ce document peut servir de base pour la soutenance ou comme support de révision. Si tu veux, je peux aussi générer une version encore plus synthétique en mode « fiche rôle / fiche pages ». 