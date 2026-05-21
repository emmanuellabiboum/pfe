# Intégration de l'API FastAPI dans le Dashboard Django

## 📋 Résumé des modifications

J'ai intégré l'API FastAPI `/api/predict/batch` dans le dashboard Django pour utiliser le même modèle ML centralisé. Voici les changements :

## 🔧 Fichiers modifiés

### 1. **core/fastapi_service.py** (NOUVEAU)
Service helper pour communiquer avec l'API FastAPI depuis Django.

**Fonctions principales :**
- `check_fastapi_health()` - Vérifie que l'API FastAPI est accessible
- `get_model_info()` - Récupère les infos du modèle
- `predict_batch_from_dataframe(df)` - Appelle `/api/predict/batch` pour prédire en batch
- `predict_single_client(features)` - Appelle `/api/predict` pour une seule prédiction
- `analyse_portefeuille_from_csv(csv_bytes)` - Appelle `/api/analyse` pour l'analyse du portefeuille

### 2. **dashboard/views.py** (MODIFIÉ)
Modification de la vue `lancer_analyse()` pour :
- Appeler l'API FastAPI en priorité avec `predict_batch_from_dataframe()`
- Fallback sur les prédictions locales si l'API est indisponible
- Sauvegarder les résultats dans Django (BDD)
- Retourner les mêmes statistiques qu'avant

**Logique :**
```python
# Si API FastAPI disponible ET clients existent
→ Créer DataFrame avec données clients
→ Appeler /api/predict/batch
→ Sauvegarder résultats en BDD Django
→ Sinon : utiliser prédictions locales
```

### 3. **churn_api/app/main.py** (BACKEND ML)
Application FastAPI avec les modèles entraînés Random Forest.

**Modèles disponibles dans `churn_api/fastapi_artifacts/`:**
- `churn_model_v1.pkl` - Modèle Random Forest entraîné
- `shap_explainer_v1.pkl` - Explainer SHAP
- `churn_threshold_v1.pkl` - Seuil de décision (0.32)
- `preprocessing_params.json` - Paramètres de preprocessing
- `feature_names_v1.json` - Noms des features
- `churn_metadata_v1.json` - Métadonnées du modèle

**Métriques du modèle:**
- AUC: 0.8954
- F1-score: 0.7797
- Recall: 0.9200
- Seuil optimal: 0.32

### 4. **requirements.txt** (MODIFIÉ)
Ajout des dépendances :
```txt
fastapi>=0.95.0
uvicorn>=0.20.0
httpx>=0.24.0
```

## 🚀 Comment ça marche

### Flux normal (API FastAPI disponible) :

```
Dashboard (Django)
    ↓
lancer_analyse()
    ↓
check_fastapi_health() → ✓ OK
    ↓
predict_batch_from_dataframe(df_clients)
    ↓
API FastAPI (/api/predict/batch)
    ↓
Résultats + probabilités
    ↓
Sauvegarder en BDD Django
    ↓
Retourner statistiques
```

### Fallback (API FastAPI indisponible) :

```
Dashboard (Django)
    ↓
check_fastapi_health() → ✗ Erreur
    ↓
Basculer sur predict_churn_score_from_client()
    ↓
Utiliser le modèle local Django
```

## 📦 Installation

```bash
# Installer les nouvelles dépendances
pip install -r requirements.txt

# Ou manuellement
pip install httpx>=0.24.0 fastapi>=0.95.0 uvicorn>=0.20.0
```

## 🔗 API FastAPI utilisée

L'intégration utilise les endpoints de `churn_api/app/main.py` :

```python
POST /api/predict/batch
Input:  CSV file avec colonnes de features
Output: {
    "total": int,
    "haut_risque": int,
    "faible_risque": int,
    "score_moyen": float,
    "taux_churn": float,
    "nb_recommandations": int
}
```

## ✅ Avantages

1. **Unification** : Même modèle ML utilisé partout (Django et FastAPI)
2. **Résilience** : Fallback automatique si API indisponible
3. **Scalabilité** : Permet de déployer l'API sur un serveur séparé
4. **Maintenance** : Mise à jour du modèle au seul endroit (FastAPI)

## ⚙️ Configuration

**FastAPI doit tourner sur `localhost:8000`** (ou modifier `FASTAPI_BASE_URL` dans `core/fastapi_service.py`)

Pour démarrer l'API :
```bash
.\.venv\Scripts\Activate.ps1
python -m uvicorn pfe_final.churn_api.app.main:app --reload --port 8000
```

Pour Django (sur un port différent) :
```bash
.\.venv\Scripts\Activate.ps1
python manage.py runserver 8080
```

## 🧪 Test

Le fallback automatique garantit que même si l'API n'est pas disponible, l'application continue de fonctionner avec les prédictions locales.

---

**Status** : Intégration terminée et testée
