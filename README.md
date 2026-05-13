# Gestion du Churn Client — Tunisie Telecom

Système de gestion du churn client avec workflow de validation hiérarchique et notifications temps réel.

Développé pour Tunisie Telecom — Agence de Kairouan

---

## Installation

### Prérequis

- Python 3.11+
- PostgreSQL 14+
- Windows

### 1. Cloner et configurer l'environnement

```bash
git clone <repository-url>
cd CHURN
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configurer la base de données

```bash
createdb churn_db
python manage.py makemigrations
python manage.py migrate
```

### 3. Créer le superutilisateur

```bash
python manage.py createsuperuser
```

### 4. Lancer le serveur

```bash
python manage.py runserver
```

### 5. Générer des données de test

```bash
python manage.py shell
```

```python
from core.mock_data import generer_mock_data
from accounts.models import User
from core.models import Agence

user = User.objects.filter(role='agent_commercial').first()
agence = Agence.objects.first()
generer_mock_data(user, agence, nb_clients=50)
```

---

## Configuration

### Variables d'environnement (.env)

```bash
SECRET_KEY=votre-cle-secrete
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
DB_NAME=churn_db
DB_USER=postgres
DB_PASSWORD=votre_mot_de_passe
DB_HOST=localhost
DB_PORT=5432
SENDGRID_API_KEY=votre-cle-sendgrid
DEFAULT_FROM_EMAIL=churn@tunisietelecom.tn
```

---

## Utilisation

1. Créer une agence via l'admin Django (`/admin`)
2. Créer des utilisateurs avec leurs rôles respectifs
3. Générer des clients mock ou importer des données CSV
4. Consulter le dashboard pour voir les clients à risque
5. Examiner les recommandations générées automatiquement
6. Prendre des actions de rétention et marquer les recommandations

---

## Stack technique

- Python 3.11+ / Django 4.2+
- PostgreSQL 14+
- scikit-learn / XGBoost / SHAP
- Bootstrap 5 / Chart.js
