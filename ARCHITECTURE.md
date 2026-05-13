# Architecture de l'application

## Structure du projet

```
CHURN/
├── accounts/          # Authentification et utilisateurs
├── core/              # Modèles partagés (Agence, Ville)
├── dashboard/         # Interface principale
├── learning/          # Données clients et ML
├── config/            # Configuration Django
└── static/            # Fichiers statiques (JS, CSS)
```

## Modules

### accounts
- Gestion des utilisateurs (login, register, OTP)
- Rôles : super_admin, admin_ville, chef_agence, agent_commercial, agent_marketing
- Workflow de validation hiérarchique
- Email OTP pour la double authentification

### core
- Modèles de base : Agence, Ville
- Génération de données mock
- Configuration du modèle ML (métriques, hyperparamètres)
- Service OTP (génération et vérification des codes)
- Moteur de notifications

### dashboard
- Vue d'accueil avec KPIs
- Vue globale du dashboard
- Gestion des recommandations
- Tâches synchrones (vérification des recommandations expirées)
- Templates HTML pour l'interface

### learning
- Modèles de données : ClientChurn, EvenementCDR, InteractionDigitale, Reclamation
- Données mock pour le développement
- Service ML (préparation des données)

### config
- Configuration Django (settings, URLs, WSGI, ASGI)
- Configuration du logging

## Flux de données

1. Utilisateur se connecte → accounts
2. Dashboard affiche les clients → dashboard
3. Données clients provenant de learning
4. Recommandations générées automatiquement → dashboard
5. Notifications envoyées → core/notifications_engine

## Stack

- Backend : Django 4.2, Python 3.11
- Base de données : PostgreSQL
- ML : scikit-learn, XGBoost, SHAP
- Frontend : Bootstrap 5, Chart.js
- Email : SendGrid API
