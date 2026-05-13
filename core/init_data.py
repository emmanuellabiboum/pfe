"""
Script d'initialisation des données Tunisie Telecom
Crée les villes et agences (Kairouan prioritaire pour le stage)
"""
from core.models import Ville, Agence


def init_villes_tt():
    """Créer les villes couvertes par TT - Kairouan prioritaire"""
    villes_data = [
        # Kairouan et sa région (prioritaire pour le stage)
        {"nom": "Kairouan", "region": "Kairouan", "prioritaire": True},
        {"nom": "Sousse", "region": "Sousse", "prioritaire": False},
        {"nom": "Monastir", "region": "Monastir", "prioritaire": False},
        {"nom": "Mahdia", "region": "Mahdia", "prioritaire": False},
        {"nom": "Sfax", "region": "Sfax", "prioritaire": False},
        {"nom": "Tunis", "region": "Tunis", "prioritaire": False},
        {"nom": "Ariana", "region": "Tunis", "prioritaire": False},
        {"nom": "Ben Arous", "region": "Tunis", "prioritaire": False},
        {"nom": "Manouba", "region": "Tunis", "prioritaire": False},
        {"nom": "Nabeul", "region": "Nabeul", "prioritaire": False},
        {"nom": "Bizerte", "region": "Bizerte", "prioritaire": False},
        {"nom": "Béja", "region": "Béja", "prioritaire": False},
        {"nom": "Jendouba", "region": "Jendouba", "prioritaire": False},
        {"nom": "Le Kef", "region": "Le Kef", "prioritaire": False},
        {"nom": "Siliana", "region": "Siliana", "prioritaire": False},
        {"nom": "Sidi Bouzid", "region": "Sidi Bouzid", "prioritaire": False},
        {"nom": "Gafsa", "region": "Gafsa", "prioritaire": False},
        {"nom": "Tozeur", "region": "Tozeur", "prioritaire": False},
        {"nom": "Kébili", "region": "Kébili", "prioritaire": False},
        {"nom": "Gabès", "region": "Gabès", "prioritaire": False},
        {"nom": "Médenine", "region": "Médenine", "prioritaire": False},
        {"nom": "Tataouine", "region": "Tataouine", "prioritaire": False},
    ]

    created_count = 0
    for ville_data in villes_data:
        ville, created = Ville.objects.get_or_create(
            nom=ville_data["nom"],
            defaults={
                "region": ville_data["region"],
                "prioritaire": ville_data["prioritaire"],
                "active": True
            }
        )
        if created:
            created_count += 1
            print(f"✅ Ville créée: {ville}")
        else:
            print(f"ℹ️ Ville existe déjà: {ville}")

    return created_count


def init_agences_tt():
    """Créer les agences TT - focus sur Kairouan"""
    agences_data = [
        # Kairouan - Agences principales (prioritaire pour le stage)
        ("Kairouan", [
            {"nom": "Agence Principale Kairouan", "code": "TT_KAI_001", "adresse": "Avenue Bourguiba, Kairouan", "telephone": "77 123 456"},
            {"nom": "Agence El Oued", "code": "TT_KAI_002", "adresse": "Route El Oued, Kairouan", "telephone": "77 234 567"},
            {"nom": "Agence Sbikha", "code": "TT_KAI_003", "adresse": "Centre Sbikha, Kairouan", "telephone": "77 345 678"},
            {"nom": "Agence Haffouz", "code": "TT_KAI_004", "adresse": "Centre Haffouz, Kairouan", "telephone": "77 456 789"},
            {"nom": "Agence Bou Hajla", "code": "TT_KAI_005", "adresse": "Centre Bou Hajla, Kairouan", "telephone": "77 567 890"},
            {"nom": "Agence Nasrallah", "code": "TT_KAI_006", "adresse": "Centre Nasrallah, Kairouan", "telephone": "77 678 901"},
            {"nom": "Agence Chrarda", "code": "TT_KAI_007", "adresse": "Centre Chrarda, Kairouan", "telephone": "77 789 012"},
            {"nom": "Agence Messaadine", "code": "TT_KAI_008", "adresse": "Zone industrielle Messaadine, Kairouan", "telephone": "77 890 123"},
        ]),
        # Sousse
        ("Sousse", [
            {"nom": "Agence Principale Sousse", "code": "TT_SOU_001", "adresse": "Avenue Habib Bourguiba, Sousse", "telephone": "73 123 456"},
            {"nom": "Agence Sousse Jaune", "code": "TT_SOU_002", "adresse": "Boulevard du Leader Yasser Arafat, Sousse", "telephone": "73 234 567"},
            {"nom": "Agence Sahloul", "code": "TT_SOU_003", "adresse": "Route de Sahloul, Sousse", "telephone": "73 345 678"},
            {"nom": "Agence Kantaoui", "code": "TT_SOU_004", "adresse": "Port El Kantaoui, Sousse", "telephone": "73 456 789"},
        ]),
        # Monastir
        ("Monastir", [
            {"nom": "Agence Principale Monastir", "code": "TT_MON_001", "adresse": "Avenue Habib Bourguiba, Monastir", "telephone": "73 567 890"},
            {"nom": "Agence Skanes", "code": "TT_MON_002", "adresse": "Zone Skanes, Monastir", "telephone": "73 678 901"},
        ]),
        # Tunis
        ("Tunis", [
            {"nom": "Agence Principale Tunis", "code": "TT_TUN_001", "adresse": "Avenue Habib Bourguiba, Tunis", "telephone": "71 123 456"},
            {"nom": "Agence La Marsa", "code": "TT_TUN_002", "adresse": "La Marsa, Tunis", "telephone": "71 234 567"},
            {"nom": "Agence Carthage", "code": "TT_TUN_003", "adresse": "Carthage, Tunis", "telephone": "71 345 678"},
        ]),
        # Sfax
        ("Sfax", [
            {"nom": "Agence Principale Sfax", "code": "TT_SFA_001", "adresse": "Avenue Hédi Chaker, Sfax", "telephone": "74 123 456"},
            {"nom": "Agence Sfax Sud", "code": "TT_SFA_002", "adresse": "Route Gabès, Sfax", "telephone": "74 234 567"},
        ]),
        # Autres villes
        ("Sidi Bouzid", [
            {"nom": "Agence Principale Sidi Bouzid", "code": "TT_SIB_001", "adresse": "Avenue Bourguiba, Sidi Bouzid", "telephone": "76 123 456"},
        ]),
        ("Gafsa", [
            {"nom": "Agence Principale Gafsa", "code": "TT_GAF_001", "adresse": "Avenue Bourguiba, Gafsa", "telephone": "76 234 567"},
        ]),
    ]

    created_count = 0
    for ville_nom, agences in agences_data:
        try:
            ville = Ville.objects.get(nom=ville_nom)
            for agence_data in agences:
                agence, created = Agence.objects.get_or_create(
                    code=agence_data["code"],
                    defaults={
                        "nom": agence_data["nom"],
                        "ville": ville,
                        "adresse": agence_data["adresse"],
                        "telephone": agence_data["telephone"],
                        "active": True
                    }
                )
                if created:
                    created_count += 1
                    print(f"✅ Agence créée: {agence}")
                else:
                    print(f"ℹ️ Agence existe déjà: {agence}")
        except Ville.DoesNotExist:
            print(f"❌ Ville non trouvée: {ville_nom}")

    return created_count


def run():
    """Exécuter l'initialisation complète"""
    print("\n" + "="*60)
    print("INITIALISATION DES DONNÉES TUNISIE TELECOM")
    print("="*60)
    
    print("\n1. Création des villes...")
    villes_count = init_villes_tt()
    
    print("\n2. Création des agences...")
    agences_count = init_agences_tt()
    
    print("\n" + "="*60)
    print(f"✅ Initialisation terminée:")
    print(f"   - {villes_count} villes créées")
    print(f"   - {agences_count} agences créées")
    print(f"   - Kairouan est marquée comme prioritaire")
    print("="*60 + "\n")


if __name__ == "__main__":
    import os
    import django
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    django.setup()
    run()
