# Guide de Modélisation UML — Projet CHURN (Tunisie Telecom)

Ce document constitue la référence officielle pour la modélisation du système. Il respecte les normes académiques UML et couvre l'intégralité des 14 Besoins Fonctionnels (BF) validés.

---

## 1. Principes de Conception et Conventions

- **Standardisation :** Notation UML 2.5 rigoureuse.
- **Traçabilité :** Chaque cas d'utilisation est lié à son identifiant de besoin (BF-XX).
- **Acteurs :** Les actions système (ex: calculs) ne sont pas des Use Cases. Seuls les objectifs acteurs sont représentés.

---

## 2. Chapitre 2 : Analyse et Conception

### 2.1 Liste des Besoins Fonctionnels (Référence)
- **M1 (Sécurité) :** BF-01 (Inscription), BF-02 (2FA), BF-03 (Reset MDP).
- **M2 (Données) :** BF-04 (Import), BF-05 (Mock), BF-06 (Analyse Prédictive IA).
- **M3 (Pilotage) :** BF-07 (Dashboards G/R/A), BF-08 (Liste Clients), BF-09 (Fiche Détail/SHAP), BF-10 (Export PDF), BF-11 (Historique Sessions).
- **M4 (Actions) :** BF-12 (Tâches Agents), BF-13 (Validation Chef), BF-14 (Alertes).

### 2.2 Diagramme de Cas d'Utilisation Global (Conventionnel)

```plantuml
@startuml
left to right direction
skinparam packageStyle rectangle
skinparam shadowing false

actor "Super Admin" as Super
actor "Admin Ville" as AdminVille
actor "Chef d'Agence" as Chef
actor "Agent (Com/Mark)" as Agent
actor "SendGrid (Email)" as SendGrid <<Service>>

rectangle "Plateforme Churn Tunisie Telecom" {
  
  package "Module 1 : Sécurité" {
    (BF-01 : S'inscrire / Valider compte) as BF01
    (BF-02 : S'authentifier via OTP) as BF02
    (BF-03 : Réinitialiser le mot de passe) as BF03
  }

  package "Module 2 : Données & Inférence" {
    (BF-04 : Importer des données clients) as BF04
    (BF-05 : Générer des données simulées) as BF05
    (BF-06 : Lancer l'Analyse Prédictive) as BF06
  }

  package "Module 3 : Visualisation" {
    (BF-07 : Consulter les Dashboards) as BF07
    (BF-08 : Consulter la liste des clients) as BF08
    (BF-09 : Consulter la fiche détaillée\net l'explicabilité SHAP) as BF09
    (BF-10 : Exporter la fiche en PDF) as BF10
    (BF-11 : Consulter l'historique des sessions) as BF11
  }

  package "Module 4 : Recommandations" {
    (BF-12 : Gérer les tâches par spécialité) as BF12
    (BF-13 : Valider les actions de rétention) as BF13
    (BF-14 : Recevoir des alertes) as BF14
  }
}

' Relations Super Admin
Super --> BF01
Super --> BF07

' Relations Admin Ville
AdminVille --> BF01
AdminVille --> BF07

' Relations Chef d'Agence
Chef --> BF04
Chef --> BF05
Chef --> BF06
Chef --> BF07
Chef --> BF11
Chef --> BF13

' Relations Agents
Agent --> BF08
Agent --> BF09
Agent --> BF12

' Accès partagés et dépendances
Chef --> BF08
Chef --> BF09
Chef --> BF14
Agent --> BF14
BF09 <.. BF10 : <<extend>>

' Services techniques
BF01 -- SendGrid
BF02 -- SendGrid
BF03 -- SendGrid
BF14 -- SendGrid

' Hiérarchie UML
Super --|> AdminVille
AdminVille --|> Chef
Chef --|> Agent
@enduml
```

### 2.3 Diagramme de Classes : Modèle de Données (Learning)
```plantuml
@startuml
skinparam style strictuml
skinparam shadowing false
skinparam roundcorner 10
skinparam classAttributeIconSize 0

enum MethodeChargement {
    CSV
    MOCK
}

class Dataset {
    - id : Integer
    - nom : String
    - methode : MethodeChargement
    - date_chargement : DateTime
    + valider_structure() : Boolean
}

class ClientChurn {
    - id : Integer
    - client_id : String
    - score_churn : Float
    - churn_predit : Boolean
    - facture_mensuelle : Float
    + calculer_churn() : Float
    + to_feature_dict() : Map
}

class ShapValeur {
    - feature : String
    - valeur : Float
    - importance : Float
}

Dataset "1" *-- "0..*" ClientChurn : contient >
ClientChurn "1" *-- "0..*" ShapValeur : explique par >
@enduml
```

### 2.4 Diagramme de Classes : Organisation & Sécurité (Core & Accounts)
```plantuml
@startuml
skinparam style strictuml
skinparam shadowing false
skinparam roundcorner 10
skinparam classAttributeIconSize 0

enum UserRole {
    SUPER_ADMIN
    ADMIN_VILLE
    CHEF_AGENCE
    AGENT_MARKETING
    AGENT_COMMERCIAL
}

enum UserStatut {
    EN_ATTENTE
    ACTIF
    SUSPENDU
}

class Ville {
    - id : Integer
    - nom : String
    - code : String
    - prioritaire : Boolean
}

class Agence {
    - id : Integer
    - nom : String
    - code : String
    - active : Boolean
}

class User {
    - id : Integer
    - username : String
    - role : UserRole
    - statut : UserStatut
    + get_validation_scope() : String
}

class AdminVille {
    - date_nomination : DateTime
    - actif : Boolean
}

Ville "1" *-- "1..*" Agence : localisée dans <
Agence "1" -- "1..3" User : emploie >
Ville "1" -- "1..*" User : gérée par (Admin) >
User "1" --o "1" AdminVille : étend >
AdminVille "0..*" -- "1" Ville : administre >
@enduml
```

### 2.5 Diagramme de Classes : Pilotage & Actions (Dashboard)
```plantuml
@startuml
skinparam style strictuml
skinparam shadowing false
skinparam roundcorner 10
skinparam classAttributeIconSize 0

enum RecType {
    MARKETING
    COMMERCIAL
    TECHNIQUE
}

enum RecStatut {
    ACTIVE
    EN_COURS
    COMPLETEE_AGENT
    COMPLETEE
    REJETEE
    EXPIREE
}

enum Urgence {
    CRITIQUE
    ELEVE
    MOYEN
    FAIBLE
    NONE
}

class AnalyseSession {
    - id : Integer
    - date_analyse : DateTime
    - nb_clients_total : Integer
    - nb_clients_churn : Integer
    - score_churn_moyen : Float
    - auc_roc : Float
    + get_differences_with_previous() : Map
}

class Recommandation {
    - type : RecType
    - contenu : Text
    - echeance : Date
    - statut : RecStatut
    - clv_estimee : Float
    + temps_restant_jours() : Integer
    + urgence() : Urgence
}

class Notification {
    - id : Integer
    - type_notif : String
    - titre : String
    - lu : Boolean
    - date_creation : DateTime
}

class RejetRecommandation {
    - explication : Text
    - statut : Enum {ATTENTE, ACCEPTE, REFUSE}
    - date_demande : DateTime
}

AnalyseSession "0..*" -- "1" Agence : concerne >
AnalyseSession "0..*" -- "1" User : lancée par >
Recommandation "0..*" -- "1" ClientChurn : pour >
Recommandation "0..*" -- "0..1" User : assignée à >
Notification "0..*" -- "1" User : destinée à >
Notification "0..*" -- "0..1" Recommandation : liée à >
RejetRecommandation "0..*" -- "1" Recommandation : rejette >
@enduml
```

---

## Chapitre 6 : Diagrammes de Séquence

Nous utilisons les diagrammes de séquence pour modéliser les interactions dynamiques entre les composants de notre architecture. Ces schémas illustrent comment les différents services (Serveur d'Application, Moteur d'Inférence ML, PostgreSQL, SendGrid) collaborent pour réaliser les processus métier critiques.

### 6.1 Flux 1 : Authentification à double facteur (2FA)

Ce processus sécurise l'accès à la plateforme en générant un code OTP via SendGrid après la validation des identifiants primaires.

```mermaid
sequenceDiagram
    autonumber
    actor User as Utilisateur
    participant App as Serveur d'Application (Django)
    participant DB as PostgreSQL
    participant Email as API SendGrid

    User->>App: Soumettre identifiants (Login/Pass)
    activate App
    App->>DB: Vérifier identifiants
    DB-->>App: Résultat vérification

    alt Identifiants invalides
        App-->>User: Message d'erreur (Accès refusé)
    else Identifiants corrects
        App->>App: Générer code OTP
        App->>Email: Envoyer OTP (Email)
        activate Email
        Email-->>User: Réception du code OTP
        deactivate Email
        App-->>User: Afficher formulaire de saisie OTP
        
        User->>App: Saisir code OTP
        App->>DB: Valider code (vs expiration)
        DB-->>App: Résultat validation

        alt OTP invalide ou expiré
            App-->>User: Message d'erreur (Session invalidée)
        else OTP valide
            App->>DB: Créer session & Enregistrer activité
            DB-->>App: OK
            App-->>User: Accès au Dashboard (Connexion réussie)
        end
    end
    deactivate App
```

### 6.2 Flux 2 : Analyse de portefeuille avec FastAPI

Ce flux constitue le cœur technologique, intégrant une communication asynchrone avec le moteur d'inférence ML.

```mermaid
sequenceDiagram
    autonumber
    actor Chef as Chef d'Agence
    participant App as Serveur d'Application (Django)
    participant ML as Moteur d'Inférence (FastAPI)
    participant DB as PostgreSQL

    Chef->>App: Lancer Analyse de Portefeuille
    activate App
    App->>DB: Préparer données clients (Batch)
    DB-->>App: Liste des clients

    opt Vérification de santé (Health Check)
        App->>ML: GET /health
        ML-->>App: 200 OK (Service opérationnel)
    end

    App->>ML: POST /api/predict/batch (Données JSON/CSV)
    activate ML
    note over ML: Chargement Random Forest + Calcul SHAP
    
    alt Calcul réussi
        ML-->>App: Résultats (Scores + SHAP JSON)
        deactivate ML
        App->>DB: Persister résultats & Créer AnalyseSession
        App-->>Chef: Affichage des KPIs & Résultats détaillés
    else Erreur Micro-service
        ML-->>App: Erreur 500 / Timeout
        App-->>Chef: Alerte : Service indisponible (Message d'erreur)
    end
    deactivate App
```

### 6.3 Flux 3 : Workflow de recommandation et validation

Modélisation du cycle de vie des actions de rétention reflétant l'organisation hiérarchique de Tunisie Telecom.

```mermaid
sequenceDiagram
    autonumber
    actor Agent as Agent (Com/Mark)
    participant App as Serveur d'Application
    participant DB as PostgreSQL
    actor Chef as Chef d'Agence

    Agent->>App: Créer recommandation (Client X)
    activate App
    App->>DB: Enregistrer (Statut: Validation Requise)
    DB-->>App: OK
    App->>App: Générer notification système
    App-->>Chef: Alerte : Nouvelle recommandation à valider
    deactivate App

    Chef->>App: Consulter détails recommandation
    activate App
    App->>DB: Récupérer infos client & contenu action
    DB-->>App: Données recommandation
    App-->>Chef: Affichage interface de décision

    alt Validation (Activation)
        Chef->>App: Activer l'action de rétention
        App->>DB: Update Statut -> "Active"
        App-->>Agent: Notification : Action prête à être exécutée
    else Rejet
        Chef->>App: Rejeter la recommandation
        App->>DB: Update Statut -> "Rejetée"
        App-->>Agent: Information : Recommandation refusée
    end
    deactivate App
```

### 6.4 Flux 4 : Exportation de rapports PDF

Génération de documents à la volée en transformant le rendu HTML (avec SHAP) en PDF via wkhtmltopdf.

```mermaid
sequenceDiagram
    autonumber
    actor User as Utilisateur
    participant App as Contrôleur Django
    participant DB as PostgreSQL
    participant PDF as Moteur pdfkit / wkhtmltopdf

    User->>App: Demander export PDF (Fiche Client)
    activate App
    App->>DB: Récupérer profil + SHAP explications
    DB-->>App: Données client formatées
    App->>App: Injecter données dans template HTML spécialisé
    
    App->>PDF: Transmettre flux HTML
    activate PDF
    note right of PDF: Transformation HTML -> PDF (A4)
    PDF-->>App: Retourner flux binaire PDF
    deactivate PDF

    App-->>User: Retourner fichier (Flux binaire au navigateur)
    deactivate App
    note over User, App: Téléchargement instantané sans stockage disque
```
