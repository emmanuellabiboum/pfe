# =============================================================================
# app/main.py — Point d'entrée FastAPI
# PFE — Prédiction du Churn — Tunisie Télécom Agence Kairouan
# =============================================================================
#
# JUSTIFICATION ARCHITECTURALE :
# Ce fichier est volontairement MINIMAL : il ne contient PAS de logique
# métier. Son rôle se limite à :
#   1. Définir le lifespan qui charge les artefacts au démarrage
#   2. Configurer CORS pour permettre les requêtes depuis React
#   3. Assembler les 5 routers en une seule application FastAPI
#
# Toute la logique ML est dans app/ml/, toutes les routes dans app/routers/.
# Cette séparation permet :
#   - Démarrer rapidement (lifespan = 1 seule passe de chargement)
#   - Tester la logique sans serveur (cf. tests_manuels/)
#   - Maintenir facilement (un bug se localise vite)
#
# Pour lancer le serveur :
#   uvicorn app.main:app --reload --port 8000
#
# Documentation interactive (Swagger UI) :
#   http://localhost:8000/docs
#
# Documentation alternative (ReDoc) :
#   http://localhost:8000/redoc

from contextlib import asynccontextmanager

from fastapi                 import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import logging

logger = logging.getLogger(__name__)

# Configuration centrale
from app.config import (
    API_TITLE,
    API_DESCRIPTION,
    API_VERSION,
    CORS_ORIGINS,
    verifier_artefacts,
)

# Mécanisme d'injection des artefacts ML
from app.ml.dependencies import (
    initialiser_artefacts,
    initialiser_shap_matrix,
)

# Routers — un par domaine fonctionnel
from app.routers import system, model, prediction, shap, clients


# =============================================================================
# LIFESPAN — chargement des artefacts au démarrage / cleanup à l'arrêt
# =============================================================================
# Le lifespan est un context manager async qui s'exécute :
#   - AVANT que l'API n'accepte des requêtes (code avant `yield`)
#   - APRÈS le dernier traitement de requête (code après `yield`)
#
# C'est la façon moderne et recommandée par FastAPI (depuis 0.93) de gérer
# les ressources globales comme les modèles ML, les connexions DB, etc.

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Cycle de vie de l'application FastAPI.

    DÉMARRAGE :
      1. Vérification de la présence de tous les artefacts (config.py)
      2. Chargement du modèle, seuil, SHAP explainer, preprocessing params
      3. Chargement de la matrice SHAP du test set
      4. L'API est prête à servir des requêtes

    ARRÊT :
      Pas de cleanup particulier à faire (les artefacts sont en mémoire,
      Python s'occupe de la libérer). On loggue juste un message d'adieu.

    Cette fonction est appelée AUTOMATIQUEMENT par uvicorn / FastAPI :
      - une fois au démarrage (avant `yield`)
      - une fois à l'arrêt (après `yield`, déclenché par Ctrl+C)
    """
    # ─────────────────────────────────────────────────────────────────────────
    # CODE DE DÉMARRAGE
    # ─────────────────────────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("  DÉMARRAGE DE L'API CHURN — TUNISIE TÉLÉCOM KAIROUAN")
    print("=" * 70 + "\n")

    # Vérification des artefacts (plante TÔT si un fichier manque)
    print("Vérification des artefacts...")
    rapport = verifier_artefacts()
    print(f"  ✓ {len(rapport['trouvés'])} artefacts trouvés\n")

    # Chargement du modèle, SHAP explainer, etc.
    initialiser_artefacts()

    # Chargement de la matrice SHAP du test set
    print("\nChargement de la matrice SHAP du test set...")
    initialiser_shap_matrix()

    print("\n" + "=" * 70)
    print(f"  ✓ API PRÊTE — Swagger UI disponible sur http://localhost:8000/docs")
    print("=" * 70 + "\n")

    # ─────────────────────────────────────────────────────────────────────────
    # L'API TOURNE ICI
    # ─────────────────────────────────────────────────────────────────────────
    yield

    # ─────────────────────────────────────────────────────────────────────────
    # CODE D'ARRÊT
    # ─────────────────────────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("  ARRÊT DE L'API — Au revoir !")
    print("=" * 70 + "\n")


# =============================================================================
# CRÉATION DE L'APPLICATION FastAPI
# =============================================================================

app = FastAPI(
    title       = API_TITLE,
    description = API_DESCRIPTION,
    version     = API_VERSION,
    lifespan    = lifespan,
)

from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc: RequestValidationError):
    logger.error(f"Validation error for {request.url}: {exc.errors()}")
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors(), "message": "Payload invalide – vérifiez les champs requis."},
    )


# =============================================================================
# CORS — Cross-Origin Resource Sharing
# =============================================================================
# JUSTIFICATION :
# Le navigateur bloque par défaut les requêtes JavaScript entre origines
# différentes (sécurité du Same-Origin Policy). Comme React tourne sur
# localhost:3000 et FastAPI sur localhost:8000, ce sont des origines
# différentes et React ne peut PAS appeler FastAPI sans cette config CORS.
#
# Les origines autorisées sont définies dans config.py pour pouvoir
# facilement ajouter l'URL de prod après déploiement cloud.

app.add_middleware(
    CORSMiddleware,
    allow_origins     = CORS_ORIGINS,
    allow_credentials = True,
    allow_methods     = ["*"],          # GET, POST, PUT, DELETE, OPTIONS
    allow_headers     = ["*"],          # Authorization, Content-Type, etc.
)


# =============================================================================
# ASSEMBLAGE DES ROUTERS
# =============================================================================
# Chaque routeur (défini dans app/routers/) est inclus dans l'application
# principale. Les préfixes et tags sont déjà définis dans chaque routeur,
# donc on n'a rien à ajouter ici.

app.include_router(system.router)       # GET  /health
app.include_router(model.router)        # GET  /api/model/info, POST /api/train
app.include_router(prediction.router)   # POST /api/predict, /api/predict/batch, /api/analyse
app.include_router(shap.router)         # GET  /api/shap/{client_id}
app.include_router(clients.router)      # GET  /api/clients


# =============================================================================
# ROUTE RACINE — redirection conviviale vers Swagger UI
# =============================================================================
# Si quelqu'un visite http://localhost:8000/ (sans /docs), on lui propose
# directement Swagger UI plutôt qu'une 404.

@app.get(
    "/",
    tags    = ["Système"],
    summary = "Page d'accueil — informations sur l'API",
    include_in_schema = False,        # ne pollue pas la doc avec ça
)
def racine() -> dict:
    """Page d'accueil de l'API — pointe vers Swagger UI."""
    return {
        "message" : "Bienvenue sur l'API de Prédiction du Churn — Tunisie Télécom Kairouan",
        "version" : API_VERSION,
        "documentation": {
            "swagger" : "/docs",
            "redoc"   : "/redoc",
        },
        "endpoints_principaux": {
            "health"     : "GET  /health",
            "predict"    : "POST /api/predict",
            "model_info" : "GET  /api/model/info",
            "shap"       : "GET  /api/shap/{client_id}",
            "clients"    : "GET  /api/clients",
        },
    }