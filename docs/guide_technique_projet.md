# Guide Technique Detaille — Projet CHURN

## 1) Vue d'ensemble du projet

Ce projet implemente une plateforme de **gestion et prediction du churn client** pour un contexte telecom.  
L'application combine :

- un **backend Django** (authentification, dashboard, gestion des clients, notifications, historique),
- une **API FastAPI** (inference ML et endpoints de prediction/explication),
- une **base PostgreSQL** (stockage des donnees metier),
- un pipeline ML base sur **scikit-learn + XGBoost + SHAP**.

Le workflow principal :

1. Import d'un dataset reel (CSV/Excel/TXT/TSV) ou generation mock.
2. Creation/mise a jour des `Dataset` et `ClientChurn`.
3. Lancement d'analyse via Django (`/lancer-analyse/`).
4. Appel prioritaire de FastAPI (`/api/predict/batch`) avec fallback local.
5. Sauvegarde des scores, calcul KPI, generation recommandations/notifications.

---

## 2) Technologies et versions

## 2.1 Versions declarees (requirements)

Source: `requirements.txt`

- **Django** `>=4.2,<5.0`
- **psycopg2-binary** `>=2.9.9`
- **python-decouple** `>=3.8`
- **python-dotenv** `>=1.0.0`
- **scikit-learn** `>=1.3.0`
- **xgboost** `>=2.0.0`
- **shap** `>=0.42.0`
- **joblib** `>=1.3.0`
- **numpy** `>=1.24.0`
- **pandas** `>=2.0.0`
- **pdfkit** `>=1.0.0`
- **Pillow** `>=10.0.0`
- **sendgrid** `>=6.9.0`
- **fastapi** `>=0.95.0`
- **uvicorn** `>=0.20.0`
- **httpx** `>=0.24.0`
- **python-multipart** `>=0.0.9`
- **django-cors-headers** `>=4.0.0`
- **django-ratelimit** `>=4.0.0`
- **ipython** `>=8.0.0`
- **django-extensions** `>=3.2.0`

## 2.2 Versions installees constatees dans `.venv`

- **Django** `4.2.30`
- **FastAPI** `0.136.1`
- **Uvicorn** `0.46.0`
- **httpx** `0.28.1`
- **pandas** `3.0.2`
- **scikit-learn** `1.8.0`
- **xgboost** `3.2.0`
- **shap** `0.51.0`

---

## 3) Roles des technologies dans l'architecture

## 3.1 Django (coeur metier web)

Django porte la logique metier et les ecrans :

- authentification et gestion des comptes (`accounts`),
- dashboard, analyses, KPI, historiques et notifications (`dashboard`),
- modeles metier (`learning`, `core`),
- integration API FastAPI via `core/fastapi_service.py`.

### Fichiers structurants

- `config/settings.py` : configuration globale (DB, auth, static, mail, securite).
- `config/urls.py` : routes racine.
- `dashboard/views.py` : orchestration des cas d'usage d'analyse.
- `dashboard/urls.py` : endpoints applicatifs.
- `learning/models.py` : `Dataset`, `ClientChurn`, etc.

## 3.2 FastAPI (service de prediction)

FastAPI expose les endpoints ML dans `churn_pfe/backend/app.py` :

- health check,
- informations modele,
- prediction unitaire,
- prediction batch CSV,
- analyse portefeuille,
- endpoint SHAP et listing clients scores.

`python-multipart` est requis pour les endpoints `UploadFile`.

## 3.3 PostgreSQL

PostgreSQL est la base principale (`django.db.backends.postgresql`) configuree dans `config/settings.py` via:

- `DB_NAME`
- `DB_USER`
- `DB_PASSWORD`
- `DB_HOST`
- `DB_PORT`

## 3.4 ML Stack

- **scikit-learn** : base pipeline/preprocessing et metriques.
- **xgboost** : modele fort pour classification churn.
- **shap** : explications locales/globales.
- **joblib** : serialisation/chargement des artefacts (`.pkl`).
- **pandas/numpy** : traitement tabulaire et transformations.

## 3.5 Outils transverses

- **httpx** : client HTTP entre Django et FastAPI.
- **sendgrid** : envoi mail (SMTP).
- **pdfkit + wkhtmltopdf** : generation PDF.
- **PowerShell script** `start_all.ps1` : demarrage simultane FastAPI + Django.

## 3.6 Microservices / services internes du projet

Le projet n'est pas decoupe en microservices deployes independamment (type Kubernetes + plusieurs repos), mais il est organise en **services internes modulaires** qui jouent ce role fonctionnel.

### Service 1 — Inference API (FastAPI)

- Fichier: `churn_pfe/backend/app.py`
- Role: servir les predictions ML via HTTP (`/api/predict`, `/api/predict/batch`, `/api/analyse`).
- Consommateur: Django, via `core/fastapi_service.py`.
- Valeur: permet de separer le moteur de prediction de l'interface metier.

### Service 2 — Integration FastAPI cote Django

- Fichier: `core/fastapi_service.py`
- Fonctions cle: `check_fastapi_health()`, `predict_batch_from_dataframe()`, `predict_single_client()`, `analyse_portefeuille_from_csv()`.
- Role: encapsuler les appels HTTP avec `httpx`, gerer timeouts et erreurs, eviter de dupliquer la logique reseau dans les vues.

### Service 3 — ML local (fallback et SHAP)

- Fichier: `core/ml_service.py`
- Role: charger les artefacts modele localement (`.pkl` + metadata), produire un score si FastAPI est indisponible, fournir des explications SHAP.
- Fonctions cle: `load_ml_model()`, `predict_churn_score_from_client()`, `get_shap_explanation()`.

### Service 4 — OTP et verification

- Fichier: `core/otp_service.py`
- Role: generation/validation OTP avec expiration, statut (`ACTIVE`, `USED`, `EXPIRED`, `REVOKED`) et limitation de taux.
- Points forts: gestion attempts, contexte OTP (`reset_password`, `validation_email`, etc.), utilitaires pour les vues.

### Service 5 — Envoi OTP par email

- Fichier: `core/otp_email_service.py`
- Role: envoyer les OTP en SMTP (SendGrid) avec template HTML et contexte personnalise.
- Fonction cle: `envoyer_email_otp(...)`.

### Service 6 — ML service orientee modeles

- Fichier: `learning/ml_service.py`
- Role: charger Voting Ensemble + modeles individuels, scaler et seuil, realiser predictions unitaires/batch.
- Note: contient aussi un mode `mock_predict` de secours.

---

## 4) Configuration et execution

## 4.1 Variables d'environnement

Variables critiques (depuis `.env` / `README.md`) :

- `SECRET_KEY`
- `DEBUG`
- `ALLOWED_HOSTS`
- `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`
- `SENDGRID_API_KEY`
- `DEFAULT_FROM_EMAIL`

## 4.2 Ports de developpement

- Django: `http://127.0.0.1:8080/`
- FastAPI docs: `http://127.0.0.1:8000/docs`

## 4.3 Demarrage

Option manuelle :

```powershell
# Terminal 1
python -m uvicorn churn_pfe.backend.app:app --reload --port 8000

# Terminal 2
python manage.py runserver 8080
```

Option script :

```powershell
powershell -ExecutionPolicy Bypass -File .\start_all.ps1
```

---

## 5) Endpoints FastAPI (service ML)

Source: `churn_pfe/backend/app.py`

## 5.1 Systeme

- `GET /health`  
  Retourne statut API, version et seuil.

## 5.2 Modele

- `GET /api/model/info`  
  Retourne metriques, seuil, features.

- `POST /api/train`  
  Retourne une simulation de metriques modeles (pas de re-entrainement online).

## 5.3 Prediction

- `POST /api/predict`  
  Prediction unitaire avec explications SHAP.

- `POST /api/predict/batch`  
  Prediction batch via upload CSV.

- `POST /api/analyse`  
  Analyse portefeuille et agregats (`haut_risque`, `moyen_risque`, etc.).

- `GET /api/shap/{client_id}`  
  Explication SHAP detaillee d'un client.

- `GET /api/clients`  
  Liste clients scores avec filtres de risque + pagination.

---

## 6) Endpoints Django (application metier)

Sources: `config/urls.py`, `dashboard/urls.py`, `accounts/urls.py`

## 6.1 Racine

- `GET /` → accueil dashboard (`dashboard:accueil`)

## 6.2 Comptes

Prefixe: `/accounts/`

- `/login/`, `/inscription/`, `/verify-otp/`, `/assign-agence/`
- `/reset-password/`, `/roles-disponibles/`
- `/gestion-comptes/`, `/action-compte/<user_id>/`, `/profile/`

## 6.3 Dashboard & analyses

- `/clients/`
- `/lancer-analyse/`
- `/train-models/`
- `/generer-mock/`
- `/reinitialiser/`
- `/dashboard-global/`
- `/historique-analyses/`

## 6.4 Notifications

- `/notifications/`
- `/notifications/api/`
- operations detail / archive / restauration / suppression bulk

## 6.5 Administration metier

- `/administration/`
- `/administration/vider-table/`
- `/administration/toggle-user/<user_id>/`
- `/administration/reset-database/`

## 6.6 Endpoints comptes / OTP (detail)

Sous prefixe `/accounts/`:

- `POST|GET /accounts/login/` : connexion utilisateur.
- `POST|GET /accounts/inscription/` : creation compte.
- `POST|GET /accounts/verify-otp/` : verification code OTP.
- `POST|GET /accounts/assign-agence/` : rattachement agence.
- `POST|GET /accounts/reset-password/` : flux mot de passe.
- `GET /accounts/roles-disponibles/` : roles autorises.
- `GET /accounts/profile/` : profil courant.

---

## 7) Flux applicatifs majeurs

## 7.1 Flux A — Analyse sur dataset reel

1. UI envoie `POST /lancer-analyse/` avec `methode=csv` + fichier.
2. Django lit le fichier et cree `Dataset` + `ClientChurn`.
3. Django teste FastAPI (`/health`).
4. Si OK → envoi batch a `/api/predict/batch`.
5. Mapping des predictions vers `score_churn`, `churn_predit`, `niveau_risque`.
6. Calcul KPI, creation `AnalyseSession`.
7. Generation recommandations + notifications.

## 7.2 Flux B — Donnees mock

1. UI declenche generation mock (`/generer-mock/` ou chemin interne).
2. `core/mock_data.py` cree un dataset `methode="mock"` et clients simules.
3. Analyse ensuite identique (FastAPI prioritaire, fallback local sinon).

## 7.3 Flux C — Reinitialisation dashboard

1. UI envoie `POST /reinitialiser/`.
2. Suppression clients/recommandations/analyses de l'agence.
3. UI remet KPI/resultats a l'etat initial.

---

## 8) Donnees et modeles principaux

## 8.1 `learning.Dataset`

Role :

- tracer la source d'un chargement (`csv`, `mock`, etc.),
- relier a une agence et un chargeur,
- stocker le nombre de clients et le fichier source.

## 8.2 `learning.ClientChurn`

Role :

- centraliser attributs client telecom (usage, contrat, engagement),
- stocker sortie prediction (`score_churn`, `churn_predit`, `niveau_risque`),
- maintenir la coherence agence/dataset.

Points importants :

- champ `agence` explicite,
- relation `dataset` (nullable selon le cas),
- surcharge `save()` pour auto-aligner `agence` depuis `dataset` si besoin.

## 8.3 Entites dashboard

- `AnalyseSession` : trace des analyses et metriques.
- `Notification` / `Recommandation` : actions metier post-scoring.

## 8.4 Formulaires Django (important metier)

### Formulaire d'affectation d'agence

- Fichier: `accounts/forms.py`
- Classe: `AgenceForm(forms.Form)`
- Champ principal: `agence = forms.ModelChoiceField(queryset=Agence.objects.all(), label="Agence")`
- Role metier: lors de l'onboarding ou d'un changement de contexte, ce formulaire force la selection d'une agence valide en base, ce qui garantit la segmentation des donnees et la coherence des permissions.

### Ou sont les autres formulaires ?

Dans l'etat actuel du code, la majeure partie des interactions (analyse, reset, actions notifications/recommandations) est geree via vues + requetes AJAX (`fetch`) et non via classes `forms.py` supplementaires.  
Ce choix est coherent avec un dashboard dynamique, mais il peut etre formalise plus tard par des `ModelForm` si vous voulez renforcer la validation serveur par schema de formulaire.

---

## 9) Strategie de tests

## 9.1 Tests unitaires Django (existant)

Source: `learning/tests.py`

Couvre notamment :

- creation et representation `ClientChurn`,
- creation et representation `Dataset`,
- comportement service ML mock (`predict_churn`),
- singleton du service ML.

Commande :

```powershell
python manage.py test learning
```

## 9.2 Test de compilation des fichiers critiques

Source: `test_compile.py`  
Verifie la compilation de:

- `core/fastapi_service.py`
- `dashboard/views.py`
- `churn_pfe/backend/app.py`

Commande :

```powershell
python test_compile.py
```

Note: ce script imprime des symboles Unicode (`✓`, `✗`). Sous certains terminaux Windows, il peut etre utile de remplacer ces caracteres par `OK/ERR`.

## 9.3 Tests API FastAPI (integration)

### Smoke test health

```powershell
python -c "from fastapi.testclient import TestClient; from churn_pfe.backend.app import app; c=TestClient(app); print(c.get('/health').status_code)"
```

### Test batch reelle (CSV)

```powershell
python -c "from fastapi.testclient import TestClient; from churn_pfe.backend.app import app; c=TestClient(app); f={'file':('test.csv', open('datasets/dataset_pfe_brut.csv','rb'),'text/csv')}; r=c.post('/api/predict/batch', files=f); print(r.status_code, r.json().get('total'))"
```

## 9.4 Tests fonctionnels (UI + metier)

Checklist recommandee :

1. Import CSV sur accueil.
2. Lancer analyse et verifier :
   - KPI non grises,
   - zone resultat remplie,
   - historique mis a jour,
   - notifications creees.
3. Reinitialisation dashboard.
4. Cas fallback si FastAPI arretee.
5. Verification isolation par agence (user A ne voit pas clients agence B).

---

## 10) Scripts et commandes utiles

## 10.1 Scripts utilitaires

Dans `scripts/` :

- `check_db.py`, `fix_db.py`, `fix_db.sql`
- `generate_dataset.py`
- `test_email.py`

## 10.2 Commande de gestion import dataset

Source: `learning/management/commands/import_dataset.py`

Exemple :

```powershell
python manage.py import_dataset --file datasets/dataset_pfe_brut.csv --agence "Agence Kairouan" --user admin
```

---

## 11) Points d'attention techniques

1. **Alignement schema DB / modeles Django**  
   Les migrations historiques doivent rester coherentes avec les modeles (`agence_id` non null sur `ClientChurn`).

2. **Mapping FastAPI <-> Django**  
   Les noms de champs doivent etre convertis explicitement si les schemas different.

3. **Niveaux de risque**  
   Respecter les valeurs autorisees Django (`faible`, `moyen`, `eleve`).

4. **Dependances upload FastAPI**  
   `python-multipart` obligatoire pour `UploadFile`.

5. **Logs**  
   Eviter les logs "en dur" dans les vues; centraliser via configuration logging.

---

## 12) Plan d'amelioration recommande

- Ajouter des tests automatises d'integration pour `lancer_analyse` (avec fixture CSV).
- Ajouter une suite de tests API (status + schema reponse).
- Versionner explicitement Python cible (ex: `3.11.x` ou `3.13.x`) via fichier de tooling.
- Ajouter document de troubleshooting (`docs/`) pour erreurs frequentes (port, DB, migration, multipart).
- Ajouter CI minimale (lint + tests unitaires + smoke API).

---

## 13) Resume executif

Le projet est une architecture hybride **Django + FastAPI + ML** avec une logique metier riche (agence, sessions d'analyse, notifications). Les endpoints sont clairement separes entre interface metier (Django) et services de prediction (FastAPI). La base de tests existe deja (unitaires + scripts + smoke), et peut etre etendue vers une couverture integration complete.

