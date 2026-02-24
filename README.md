# MLOps Rakuten

Classification de types de produits pour Rakuten France

> Projet MLOps de bout en bout : ingestion de données, entraînement de modèle, exposition via API sécurisée, monitoring et versioning.

---

## Table des matières

- [Architecture globale](#architecture-globale)
- [Project Organization](#project-organization)
- [Installation](#installation)
- [Structure du pipeline de données](#structure-du-pipeline-de-données)
- [Sécurité et Gateway](#sécurité-et-gateway)
- [Suivi d'expériences et versioning](#suivi-dexpériences-et-versioning)
- [Containerisation via Docker](#containerisation-via-docker)
- [Lancer l'application avec Docker](#lancer-lapplication-avec-docker)
- [Monitoring](#monitoring)
- [Tests](#tests)
- [Commandes Makefile](#commandes-makefile)

---

## Architecture globale

Le projet suit une architecture microservices conteneurisée. Voici le flux de données et les responsabilités de chaque composant :

```
┌─────────────────────────────────────────────────────────────────┐
│                         CLIENT (curl / Swagger)                 │
└────────────────────────────┬────────────────────────────────────┘
                             │ HTTPS (TLS auto-signé)
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                        NGINX (Reverse Proxy)                    │
│  • Terminaison TLS                                              │
│  • Routage vers le service API Gateway                          │
└────────────────────────────┬────────────────────────────────────┘
                             │ HTTP interne
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                       API GATEWAY (FastAPI)                     │
│  • Authentification OAuth2 / Bearer Token                       │
│  • Routage vers les services internes                           │
└──────┬──────────────────┬──────────────────────┬───────────────┘
       │                  │                      │
       ▼                  ▼                      ▼
┌────────────┐   ┌────────────────┐   ┌──────────────────┐
│  Ingest    │   │  Train Service │   │  Predict Service │
│  Service   │   │                │   │                  │
│ (FastAPI)  │   │  • Pipeline    │   │  • Chargement    │
│            │   │    complète    │   │    modèle MLflow │
│ • Merge    │   │  • MLflow      │   │  • Inférence     │
│   datasets │   │    tracking    │   │  • Top-K résult. │
└────────────┘   └───────┬────────┘   └──────────────────┘
                         │
              ┌──────────┴──────────┐
              │                     │
              ▼                     ▼
┌─────────────────────┐  ┌──────────────────────────────┐
│  Stockage local     │  │  MLflow + DagsHub             │
│  (volumes Docker)   │  │  • Tracking expériences       │
│  • data/            │  │  • Métriques / artefacts      │
│  • models/          │  │  • DVC remote (données)       │
└─────────────────────┘  └──────────────────────────────┘
                                     │
              ┌──────────────────────┤
              ▼                      ▼
┌──────────────────┐      ┌────────────────────────┐
│  Prometheus      │      │  Evidently             │
│  • Métriques     │      │  • Data drift          │
│    système       │      │  • Model monitoring    │
└────────┬─────────┘      └────────────────────────┘
         ▼
┌──────────────────┐
│  Grafana         │
│  • Dashboards    │
└──────────────────┘
```

### Flux de traitement des données

```
data/raw/rakuten/
  ├── X_train_update.csv       ──┐
  └── Y_train_CVw08PX.csv       ─┤─► DataIngestion ──► DataPreprocessing
data/raw/product_categories.csv ─┘        │
                                          ▼
                                  data/interim/rakuten_train.csv
                                          │
                                          ▼
                                  DataTransformation
                                  (TF-IDF + train/test split)
                                          │
                                          ▼
                                  data/processed/
                                          │
                                          ▼
                                  ModelTrainer (Linear SVC)
                                          │
                                          ▼
                                  models/text_classifier.pkl
```

---

## Project Organization

```
├── Makefile                   <- Commandes utilitaires (data, train, docker...)
├── README.md
├── .env                       <- Variables d'environnement (non versionné)
├── data
│   ├── interim                <- Données transformées intermédiaires
│   ├── processed              <- Datasets finaux pour l'entraînement
│   └── raw                    <- Données brutes immuables
│
├── docker-compose.yml         <- Orchestration des conteneurs
│
├── docker
│   └── api-service
│       └── Dockerfile
│
├── deployments
│   ├── certs
│   │   ├── nginx.crt          <- Certificat TLS
│   │   └── nginx.key          <- Clé privée
│   ├── nginx
│   │   └── nginx.conf         <- Configuration Nginx (reverse proxy + TLS)
│   └── prometheus
│       └── prometheus.yml
│
├── docs                       <- Documentation MkDocs
├── logs                       <- Logs applicatifs et erreurs
├── models                     <- Modèles entraînés et sérialisés
├── notebooks
│   └── 01_exploration.ipynb
│
├── pyproject.toml
├── requirements.txt
├── requirements-dev.txt
│
├── tests/
│   ├── test_pipelines.py
│   ├── test_data_ingestion.py
│   ├── test_data_preprocessing.py
│   ├── test_data_transformation.py
│   ├── test_model_trainer.py
│   ├── test_model_evaluation.py
│   └── test_prediction.py
│
└── mlops_rakuten/
    ├── main.py                <- Point d'entrée CLI (train / predict)
    ├── services/              <- API FastAPI (gateway, ingest, train, predict)
    ├── auth/                  <- OAuth2 + gestion des utilisateurs
    ├── config/                <- Configuration YAML, entités, constantes
    ├── modules/               <- Logique métier (ingestion → évaluation)
    ├── pipelines/             <- Pipelines orchestrant les modules
    └── utils.py
```

---

## Installation

### 1. Environnement Python

Vérifier si `uv` est installé, sinon [l'installer](https://docs.astral.sh/uv/getting-started/installation/) :

```bash
uv --version
```

Créer et activer l'environnement, puis installer les dépendances :

```bash
make create_environment
source .venv/bin/activate
make requirements
```

Vérifier l'installation :

```bash
python -c "import pandas, typer, mlops_rakuten; print('OK')"
```

### 2. Configuration des données

Les données ne sont pas incluses dans le repository et doivent être téléchargées manuellement.

**Fichiers requis :**
- `X_train_update.csv`
- `Y_train_CVw08PX.csv`
- `product_categories.csv`

**Mise en place :**

```bash
mkdir -p data/raw/rakuten

# Copier les fichiers :
# product_categories.csv  →  data/raw/
# X_train_update.csv      →  data/raw/rakuten/
# Y_train_CVw08PX.csv     →  data/raw/rakuten/
```

Vérification :

```bash
ls data/raw/            # → product_categories.csv
ls data/raw/rakuten/    # → X_train_update.csv  Y_train_CVw08PX.csv
```

---

## Structure du pipeline de données

Le pipeline suit une architecture en 5 étapes séquentielles.

**Étape 1 — Configuration** (`config/`) : les chemins de fichiers et paramètres sont centralisés dans `config.yml`. Les entités Python (`entities.py`) assurent un typage fort via dataclasses. Le `config_manager.py` instancie les objets de configuration pour chaque étape.

**Étape 2 — Data Seeding** : découpage du dataset initial en sous-ensembles reproductibles.

**Étape 3 — Data Ingestion** : fusion des fichiers features (`X_train`) et target (`Y_train`) avec les catégories produits.

**Étape 4 — Data Preprocessing** : nettoyage (valeurs nulles, outliers, doublons).

**Étape 5 — Data Transformation** : vectorisation TF-IDF sur les champs textuels (`designation`), découpage train/test, sauvegarde des artefacts.

**Étape 6 — Model Trainer** : entraînement d'un classificateur Linear SVC, sauvegarde du modèle sérialisé (`.pkl`) et tracking MLflow.

**Étape 7 — Model Evaluation** : calcul des métriques (accuracy, F1-score), génération de la matrice de confusion, promotion des alias MLflow.

Chaque étape est encapsulée dans un module (`modules/`) et exposée via un pipeline (`pipelines/`). L'exécution complète s'effectue via `main.py`.

---

## Sécurité et Gateway

### Vue d'ensemble

La sécurité repose sur deux couches complémentaires : la terminaison TLS par Nginx et l'authentification applicative OAuth2.

```
Internet
   │
   │ HTTPS (port 443)
   ▼
┌──────────────────────────────────────┐
│  NGINX — Reverse Proxy               │
│  • Terminaison TLS (certificat X.509)│
│  • Redirect HTTP → HTTPS             │
│  • Forwarding vers Gateway (HTTP)    │
└──────────────────┬───────────────────┘
                   │ HTTP interne (réseau Docker)
                   ▼
┌──────────────────────────────────────┐
│  API Gateway (FastAPI)               │
│  • POST /token  → émission JWT       │
│  • Validation Bearer Token           │
│  • Routing sécurisé vers services    │
└──────────────────────────────────────┘
```

### Nginx — Terminaison TLS

La configuration Nginx (`deployments/nginx/nginx.conf`) assure :
- L'écoute sur le port 443 en HTTPS
- La redirection automatique du port 80 vers 443
- Le proxy pass vers le service `api-gateway` sur le réseau interne Docker
- La transmission des headers (`X-Forwarded-For`, `X-Real-IP`) pour la traçabilité

**Génération du certificat auto-signé (développement) :**

```bash
mkcert -key-file deployments/certs/nginx.key \
       -cert-file deployments/certs/nginx.crt \
       localhost 127.0.0.1 ::1
```

> En production, remplacer par un certificat Let's Encrypt.

### Authentification OAuth2 / Bearer Token

L'authentification est gérée par le module `auth/` via le standard OAuth2 Password Flow :

1. Le client envoie ses credentials (`username` / `password`) sur `POST /token`
2. Le gateway vérifie le mot de passe haché (`auth/hash_password.py`) contre `auth/users.json`
3. Un Bearer Token est retourné
4. Toutes les routes protégées exigent ce token dans le header `Authorization: Bearer <token>`

**Utilisateurs configurés :**

| Utilisateur | Rôle  | Mot de passe |
|-------------|-------|--------------|
| jane        | user  | password     |
| john        | user  | password     |
| julien      | admin | admin123     |
| claudia     | admin | admin456     |
| samuel      | admin | admin789     |

> Les mots de passe sont stockés sous forme de hash dans `auth/users.json`.

---

## Suivi d'expériences et versioning

### DagsHub + DVC

[DagsHub](https://dagshub.com) est la plateforme centrale de collaboration MLOps. Elle héberge le repository Git et le remote DVC pour le versioning des données.

[DVC](https://dvc.org) (*Data Version Control*) gère le versioning des datasets et artefacts sans les stocker dans Git. Les fichiers suivis génèrent des pointeurs `.dvc` et mettent à jour le `.gitignore` automatiquement.

### Configuration — fichier `.env`

Créer un fichier `.env` à la racine du projet (non versionné, ajouté au `.gitignore`) :

```dotenv
# ── DagsHub / MLflow ──────────────────────────────────────────────────────────
DAGSHUB_USER=shiff-oumi
DAGSHUB_REPO=nov25cmlops_rakuten_dag
DAGSHUB_TOKEN=<token_dagshub>

MLFLOW_TRACKING_URI=https://dagshub.com/shiff-oumi/nov25cmlops_rakuten_dag.mlflow
MLFLOW_TRACKING_USERNAME=shiff-oumi
MLFLOW_TRACKING_PASSWORD=<token_dagshub>
```

Ces variables configurent à la fois le remote DVC (authentification) et le tracking server MLflow.

> Le token DagsHub est le même pour DVC et MLflow. Il se génère dans les paramètres du compte DagsHub → *Settings → Access Tokens*.

---

### Pipeline DVC

La pipeline est définie dans `dvc.yaml` et orchestrée en plusieurs étapes.

#### Initialisation

```bash
dvc init

# Ajouter les fichiers raw au tracking DVC
dvc add data/raw/rakuten/X_train_update.csv
dvc add data/raw/rakuten/Y_train_CVw08PX.csv
dvc add data/raw/product_categories.csv
```

#### 1. Seed

Découpe le dataset complet en 10 fichiers de 1 000 lignes pour permettre une ingestion incrémentale.

```bash
dvc repro seed
```

Le fichier de sortie `data/interim/rakuten_train.csv` est tracké via un pointeur DVC (et non via la pipeline, pour éviter de déclencher une réinitialisation à chaque changement) :

```bash
dvc add data/interim/rakuten_train.csv
```

#### 2. Ingestion

```bash
python mlops_rakuten/pipelines/data_ingestion.py
dvc add data/interim/rakuten_train.csv
```

#### 3. Pipeline complète

```bash
dvc repro
```

#### Graphe de la pipeline

```
+-----------------------------------------+        +------------------------------------------+        +-------------------------------------+
| data/raw/rakuten/X_train_update.csv.dvc |        | data/raw/rakuten/Y_train_CVw08PX.csv.dvc |        | data/raw/product_categories.csv.dvc |
+-----------------------------------------+        +------------------------------------------+        +-------------------------------------+
                                          \                        |                        /
                                           \                       |                       /
                                                           +------+
                                                           | seed |
                                                           +------+
                                                               |
                                         +------------------------------------+
                                         | data/interim/rakuten_train.csv.dvc |
                                         +------------------------------------+
                                                               |
                                                       +------------+
                                                       | preprocess |
                                                       +------------+
                                                               |
                                                       +-----------+
                                                       | transform |
                                                       +-----------+
                                                               |
                                                         +-------+
                                                         | train |
                                                         +-------+
                                                               |
                                                        +----------+
                                                        | evaluate |
                                                        +----------+
```

À chaque étape, versionner les fichiers `.dvc` et `dvc.lock` dans Git :

```bash
git add .
git commit -m "..."
git push
```

---

### Configuration du remote DagsHub

```bash
# Créer le remote DVC
dvc remote add origin https://dagshub.com/shiff-oumi/nov25cmlops_rakuten_dag.dvc

# Configurer l'authentification locale
# (crée automatiquement .dvc/config.local, ignoré par .gitignore)
dvc remote modify origin --local auth basic
dvc remote modify origin --local user shiff-oumi
dvc remote modify origin --local password <token_dagshub>

# Synchronisation des données
dvc push   # ──► DagsHub S3
dvc pull   # ◄── DagsHub S3
```

---

### MLflow — Suivi d'expériences et registre de modèles

MLflow assure trois rôles distincts dans le projet :

- **Experiment Tracking** : chaque run de training logue ses hyperparamètres, métriques et artefacts
- **Model Registry** : les versions de modèles sont enregistrées et promues via un système d'alias
- **Artifact Store** : les objets de preprocessing (vectorizer, label encoder, mapping catégories) sont stockés et récupérables à tout moment

Le tracking server est hébergé sur DagsHub, ce qui centralise l'accès à toute l'équipe.

#### Cycle de vie d'un run

**1. Training — `ModelTrainer`**

Le training ouvre un run MLflow et logue l'ensemble des informations dans un seul bloc `with mlflow.start_run()`.

Paramètres loggés : `model_type`, `C`, `max_iter`, `use_class_weight`.
Métriques loggées : `train_accuracy`, `train_f1_macro`.

Artefacts loggés :

```
run/
├── preprocessing/
│   ├── tfidf_vectorizer.pkl
│   ├── label_encoder.pkl
│   └── class_mapping.json
├── model/                        ← enregistré dans le Model Registry
├── model_config.json
├── metrics_train.json
└── classification_report_train.txt
```

En fin de run, le modèle reçoit l'alias `pending` dans le Model Registry. Le `run_id` est sauvegardé dans `mlflow_run_metadata.json` (tracké par DVC) pour être réutilisé par l'étape d'évaluation.

**2. Évaluation — `ModelEvaluation`**

L'évaluation réouvre le run du training via son `run_id` pour y ajouter les métriques de validation (`val_accuracy`, `val_f1_macro`, `val_f1_weighted`). Si le `run_id` est introuvable, un nouveau run est créé dans l'experiment `model_evaluation` en fallback.

**3. Prédiction — `Prediction`**

La classe `Prediction` charge l'ensemble de ses artefacts depuis MLflow (alias `production`), avec un fallback sur les fichiers locaux si MLflow est indisponible.

#### Système d'alias — Model Registry

Les alias remplacent les stages (`Staging`, `Production`) dépréciés dans MLflow 2.x.

```
text_classifier_tfidf_m
├── @pending     → Nouvellement entraîné, en attente d'évaluation
├── @production  → Meilleur modèle validé, utilisé par Prediction
└── @archived    → Ancienne version production, conservée pour traçabilité
```

Logique de promotion :

```
Après training
    → alias "pending" attribué à la nouvelle version

Après évaluation
    ├── Pas de version @production existante
    │       → Promotion directe : pending → production
    │
    └── Une version @production existe
            ├── val_f1_macro (nouveau) ≥ val_f1_macro (prod) + 0.01
            │       → pending → production
            │       → ancienne production → archived
            │
            └── Amélioration insuffisante
                    → Pas de changement, la version reste "pending"
```

#### Flux de données — DVC et MLflow

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                              SOURCES DE DONNÉES                              │
│   data/raw/X_train.csv   data/raw/Y_train.csv   data/raw/categories.csv     │
└───────────────────────┬──────────────────────────────────────────────────────┘
                        │  dvc add  →  pointeurs .dvc trackés par Git
                        ▼
              ┌──────────────────┐
              │   dvc push  ──►  │──────────────────────────────────────────►  DagsHub S3
              │   dvc pull  ◄──  │◄─────────────────────────────────────────  (stockage binaire)
              └──────────────────┘
                        │
                        │  dvc repro  (seed → preprocess → transform → train → evaluate)
                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  STAGE : train                                                              │
│                                                                             │
│  X_train.npz  +  y_train.npy                                               │
│       │                                                                     │
│       ▼                                                                     │
│  ModelTrainer.run()                                                         │
│       │                                                                     │
│       ├──► mlflow.log_param / log_metric  ─────────────────────────────►   DagsHub MLflow
│       │                                                                     (Tracking Server)
│       ├──► mlflow.log_artifact (preprocessing/)  ──────────────────────►   DagsHub S3
│       │         tfidf_vectorizer.pkl                                        (Artifact Store)
│       │         label_encoder.pkl
│       │         class_mapping.json
│       │
│       ├──► mlflow.sklearn.log_model  ──────────────────────────────────►   Model Registry
│       │         → alias "pending" attribué                                  (DagsHub MLflow)
│       │
│       └──► mlflow_run_metadata.json  →  dvc add  →  dvc push  ────────►   DagsHub S3
│
└─────────────────────────────────────────────────────────────────────────────┘
                        │
                        │  dvc repro  (étape suivante : evaluate)
                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  STAGE : evaluate                                                           │
│                                                                             │
│  ModelEvaluation.run()                                                      │
│       │                                                                     │
│       ├──► mlflow.sklearn.load_model("@pending")  ◄────────────────────    Model Registry
│       │
│       ├──► mlflow.start_run(run_id=train_run_id)
│       │         val_accuracy, val_f1_macro, val_f1_weighted  ──────────►   DagsHub MLflow
│       │                                                                     (même run que training)
│       └──► _manage_alias_promotion()
│                 pending → production  (si F1 suffisant)
│                 ancienne production  → archived
│
└─────────────────────────────────────────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  SERVICE : predict                                                          │
│                                                                             │
│  Prediction._load_artifacts()                                               │
│       │                                                                     │
│       ├──► mlflow.sklearn.load_model("@production")  ◄─────────────────    Model Registry
│       │
│       ├──► mlflow.artifacts.download_artifacts("preprocessing/")  ◄────    Artifact Store
│       │         tfidf_vectorizer.pkl
│       │         label_encoder.pkl
│       │         class_mapping.json
│       │
│       └──► Fallback local si MLflow indisponible
│
└─────────────────────────────────────────────────────────────────────────────┘

─────────────────────────────────────────────────────────────────────────────
  RÉSUMÉ DES FLUX DE PUSH / PULL
─────────────────────────────────────────────────────────────────────────────

  DVC   push / pull  ──►  DagsHub S3      : données brutes et intermédiaires
                                            (.csv, .npz, .npy, mlflow_run_metadata.json)
                                            pointeurs .dvc versionnés dans Git

  MLflow log         ──►  DagsHub MLflow  : params, métriques, runs
  MLflow log         ──►  DagsHub S3      : modèle + artefacts preprocessing
  MLflow load        ◄──  DagsHub MLflow  : modèle @production, artefacts preprocessing

  Git   push / pull  ──►  GitHub          : code, .dvc, dvc.lock, dvc.yaml, config
```

#### Ce qui est versionné où

| Objet                            | Outil  | Destination        |
|----------------------------------|--------|--------------------|
| Données brutes (CSV)             | DVC    | DagsHub S3         |
| Données intermédiaires (npz/npy) | DVC    | DagsHub S3         |
| `mlflow_run_metadata.json`       | DVC    | DagsHub S3         |
| Code source                      | Git    | GitHub             |
| `.dvc`, `dvc.lock`, `dvc.yaml`   | Git    | GitHub             |
| Hyperparamètres, métriques       | MLflow | DagsHub MLflow     |
| Modèle                           | MLflow | DagsHub S3         |
| Vectorizer, LabelEncoder         | MLflow | DagsHub S3         |
| Alias de modèle (pending, prod…) | MLflow | DagsHub MLflow     |

---

## Containerisation via Docker

### Configuration — fichier `.env`

En plus des variables DagsHub/MLflow, le `.env` contient les variables nécessaires aux containers pour effectuer des commits Git automatiques depuis l'intérieur des services.

```dotenv
# ── DagsHub / MLflow ──────────────────────────────────────────────────────────




# ── Git / GitHub ───────────────────────────────────────────────────────────────

```

**Pourquoi séparer `DAGSHUB_REPO` et `GITHUB_REPO` ?**

DagsHub héberge les données DVC et le tracking MLflow. GitHub héberge le code source. Les deux repos sont distincts, ce qui permet d'identifier clairement l'origine d'un commit : un commit portant `GIT_AUTHOR_NAME=Rakuten MLOps` a été produit automatiquement par un container (ex. après un `dvc push` ou un push d'artefact), tandis qu'un commit avec le nom du développeur est un commit manuel.

**Clé SSH et mount**

Chaque développeur monte sa propre clé SSH dans le container pour les opérations Git. Le mount est défini dans `docker-compose.yml` :

```yaml
volumes:
  - ~/.ssh:/root/.ssh:ro
```

Cela permet à chaque membre de l'équipe de pousser sur GitHub avec ses propres droits, sans partager de credentials dans le `.env`.

> Le fichier `.env` ne doit jamais être commité. Il est ajouté au `.gitignore`. Chaque développeur crée le sien localement à partir du modèle `.env.example`.

---

## Containerisation via Docker

### Services

La stack Docker Compose comprend les services suivants :

| Service        | Rôle                                         | Port exposé |
|----------------|----------------------------------------------|-------------|
| `nginx`        | Reverse proxy + terminaison TLS              | 443         |
| `api-gateway`  | Authentification + routage                   | interne     |
| `api-train`    | Pipeline d'entraînement                      | interne     |
| `api-predict`  | Service d'inférence                          | interne     |
| `api-ingest`   | Ingestion et fusion des datasets             | interne     |
| `prometheus`   | Collecte de métriques                        | 9090        |

### Volumes

Les données et modèles sont persistés via des volumes Docker nommés, assurant la séparation entre le cycle de vie des conteneurs et celui des données.

### Exécution

```bash
# Build et démarrage de la stack
make docker-up

# Vérification des conteneurs
make docker-ps

# Injection des données d'entraînement (obligatoire avant le premier run)
make docker-cp-traincsv

# Logs en temps réel
make docker-logs

# Arrêt (volumes conservés)
make docker-down

# Arrêt + suppression des volumes  ⚠️ destructif
make docker-down-v
```

---

## Lancer l'application avec Docker

### 1. Démarrer la stack

```bash
make docker-up
make docker-ps   # vérification
```

### 2. Injecter les données d'entraînement

```bash
make docker-cp-traincsv
```

Cette commande copie `data/interim/rakuten_train.csv` vers `/app/data/interim/rakuten_train.csv` dans le volume Docker. **Étape obligatoire avant le premier entraînement.**

### 3. Accéder à Swagger

```bash
make swagger
# → https://localhost/docs
```

### Workflow via Swagger

**1. Authentification** — `POST /token`

Fournir `username` et `password`, récupérer le `access_token`, puis cliquer sur **Authorize** :
```
Bearer <access_token>
```

**2. Entraîner un modèle** — `POST /train`

Lance la pipeline complète. Le modèle est sauvegardé dans `/app/models/<timestamp>/text_classifier.pkl`.

**3. Vérifier l'état** — `GET /info`

Retourne le statut du modèle (`ready`), son chemin et le dernier dataset traité.

**4. Prédire** — `POST /predict`

```json
{
  "designation": "Très joli pull pour enfants",
  "top_k": 3
}
```

### Tests en ligne de commande

```bash
# Authentification
curl -k -X POST https://localhost/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=julien&password=admin123"

# Entraînement
curl -k -X POST https://localhost/train \
  -H "Authorization: Bearer <TOKEN>"

# Informations modèle
curl -k https://localhost/info \
  -H "Authorization: Bearer <TOKEN>"

# Prédiction
curl -k -X POST https://localhost/predict \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"designation":"Très joli pull pour enfants","top_k":3}'
```

> L'option `-k` est nécessaire avec un certificat TLS auto-signé.

---

## Monitoring

### Evidently

Evidently est utilisé pour le monitoring de la qualité du modèle en production :
- Détection de **data drift** (évolution de la distribution des inputs)
- Monitoring des **performances** au fil du temps
- Génération de rapports HTML comparant les distributions de référence et de production

### Prometheus + Grafana

Prometheus collecte les métriques d'infrastructure et applicatives exposées par les services FastAPI. Grafana visualise ces métriques via des dashboards configurables.

Accès Prometheus : [http://localhost:9090](http://localhost:9090)

---

## Tests

Les tests couvrent chaque étape du pipeline de manière isolée :

```bash
# Lancer tous les tests
pytest tests/

# Tests par module
pytest tests/test_data_ingestion.py
pytest tests/test_model_trainer.py
pytest tests/test_prediction.py
```

| Fichier de test              | Couverture                        |
|------------------------------|-----------------------------------|
| `test_pipelines.py`          | Pipeline complète (intégration)   |
| `test_data_ingestion.py`     | Fusion des datasets               |
| `test_data_preprocessing.py` | Nettoyage des données             |
| `test_data_transformation.py`| TF-IDF + split                    |
| `test_model_trainer.py`      | Entraînement Linear SVC           |
| `test_model_evaluation.py`   | Métriques et matrice de confusion |
| `test_prediction.py`         | Inférence et format de sortie     |

---

## Commandes Makefile (Docker)

| Commande                  | Description                                          |
|---------------------------|------------------------------------------------------|
| `make docker-up`          | Build et démarre l'ensemble des services             |
| `make docker-down`        | Arrête les services (volumes conservés)              |
| `make docker-down-v`      | Arrête les services **et supprime les volumes** ⚠️   |
| `make docker-ps`          | Liste l'état des conteneurs                          |
| `make docker-cp-traincsv` | Injecte `rakuten_train.csv` dans le volume Docker    |
| `make docker-logs`        | Affiche les logs en temps réel                       |
| `make swagger`            | Ouvre Swagger UI dans le navigateur                  |
| `make create_environment` | Crée l'environnement Python avec `uv`                |
| `make requirements`       | Installe les dépendances Python                      |
