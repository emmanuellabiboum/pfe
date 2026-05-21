## 1) Diagramme de cas d'utilisation global (détaillé)

```mermaid
usecaseDiagram
    %% Acteurs (figurines)
    actor SuperAdmin as Super
    actor AdminVille as AdminVille
    actor ChefAgence as Chef
    actor AgentCommercial as AgentCom
    actor AgentMarketing as AgentMark

    %% Cas d'utilisation
    (Se connecter / OTP) as UC_Auth
    (Se déconnecter) as UC_Logout
    (Gérer comptes utilisateurs) as UC_GererCompte
    (Consulter fiche client) as UC_ConsulterClient
    (Consulter historique recommandations) as UC_HistoriqueReco
    (Lancer analyse / import) as UC_LancerAnalyse
    (Générer données mock) as UC_GenererMock
    (Créer recommandation commerciale) as UC_CreerRecoCom
    (Créer recommandation marketing) as UC_CreerRecoMark
    (Valider / Rejeter recommandation) as UC_ValiderReco
    (Compléter recommandation) as UC_CompleterReco
    (Consulter notifications) as UC_ConsulterNotif
    (Accéder tableau de bord KPIs) as UC_Dashboard
    (Accéder tableau de bord multi-agences) as UC_DashboardMulti

    %% Liens acteur → use case
    AgentCom --> UC_Auth
    AgentCom --> UC_Logout
    AgentCom --> UC_ConsulterClient
    AgentCom --> UC_HistoriqueReco
    AgentCom --> UC_CreerRecoCom
    AgentCom --> UC_CompleterReco
    AgentCom --> UC_ConsulterNotif

    AgentMark --> UC_Auth
    AgentMark --> UC_Logout
    AgentMark --> UC_ConsulterClient
    AgentMark --> UC_HistoriqueReco
    AgentMark --> UC_CreerRecoMark
    AgentMark --> UC_CompleterReco
    AgentMark --> UC_ConsulterNotif

    Chef --> UC_Auth
    Chef --> UC_Logout
    Chef --> UC_ConsulterClient
    Chef --> UC_HistoriqueReco
    Chef --> UC_LancerAnalyse
    Chef --> UC_GenererMock
    Chef --> UC_ValiderReco
    Chef --> UC_ConsulterNotif
    Chef --> UC_Dashboard

    AdminVille --> UC_Auth
    AdminVille --> UC_Logout
    AdminVille --> UC_GererCompte
    AdminVille --> UC_DashboardMulti

    Super --> UC_Auth
    Super --> UC_Logout
    Super --> UC_GererCompte
    Super --> UC_DashboardMulti

    %% Héritage / spécialisation des rôles (visualisation)
    Super --|> AdminVille
    AdminVille --|> Chef

    %% Intégrations techniques (références)
    UC_LancerAnalyse ..> FastAPI : "POST /api/predict/batch"
    UC_ConsulterClient ..> FastAPI : "GET /api/predict/{id}"
    UC_ExporterPDF ..> WKHTML : "wkhtmltopdf"
    %% Note : le diagramme utilise la notation usecaseDiagram pour afficher
    %% les figurines d'acteurs et la hiérarchie simple des rôles.
```

---

## 2) Diagramme Entité-Association (E-A) — Plus complet

```mermaid
erDiagram
    USER {
        int id PK
        string username
        string email
        string role
        string statut
        int agence_id FK
        int ville_id FK
        int tentatives_connexion
    }

    VILLE {
        int id PK
        string nom
        string region
    }

    AGENCE {
        int id PK
        string nom
        string adresse
        string telephone
        int ville_id FK
    }

    DATASET {
        int id PK
        string methode
        int agence_id FK
        int nb_clients
        datetime created_at
        string fichier
    }

    CLIENT_CHURN {
        int id PK
        string client_id
        float score_churn
        boolean churn_predit
        float facture_moyenne_mensuelle
        int dataset_id FK
        int agence_id FK
    }

    SHAP_VALEUR {
        int id PK
        int client_id FK
        string feature
        float shap_value
    }

    RECOMMANDATION {
        int id PK
        int client_id FK
        int createur_id FK
        string type_recommandation
        string statut
        float clv_estimee
        datetime created_at
        datetime updated_at
    }

    REJET_RECOMMANDATION {
        int id PK
        int recommandation_id FK
        int rejeteur_id FK
        text motif
        datetime created_at
    }

    ANALYSE_SESSION {
        int id PK
        int agence_id FK
        int nb_clients
        float seuil_optimal
        float auc_roc
        datetime date_analyse
    }

    NOTIFICATION {
        int id PK
        int destinataire_id FK
        string type
        text titre
        text contenu
        boolean is_read
        datetime created_at
    }

    OTP_CODE {
        int id PK
        int user_id FK
        string code
        datetime expire_at
        datetime created_at
    }

    %% Relations (cardinalités + sens)
    VILLE ||--o{ AGENCE : "1..n"
    AGENCE ||--o{ DATASET : "1..n"
    DATASET ||--o{ CLIENT_CHURN : "1..n"

    CLIENT_CHURN ||--o{ SHAP_VALEUR : "1..n"
    CLIENT_CHURN ||--o{ RECOMMANDATION : "0..n"

    USER ||--o{ RECOMMANDATION : "1..n (createur)"
    USER ||--o{ REJET_RECOMMANDATION : "0..n (rejeteur)"
    RECOMMANDATION ||--o{ REJET_RECOMMANDATION : "0..n"

    AGENCE ||--o{ ANALYSE_SESSION : "0..n"
    USER ||--o{ NOTIFICATION : "0..n"
    CLIENT_CHURN }|..|{ NOTIFICATION : "0..n (lié_à)"

    USER ||--o{ OTP_CODE : "0..n"

    %% Remarque : ce modèle reflète les entités et champs principaux observés dans le code.
```

---

## 3) Diagrammes de classes par module

### 3.1 Module `accounts`

```mermaid
classDiagram
    class User {
        +id
        +username
        +role
        +statut
        +telephone
        +tentatives_connexion
        +est_bloque
        +save()
        +get_validation_scope()
        +clean()
    }
    class OTPCode {
        +id
        +user_id
        +code
        +expire_at
        +created_at
    }
    class LoginActivity {
        +id
        +user_id
        +timestamp
    }
    class AdminVille {
        +id
        +user_id
        +ville_id
        +date_nomination
        +actif
    }
    User "1" o-- "0..*" OTPCode
    User "1" o-- "0..*" LoginActivity
    User "1" o-- "0..1" AdminVille
    User "0..1" --> "0..1" Agence
    User "0..1" --> "0..1" Ville
    AdminVille "0..1" --> "0..1" Ville
```

### 3.2 Module `learning`

```mermaid
classDiagram
    class Dataset {
        +id
        +nom
        +methode
        +fichier
        +nb_clients
        +date_chargement
        +charge_par_id
    }
    class ClientChurn {
        +id
        +client_id
        +nom
        +score_churn
        +churn_predit
        +agence_id
        +dataset_id
        +date_prediction
        +facture_moyenne_mensuelle
    }
    class EvenementCDR {
        +id
        +client_id
        +date_heure
        +type_evenement
        +duree_appel_sec
        +sms_compte
        +data_mb
    }
    class InteractionDigital {
        +id
        +client_id
        +date_heure
        +type_interaction
        +duree_session_sec
        +pages_visitees
    }
    class DonneeGeospatiale {
        +id
        +client_id
        +latitude
        +longitude
        +zone_couverture
    }
    class Reclamation {
        +id
        +client_id
        +type_reclamation
        +statut
        +date_creation
    }
    class CampagneMarketing {
        +id
        +nom
        +type_campagne
        +date_envoi
    }
    class InteractionCampagne {
        +id
        +campagne_id
        +client_id
        +ouvert
        +clique
        +converti
    }
    class ShapValeur {
        +id
        +client_id
        +feature
        +valeur
        +importance
    }
    Dataset "1" o-- "0..*" ClientChurn
    Dataset "1" --> "1" Agence
    Dataset "0..1" --> "0..1" User
    ClientChurn "1" o-- "0..*" EvenementCDR
    ClientChurn "1" o-- "0..*" InteractionDigital
    ClientChurn "1" o-- "0..1" DonneeGeospatiale
    ClientChurn "1" o-- "0..*" Reclamation
    ClientChurn "1" o-- "0..*" InteractionCampagne
    CampagneMarketing "1" o-- "0..*" InteractionCampagne
    ClientChurn "1" o-- "0..*" ShapValeur
```

### 3.3 Module `dashboard`

```mermaid
classDiagram
    class Message {
        +id
        +destinataire_id
        +expediteur_id
        +client_id
        +sujet
        +contenu
        +lu
        +date_envoi
    }
    class ModelPerformance {
        +accuracy
        +precision
        +recall
        +roc_auc
        +created_at
    }
    class SystemMetrics {
        +total_predictions
        +total_pdfs_generated
        +total_recommendations
        +errors_count
        +updated_at
    }
    class Recommandation {
        +id
        +client_id
        +type_recommandation
        +contenu
        +statut
        +clv_estimee
        +cree_par_id
        +assignee_a_id
        +modifiee_par_id
        +date_creation
    }
    class Notification {
        +id
        +destinataire_id
        +type_notif
        +titre
        +contenu
        +lien
        +client_id
        +recommandation_id
        +lu
        +archive
        +supprimee
        +date_creation
    }
    class RejetRecommandation {
        +id
        +recommandation_id
        +demandeur_id
        +explication
        +statut
        +valide_par_id
        +date_demande
        +date_validation
    }
    class AnalyseSession {
        +id
        +agence_id
        +lancee_par_id
        +date_analyse
        +nb_clients_total
        +nb_clients_churn
        +nb_clients_non_churn
        +score_churn_moyen
        +nb_recommandations_generees
        +seuil_optimal
        +auc_roc
        +f1_score
        +recall
        +precision
        +methode
    }
    User "1" o-- "0..*" Message
    ClientChurn "0..1" o-- "0..*" Message
    User "1" o-- "0..*" Recommandation
    ClientChurn "1" o-- "0..*" Recommandation
    Recommandation "1" o-- "0..*" RejetRecommandation
    User "1" o-- "0..*" Notification
    Recommandation "0..1" o-- "0..*" Notification
    ClientChurn "0..1" o-- "0..*" Notification
    Agence "1" o-- "0..*" AnalyseSession
    User "1" o-- "0..*" AnalyseSession
```

---

## 4) Diagrammes de séquence — Flux clés

### 4.1 Flux : Authentification à double facteur

```mermaid
sequenceDiagram
    participant User
    participant Django
    participant DB
    participant Mail

    User->>Django: POST /accounts/login (username,password)
    Django->>DB: load User + verify password + vérifier blocage
    Django->>DB: OTPCode.objects.filter(user).delete()
    Django->>DB: OTPCode.objects.create(user, code, expire_at)
    Django->>Mail: envoyer email OTP
    Django-->>User: redirect /accounts/verify-otp
    User->>Django: POST /accounts/verify-otp (code)
    Django->>DB: lookup OTPCode(user, code)
    DB-->>Django: OTP valide / expire_at check
    Django->>DB: delete OTPCode
    Django-->>User: login success
```

### 4.2 Flux : Lancer analyse (FastAPI disponible — batch)

```mermaid
sequenceDiagram
    participant User
    participant Django
    participant FastAPI
    participant DB

    User->>Django: POST /lancer_analyse (mock ou csv)
    Django->>Django: préparer clients et payload
    Django->>FastAPI: POST /api/predict/batch
    FastAPI-->>Django: 200 + predictions
    Django->>DB: update ClientChurn scores
    Django->>DB: create AnalyseSession
    Django->>DB: create Notification (alerte_churn)
    Django-->>User: rendre dashboard / JSON résultats
```

### 4.3 Flux : Lancer analyse (FastAPI indisponible — comportement réel)

```mermaid
sequenceDiagram
    participant User
    participant Django
    participant FastAPI

    User->>Django: POST /lancer_analyse
    Django->>FastAPI: GET /health
    FastAPI--xDjango: timeout / non reachable
    Django-->>User: erreur 503 + message
    Note right of Django: le code ne bascule pas sur un fallback local de prédiction
```

### 4.4 Flux : Génération de données mock

```mermaid
sequenceDiagram
    participant User
    participant Django
    participant Core
    participant DB

    User->>Django: POST /dashboard/generer_mock
    Django->>Core: generer_mock_data(agence_id, user_id, nb_clients)
    Core-->>Django: clients mock créés
    Django->>DB: update ClientChurn scores (règles heuristiques)
    Django-->>User: redirect /dashboard/clients
```

### 4.5 Flux : Workflow de recommandation (création → validation → rejet)

```mermaid
sequenceDiagram
    participant Agent
    participant Django
    participant DB
    participant Chef

    Agent->>Django: POST create recommendation
    Django->>DB: create Recommandation(statut='active' ou 'en_attente_validation')
    Django->>DB: create Notification(type=validation_requise)
    Chef->>Django: GET /valider_creation_recommandation
    Django->>DB: update Recommandation.statut
    alt rejected
        Django->>DB: create RejetRecommandation
        Django->>DB: update Notification(type=validation_refusee)
        Django-->>Agent: notify rejection
    else validated
        Django->>DB: update Notification(type=validation_acceptee)
        Django-->>Agent: notify acceptance
    end
```

### 4.6 Flux : Export PDF depuis la fiche client via wkhtmltopdf

```mermaid
sequenceDiagram
    participant User
    participant Django
    participant DB
    participant WKHTMLTOPDF

    User->>Django: GET /clients/<client_id>/pdf/
    Django->>DB: charger ClientChurn et recommandations associées
    Django->>Django: render_to_string("dashboard/fiche_client_pdf.html")
    Django->>WKHTMLTOPDF: pdfkit.from_string(html)
    WKHTMLTOPDF-->>Django: PDF bytes
    Django-->>User: PDF téléchargement
    alt erreur wkhtmltopdf
        Django-->>User: message d'erreur
    end
```

---

## 5) Arborescence UML — Structure des modules

```mermaid
graph TD
    A["Projet CHURN"] --> B[" accounts"] 
    A --> C[" learning"]
    A --> D["dashboard"]
    A --> E["core"]
    A --> F["config"]
    
    B --> B1["User modèle custom"]
    B --> B2["OTPCode"]
    B --> B3["AdminVille"]
    B --> B4["LoginActivity"]
    B --> B5["Views login verify-otp reset"]
    B --> B6["Forms AuthForm ResetForm"]
    B --> B7["Services email OTP"]
    
    C --> C1["Dataset"]
    C --> C2["ClientChurn"]
    C --> C3["ShapValeur"]
    C --> C4["EvenementCDR"]
    C --> C5["InteractionDigital"]
    C --> C6["DonneeGeospatiale"]
    C --> C7["Pipeline ML Data Quality"]
    
    D --> D1["Recommandation"]
    D --> D2["RejetRecommandation"]
    D --> D3["Notification"]
    D --> D4["AnalyseSession"]
    D --> D5["Message"]
    D --> D6["Tasks Celery async"]
    D --> D7["Views dashboard validation"]
    
    E --> E1["ml_service prédictions"]
    E --> E2["ml_pipeline prétraitement"]
    E --> E3["fastapi_service intégration"]
    E --> E4["data_quality nettoyage"]
    E --> E5["model_config hyperparamètres"]
    E --> E6["notifications_engine"]
    E --> E7["otp_service"]
    E --> E8["mock_data génération test"]
    
    F --> F1["settings.py Django config"]
    F --> F2["urls.py routing"]
    F --> F3["wsgi.py"]
    F --> F4["asgi.py"]
```

---

## 6) Arborescence URL — Structure du routage

```mermaid
graph TD
    Root["/ ROOT"] --> Auth[" /accounts/"]
    Root --> Dashboard["/dashboard/"]
    Root --> Admin[" /admin/"]
    Root --> API[" /api/"]
    
    Auth --> A1["login GET/POST"]
    Auth --> A2["verify-otp GET/POST"]
    Auth --> A3["logout GET"]
    Auth --> A4["reset-password GET/POST"]
    Auth --> A5["gestion-comptes GET/POST"]
    Auth --> A6["create-user GET/POST"]
    Auth --> A7["edit-user/:id GET/POST"]
    Auth --> A8["delete-user/:id POST"]
    
    Dashboard --> D1["clients/ GET"]
    Dashboard --> D2["clients/:id/ GET"]
    Dashboard --> D3["clients/:id/pdf/ GET"]
    Dashboard --> D4["recommandations/ GET/POST"]
    Dashboard --> D5["recommandations/:id/valider/ POST"]
    Dashboard --> D6["recommandations/:id/rejeter/ POST"]
    Dashboard --> D7["notifications/ GET"]
    Dashboard --> D8["notifications/:id/marquer-lu/ POST"]
    Dashboard --> D9["analyse/ GET/POST"]
    Dashboard --> D10["generer-mock/ POST"]
    Dashboard --> D11["statistiques/ GET"]
    
    Admin --> Adm1["Django Admin Interface"]
    
    API --> AP1["health GET"]
    API --> AP2["model-info GET"]
    AP2 --> AP2a["FastAPI: /api/model/info"]
    AP1 --> AP1a["FastAPI: /health"]
```



