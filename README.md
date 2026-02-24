# MLOps Rakuten

Classification de types de produits pour Rakuten France

> Projet MLOps de bout en bout : ingestion de données, entraînement de modèle, exposition via API sécurisée, orchestration batch, monitoring et versioning.

---

## Table des matières

- [Architecture globale](#architecture-globale)
- [Modes d'exécution](#modes-dexécution)
- [Project Organization](#project-organization)
- [Installation](#installation)
- [Structure du pipeline de données](#structure-du-pipeline-de-données)
- [Sécurité et Gateway](#sécurité-et-gateway)
- [Suivi d'expériences et versioning](#suivi-dexpériences-et-versioning)
- [Containerisation via Docker](#containerisation-via-docker)
- [Lancer l'application avec Docker](#lancer-lapplication-avec-docker)
- [Orchestration batch avec Airflow](#orchestration-batch-avec-airflow)
- [Monitoring](#monitoring)
- [Tests](#tests)
- [Commandes Makefile](#commandes-makefile)

---

## Architecture globale

Le projet suit une architecture microservices conteneurisée. Le même pipeline de données et d'entraînement est accessible via trois modes d'exécution distincts, selon le contexte (développement, API, automatisation batch).

```
┌──────────────────────────────────────────────────────────────────────┐
│               MODES DE DÉCLENCHEMENT                                 │
│                                                                      │
│   Mode 1 — CLI local      make ingest-dvc / train-dvc               │
│   Mode 2 — API curl       curl / Swagger → nginx → gateway → api-*  │
│   Mode 3 — Airflow batch  DAG schedulé → subprocess → main.py       │
└───────────────────────────────┬──────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         CLIENT (curl / Swagger / Airflow)           │
└────────────────────────────┬────────────────────────────────────────┘
                             │ HTTPS (TLS auto-signé)
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        NGINX (Reverse Proxy)                        │
│  • Terminaison TLS                                                  │
│  • Routage vers le service API Gateway                              │
└────────────────────────────┬────────────────────────────────────────┘
                             │ HTTP interne
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       API GATEWAY (FastAPI)                         │
│  • Authentification OAuth2 / Bearer Token                           │
│  • Routage vers les services internes                               │
└──────┬──────────────────┬──────────────────────┬────────────────────┘
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
│  Prometheus      │      │  Grafana               │
│  • Métriques     │      │  • Dashboards          │
└──────────────────┘      └────────────────────────┘
```

---

## Modes d'exécution

Le projet expose **trois modes d'exécution** qui partagent le même pipeline (`main.py`, `cli.py`) et diffèrent uniquement par leur transport et leur déclencheur.

### Vue d'ensemble

```
┌─────────────────┬────────────────────┬──────────────────────────────┐
│ Mode            │ Déclencheur        │ Transport                    │
├─────────────────┼────────────────────┼──────────────────────────────┤
│ CLI local       │ make / terminal    │ subprocess direct            │
│ API curl        │ humain / Swagger   │ HTTP → nginx → gateway       │
│ Airflow batch   │ scheduler / cron   │ DAG → subprocess → main.py   │
└─────────────────┴────────────────────┴──────────────────────────────┘
```

### Mode 1 — CLI local

Exécution directe sur la machine de développement, sans Docker. Utilisé pour le développement et les tests rapides.

```bash
# Ingestion d'un batch
python mlops_rakuten/main.py ingest data/raw/rakuten/seeds/rakuten_batch_0001.csv

# Entraînement
python mlops_rakuten/main.py train

# Ou via Makefile
make ingest-dvc CSV=rakuten_batch_0001.csv
make train-dvc
```

### Mode 2 — API Docker

Deux sous-modes contrôlés par la variable `EXECUTION_MODE` :

#### EXECUTION_MODE=cli (recommandé)

Les services FastAPI (`api-ingest`, `api-train`) exécutent DVC et Git via **subprocess** directement dans leur container. Aucun container supplémentaire.

```bash
make docker-up-cli
# Lance : nginx + gateway + api-ingest + api-train + api-predict + monitoring
```

#### EXECUTION_MODE=docker (docker-in-docker)

Les services FastAPI délèguent DVC et Git à des containers dédiés (`dvc-runner`, `git-runner`) via `docker exec`. Mode pédagogique pour démontrer une architecture microservices avancée.

```bash
make docker-up-docker
# Lance : tous les services + dvc-runner + git-runner
```

```
EXECUTION_MODE=cli                    EXECUTION_MODE=docker
──────────────────────────────────    ────────────────────────────────────
api-ingest                            api-ingest
  └── subprocess → dvc/git              └── docker exec → rakuten-dvc-runner
                                                        → rakuten-git-runner
```

**Appels API (identiques dans les deux sous-modes) :**

```bash
make api-token                              # récupérer un JWT
make api-init                               # initialiser le dataset seed
make api-ingest CSV=rakuten_batch_0001.csv  # ingérer un batch
make api-train                              # entraîner
make api-predict TEXT="Vélo électrique" TOPK=3
```

### Mode 3 — Airflow batch (automatisé)

Airflow orchestre le pipeline complet de façon autonome. Il réutilise le transport CLI (`utils/cli.py`) — même code que le Mode 1, simplement déclenché par un scheduler.

```bash
make docker-up-batch      # stack CLI + Airflow
make airflow-trigger      # déclencher manuellement
make airflow-set-batch N=3
```

Le DAG `rakuten_batch_pipeline` s'exécute tous les lundis à 3h00 :

```
check_batch ──► ingest_batch ──► train_model ──► increment_batch
     │
     └── no_batch (si CSV introuvable → skip)
```

### Commits Git par mode

Chaque mode produit des commits identifiables dans l'historique Git :

```
git log --oneline

a3f1c2e  Airflow:train  — model v26, f1_macro=0.7750  ← automatique (Airflow)
58ee89f  Airflow:ingest — batch=rakuten_batch_0003     ← automatique (Airflow)
3a2f1c4  CLI:train      — model v25, f1_macro=0.7697  ← manuel (API / CLI)
9b4e2d1  CLI:ingest     — batch=rakuten_batch_0002     ← manuel (API / CLI)
```

### Résumé des profiles Docker

| Commande Makefile         | Services                               | Usage                      |
|---------------------------|----------------------------------------|----------------------------|
| `make docker-up-cli`      | stack de base, EXECUTION_MODE=cli      | Dev / démo API             |
| `make docker-up-docker`   | stack + runners, EXECUTION_MODE=docker | Démo docker-in-docker      |
| `make docker-up-batch`    | stack cli + airflow (profile batch)    | Batch automatisé           |

---

## Project Organization

```
├── Makefile                   <- Commandes utilitaires
├── README.md
├── .env                       <- Variables d'environnement (non versionné)
├── Dockerfile                 <- Image commune à tous les services
├── entrypoint.sh              <- Init Git/DVC/SSH au démarrage des containers
├── docker-compose.yml         <- Orchestration (tous modes)
│
├── data/
│   ├── interim/               <- Données intermédiaires
│   ├── processed/             <- Datasets finaux pour l'entraînement
│   └── raw/
│       └── rakuten/
│           └── seeds/         <- Batches CSV (rakuten_batch_0001.csv … 0010.csv)
│
├── deployments/
│   ├── airflow/
│   │   ├── docker-compose.airflow.yml
│   │   └── dags/
│   │       └── rakuten_batch_pipeline.py
│   ├── certs/                 <- Certificats TLS
│   ├── nginx/
│   │   └── nginx.conf
│   └── prometheus/
│       └── prometheus.yml
│
├── models/                    <- Modèles entraînés
├── reports/                   <- Métriques et rapports
├── logs/                      <- Logs applicatifs
│
├── tests/
│
└── mlops_rakuten/
    ├── main.py                <- Point d'entrée CLI
    ├── services/              <- API FastAPI (gateway, ingest, train, predict)
    ├── auth/                  <- OAuth2
    ├── config/                <- config.yml, entités, constantes
    ├── modules/               <- Logique métier
    ├── pipelines/             <- Pipelines orchestrant les modules
    └── utils/
        ├── cli.py             <- Transport subprocess (Modes 1 et 3)
        ├── docker.py          <- Transport docker exec (Mode 2 docker)
        └── sync_core.py       <- Logique Git/DVC commune
```

---

## Installation

### 1. Environnement Python

```bash
uv --version   # vérifier uv, sinon : https://docs.astral.sh/uv/
make create_environment
source .venv/bin/activate
make requirements
python -c "import pandas, typer, mlops_rakuten; print('OK')"
```

### 2. Configuration des données

```bash
mkdir -p data/raw/rakuten

# Copier les fichiers :
# product_categories.csv  →  data/raw/
# X_train_update.csv      →  data/raw/rakuten/
# Y_train_CVw08PX.csv     →  data/raw/rakuten/
```

### 3. Fichier .env

```dotenv
# DagsHub / MLflow
DAGSHUB_USER=shiff-oumi
DAGSHUB_REPO=nov25cmlops_rakuten_dag
DAGSHUB_TOKEN=<token_dagshub>
MLFLOW_TRACKING_URI=https://dagshub.com/shiff-oumi/nov25cmlops_rakuten_dag.mlflow
MLFLOW_TRACKING_USERNAME=shiff-oumi
MLFLOW_TRACKING_PASSWORD=<token_dagshub>

# Git / GitHub
GIT_AUTHOR_NAME=Rakuten MLOps
GIT_AUTHOR_EMAIL=mlops@rakuten.local
GITHUB_USER=shiff-oumi
GITHUB_TOKEN=<token_github>
```

---

## Structure du pipeline de données

```
data/raw/  (X_train, Y_train, categories)
    │  dvc add
    ▼
  seed  →  data/raw/rakuten/seeds/  (10 batches × ~1000 lignes)
    │
    ▼  (après make api-ingest ou make api-init)
  data/interim/rakuten_train.csv    (dataset courant, tracké DVC)
    │  dvc repro
    ▼
  preprocess  →  data/interim/preprocessed_dataset.csv
    ▼
  transform   →  data/processed/  (TF-IDF, splits train/val)
    ▼
  train       →  models/text_classifier.pkl  +  MLflow (alias: pending)
    ▼
  evaluate    →  reports/  +  promotion MLflow (pending → production si +1% F1)
```

---

## Sécurité et Gateway

```
Internet  (HTTPS 443)
   ▼
NGINX  →  terminaison TLS, redirect HTTP→HTTPS
   ▼
API Gateway (FastAPI)  →  POST /token, validation Bearer Token, routing
   ▼
api-ingest / api-train / api-predict
```

**Génération du certificat auto-signé :**

```bash
mkcert -key-file deployments/certs/nginx.key \
       -cert-file deployments/certs/nginx.crt \
       localhost 127.0.0.1 ::1
```

**Utilisateurs configurés :**

| Utilisateur | Rôle  | Mot de passe |
|-------------|-------|--------------|
| jane        | user  | password     |
| john        | user  | password     |
| julien      | admin | admin123     |
| claudia     | admin | admin456     |
| samuel      | admin | admin789     |

---

## Suivi d'expériences et versioning

### Ce qui est versionné où

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
| Alias modèle (pending, prod…)    | MLflow | DagsHub MLflow     |

### Système d'alias MLflow

```
text_classifier_tfidf_m
├── @pending     → Nouvellement entraîné, en attente d'évaluation
├── @production  → Meilleur modèle validé, utilisé par Prediction
└── @archived    → Ancienne version, conservée pour traçabilité
```

Logique de promotion :

```
Après training  →  alias "pending" attribué

Après évaluation
  ├── Pas de @production → promotion directe
  └── @production existe
        ├── val_f1_macro (nouveau) ≥ val_f1_macro (prod) + 0.01 → promotion
        └── Amélioration insuffisante → pas de changement
```

### Configuration DVC remote

```bash
dvc remote add origin https://dagshub.com/shiff-oumi/nov25cmlops_rakuten_dag.dvc
dvc remote modify origin --local auth basic
dvc remote modify origin --local user shiff-oumi
dvc remote modify origin --local password <token_dagshub>

dvc push   # → DagsHub S3
dvc pull   # ← DagsHub S3
```

---

## Containerisation via Docker

### Services

| Service       | Rôle                                    | Port    | Profile    |
|---------------|-----------------------------------------|---------|------------|
| `nginx`       | Reverse proxy + TLS                     | 443     | toujours   |
| `gateway`     | Auth + routage                          | interne | toujours   |
| `api-ingest`  | Ingestion datasets                      | interne | toujours   |
| `api-train`   | Entraînement                            | interne | toujours   |
| `api-predict` | Inférence                               | interne | toujours   |
| `prometheus`  | Métriques                               | 9090    | toujours   |
| `grafana`     | Dashboards                              | 3000    | toujours   |
| `dvc-runner`  | DVC isolé (docker-in-docker)            | interne | `docker`   |
| `git-runner`  | Git isolé (docker-in-docker)            | interne | `docker`   |
| `airflow`     | Orchestration batch                     | 8082    | `batch`    |

### SSH et commits automatiques

```yaml
# docker-compose.yml
volumes:
  - ~/.ssh:/root/.ssh   # clé SSH du développeur montée dans les containers
```

L'`entrypoint.sh` configure `GIT_SSH_COMMAND` automatiquement au démarrage — pas de `chmod` sur le mount, compatible WSL2.

---

## Lancer l'application avec Docker

### Mode CLI

```bash
make docker-up-cli
make docker-ps
make api-health

make api-init
make api-ingest CSV=rakuten_batch_0001.csv
make api-train
make api-predict TEXT="Vélo électrique pliable" TOPK=3
```

### Mode Docker-in-Docker

```bash
make docker-up-docker
docker ps | grep runner   # vérifier que les runners sont UP
make api-ingest CSV=rakuten_batch_0002.csv
make api-train
```

### Swagger

```bash
make swagger   # → https://localhost/docs
```

---

## Orchestration batch avec Airflow

### Démarrage

```bash
make docker-up-batch
make airflow-ui    # → http://localhost:8082  (admin/admin)
```

### DAG — rakuten_batch_pipeline

```
Schedule : 0 3 * * 1  (tous les lundis à 3h)

check_batch
    ├── CSV trouvé → ingest_batch → train_model → increment_batch
    └── CSV absent → no_batch (skip)
```

Le DAG réutilise `mlops_rakuten.utils.cli` directement — même transport subprocess que le Mode CLI

### Commandes Airflow

```bash
make airflow-trigger          # déclencher manuellement
make airflow-runs             # voir les derniers runs
make airflow-set-batch N=3    # configurer le prochain batch
make airflow-ui               # ouvrir l'interface
```

---

## Monitoring

- **Prometheus** : métriques système et applicatives → [http://localhost:9090](http://localhost:9090)
- **Grafana** : dashboards → [http://localhost:3000](http://localhost:3000) (admin/admin)

---

## Tests

```bash
pytest tests/                           # tous les tests
pytest tests/test_model_trainer.py      # module spécifique
```

| Fichier                      | Couverture                        |
|------------------------------|-----------------------------------|
| `test_pipelines.py`          | Pipeline complète (intégration)   |
| `test_data_ingestion.py`     | Fusion des datasets               |
| `test_data_preprocessing.py` | Nettoyage                         |
| `test_data_transformation.py`| TF-IDF + split                    |
| `test_model_trainer.py`      | Entraînement                      |
| `test_model_evaluation.py`   | Métriques et matrice de confusion |
| `test_prediction.py`         | Inférence et format de sortie     |

---

## Commandes Makefile

### Stack Docker

| Commande                | Description                                          |
|-------------------------|------------------------------------------------------|
| `make docker-up-cli`    | Stack CLI (EXECUTION_MODE=cli, sans runners)         |
| `make docker-up-docker` | Stack Docker-in-Docker (avec runners)                |
| `make docker-up-batch`  | Stack CLI + Airflow                                  |
| `make docker-down`      | Arrêt (volumes conservés)                            |
| `make docker-down-v`    | Arrêt + suppression des volumes                      |
| `make docker-ps`        | État des containers                                  |
| `make docker-logs`      | Logs en temps réel                                   |
| `make docker-mode`      | Affiche EXECUTION_MODE actif                         |

### API

| Commande                              | Description                    |
|---------------------------------------|--------------------------------|
| `make api-health`                     | Santé de tous les services     |
| `make api-token`                      | Récupère un JWT                |
| `make api-init`                       | Initialise le dataset seed     |
| `make api-init-force`                 | Réinitialise (force)           |
| `make api-ingest CSV=<fichier>`       | Ingère un batch CSV            |
| `make api-train`                      | Lance l'entraînement           |
| `make api-predict TEXT=<t> TOPK=<n>`  | Prédiction                     |
| `make api-info`                       | Informations modèle actif      |

### Airflow

| Commande                      | Description                        |
|-------------------------------|------------------------------------|
| `make airflow-trigger`        | Déclenche le DAG manuellement      |
| `make airflow-runs`           | Liste les derniers runs            |
| `make airflow-set-batch N=3`  | Configure le prochain batch        |
| `make airflow-ui`             | Ouvre http://localhost:8082        |

### Environnement local

| Commande                  | Description                        |
|---------------------------|------------------------------------|
| `make create_environment` | Crée le venv Python avec `uv`      |
| `make requirements`       | Installe les dépendances           |
| `make ingest-dvc CSV=<f>` | Ingestion locale (Mode 1)          |
| `make train-dvc`          | Entraînement local (Mode 1)        |
| `make fix-permissions`    | Répare `.git/` et `data/`          |
| `make swagger`            | Ouvre https://localhost/docs       |
