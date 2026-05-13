# =============================================================================
# tests_manuels/test_routers_full.py
# Inspection complète de tous les routers (Étapes 5 + 6)
# =============================================================================

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.routers import system, model, prediction, shap, clients


def lister_routes(router, nom: str) -> None:
    print(f"\n--- {nom} ---")
    for route in router.routes:
        methodes = ",".join(sorted(route.methods))
        # path peut contenir des paramètres comme {client_id}
        print(f"  {methodes:<8} {route.path:<35} ({route.name})")


print("=" * 70)
print("  INSPECTION COMPLETE DES 5 ROUTERS")
print("=" * 70)

lister_routes(system.router,     "router system")
lister_routes(model.router,      "router model")
lister_routes(prediction.router, "router prediction")
lister_routes(shap.router,       "router shap")
lister_routes(clients.router,    "router clients")

# Compteur total
total_routes = (
    len(system.router.routes)
    + len(model.router.routes)
    + len(prediction.router.routes)
    + len(shap.router.routes)
    + len(clients.router.routes)
)

print("\n" + "=" * 70)
print(f"  Total : {total_routes} endpoints sur 8 prevus")
print("=" * 70)

if total_routes == 8:
    print("  TOUS LES ENDPOINTS SONT EN PLACE")
else:
    print(f"  ⚠ {8 - total_routes} endpoint(s) manquant(s)")