# =============================================================================
# tests_manuels/test_routers.py
# Inspection des routers FastAPI sans démarrer le serveur
# =============================================================================

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.routers import system, model, prediction


def lister_routes(router, nom: str) -> None:
    print(f"\n--- {nom} ---")
    for route in router.routes:
        # Affiche les méthodes HTTP et le path
        methodes = ",".join(route.methods)
        print(f"  {methodes:<8} {route.path:<25} ({route.name})")


print("=" * 70)
print("  INSPECTION DES ROUTERS FastAPI")
print("=" * 70)

lister_routes(system.router,     "router system")
lister_routes(model.router,      "router model")
lister_routes(prediction.router, "router prediction")

print("\n" + "=" * 70)
print("  Total : 6 endpoints sur 8 prevus (les 2 derniers a l'Etape 6)")
print("=" * 70)