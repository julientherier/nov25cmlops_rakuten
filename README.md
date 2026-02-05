# MLOps Rakuten

Product type classification for Rakuten France

---

## Project Organization

```
├── Makefile           <- Makefile with convenience commands like `make data` or `make train`
├── README.md          <- The top-level README for developers using this project.
├── data
│   ├── external       <- Data from third party sources.
│   ├── interim        <- Intermediate data that has been transformed.
│   ├── processed      <- The final, canonical data sets for modeling.
│   └── raw            <- The original, immutable data dump.
│
├── docker-compose.yml    <- Docker containers orchestration
│
├── docker
│   ├── api-service
│   │   └── Dockerfile      <- Configuration for the Base container
│
├── deployments
│   ├── certs
│   │   ├── nginx.crt       <- Nginx certificate
│   │   └── nginx.key       <- Certificate key
│   ├── nginx
│   │   └── nginx.conf      <- Configuration for Nginx
│   └── prometheus
│       └── prometheus.yml  <- Configuration for Prometheus
│
├── docs               <- A default mkdocs project; see www.mkdocs.org for details
│
├── logs               <- Contains all log and error files
│
├── models             <- Trained and serialized models, model predictions, or model summaries
│
├── notebooks
│   └── 01_exploration.ipynb  <- Text data exploration
│
│
├── pyproject.toml     <- Project configuration file with package metadata for
│                         mlops_rakuten and configuration for tools like black
│
├── references         <- Data dictionaries, manuals, and all other explanatory materials.
│
├── reports            <- Generated analysis as HTML, PDF, LaTeX, etc.
│   └── figures        <- Generated graphics and figures to be used in reporting
│
├── requirements-dev.txt   <- The requirements file for development environment
│
├── requirements.txt   <- The requirements file for reproducing the analysis environment
│
├── tests
│   ├── test_pipelines.py            <- Test all the pipelines
│   ├── test_data_ingestion.py       <- Test Data Ingestion
│   ├── test_data_preprocessing.py   <- Test Data Preprocessing
│   ├── test_data_transformation.py  <- Test Data Transformation
│   ├── test_model_trainer.py        <- Test Model Trainer
│   ├── test_model_evaluation.py     <- Test Model Evaluation
│   └── test_prediction.py           <- Test Prediction
│
└── mlops_rakuten   <- Source code for use in this project.
    │
    ├── __init__.py             <- Makes mlops_rakuten a Python module
    │
    ├── main.py                 <- Scripts to train model or make prediction
    │
    ├── services
    │   ├── gateway_app.py          <- API Gateway
    │   ├── ingest_app.py           <- API Ingest Service
    │   ├── predict_app.py          <- API Predict Service
    │   ├── schemas_app.py          <- pydantic Models
    │   └── train_app.py            <- API Train Service
    │
    ├── auth
    │   ├── auth_simple.py          <- OAuth2 authentication
    │   ├── hash_password.py        <- Utility script for getting password hash
    │   └── users.json              <- Users and Admins lists
    │
    ├── config
    │   ├── __init__.py
    │   ├── config_manager.py       <- Create Config objects
    │   ├── config.yml              <- Parameters for Config objects
    │   ├── constants.py            <- Store useful variables and configuration
    │   └── entities.py             <- Modules used to process data and train model
    │
    ├── modules
    │   ├── __init__.py
    │   ├── data_seeding.py         <- Code to split initial dataset
    │   ├── data_ingestion.py       <- Code to merge new dataset
    │   ├── data_preprocessing.py   <- Code to clean data
    │   ├── data_transformation.py  <- Code for TF-IDF and train / test split
    │   ├── model_trainer.py        <- Code for Linear SVC
    │   ├── model_evaluation.py     <- Code for evaluating Linear SVC performances
    │   └── prediction.py           <- Code for running inference
    │
    ├── pipelines
    │   ├── data_seeding.py         <- Data seeding pipeline
    │   ├── data_ingestion.py       <- Data ingestion pipeline
    │   ├── data_preprocessing.py   <- Data Preprocessing pipeline
    │   ├── data_transformation.py  <- Data Transformation pipeline
    │   ├── model_trainer.py        <- Model Trainer pipeline
    │   ├── model_evaluation.py     <- Model Evaluation pipeline
    │   └── prediction.py           <- Prediction pipeline
    │
    └── utils.py                <- Create directory and read YAML file
```

---

## Installation

### 1. Environnement Python

1. Vérifier si `uv` est installé, sinon [Installer uv](https://docs.astral.sh/uv/getting-started/installation/).
   `$ uv --version`

2. Création de l'environnement Python (macOs / Linux)
   `$ make create_environment`

3. Activer l'environnement Python (macOS / Linux)
   `$ source .venv/bin/activate`

4. Installer les dépendances
   `$ make requirements`

5. Vérifier que l'environnement est opérationnel
   `$ python -c "import pandas, typer, mlops_rakuten; print('OK')"`

### 2. Configuration des données

Les données ne sont pas incluses dans le repository. Vous devez les télécharger manuellement.

#### Étape 1 : Télécharger les données

- Accéder au dossier partagé
- Télécharger les fichiers :
  - `X_train_update.csv`
  - `Y_train_CVw08PX.csv`
  - `product_categories.csv`

#### Étape 2 : Créer le dossier et copier les fichiers
```bash
# Créer le dossier data/raw/rakuten s'il n'existe pas
$ mkdir -p data/raw/rakuten
```

#### Étape 3 : Copier-Coller les fichiers dans les repertoires
- `product_categories.csv` dans `data/raw/`
- `X_train_update.csv` et `Y_train_CVw08PX.csv` dans `data/raw/rakuten`

#### Étape 4 : Vérifier
```bash
# Vérifier la présence des fichiers
$ ls data/raw/
$ ls data/raw/rakuten

# Devrait afficher :
# product_categories.csv
# X_train_update.csv
# Y_train_CVw08PX.csv
```

---

## Structure

### Step 1: Classes de Configuration
- mlops_rakuten/config.py définit les variables globales contenant les chemins vers les répertoires et fichiers.
- mlops_rakuten/config.yml définit tous les chemins vers les fichiers qui seront utilisés ou créés à chaque étape du pipeline.
- mlops_rakuten/entities.py définit toutes les classes qui seront utilisés comme configuration.

### Step 2: Configuration Manager
- mlops_rakuten/config_manager.py crée les objets de configuration en s’appuyant sur les classes définies préalablement.
  + DataSeedingConfig
  + DataIngestionConfig
  + DataPreprocessingConfig
  + DataTransformationConfig
  + ModelTrainerConfig
  + ModelEvaluationConfig

### Step 3: les modules de Data et Model et Predict
- mlops_rakuten/modules/ définit les modules utilisés dans les pipelines Data et Model:
  + mlops_rakuten/modules/data_seeding.py définit le module de DataSeeding (découpage des données initiales)
  + mlops_rakuten/modules/data_ingestion.py définit le module de DataIngestion (fusion des datasets features et target)
  + mlops_rakuten/modules/data_preprocessing.py définit le module de DataPreprocessing (n/a, outliers, duplicates, etc.)
  + mlops_rakuten/modules/data_transformation.py définit le module de DataTransformation (TF-IDF et train / test split, sauvegarde des artifacts)
  + mlops_rakuten/modules/model_trainer.py définit le module de ModelTrainer (Linear SVC, sauvegarde des artifacts)
  + mlops_rakuten/modules/model_evaluation.py définit le module de ModelEvaluation (metrics et matrice de confusion)

### Step 4: Étapes du Pipeline
- mlops_rakuten/pipelines/ définit les pipelines qui seront instanciés et exécutés:
  + mlops_rakuten/pipelines/data_seeding.py
  + mlops_rakuten/pipelines/data_ingestion.py
  + mlops_rakuten/pipelines/data_preprocessing.py
  + mlops_rakuten/pipelines/data_transformation.py
  + mlops_rakuten/pipelines/model_trainer.py
  + mlops_rakuten/pipelines/model_evaluation.py

### Step 5: Exécution de la Pipeline complète
- mlops_rakuten/main.py permet d'exécuter l'ensemble de la Pipeline.

---

## Données requises

### Exécution via Docker

Pour pouvoir entraîner un modèle, le fichier suivant doit exister **dans le volume Docker** :

* `/app/data/interim/rakuten_train.csv`

Ce fichier est présent **en local** dans le dépôt, à l’emplacement :

* `data/interim/rakuten_train.csv`

Il n’est **pas copié automatiquement** au démarrage des conteneurs.
L’injection dans le volume Docker est **volontairement explicite**, afin de rester compatible avec une future intégration DVC / Dagshub.

> À terme, cette étape sera remplacée par un `dvc pull`.

---

## Lancer l’application avec Docker

### 1. Démarrer la stack complète

```bash
make docker-up
```

Vérifier que les conteneurs sont bien lancés :

```bash
make docker-ps
```

---

### 2. Injecter le fichier d’entraînement dans le volume Docker

```bash
make docker-cp-traincsv
```

Cette commande :

* copie `data/interim/rakuten_train.csv` (local)
* vers `/app/data/interim/rakuten_train.csv` dans le volume Docker

👉 **Étape obligatoire avant le premier entraînement**.

---

### 3. Accéder à Swagger

```bash
make swagger
```

Puis ouvrir dans le navigateur :

* [https://localhost/docs](https://localhost/docs)

---

## Tester l’application (Swagger)

### 1. Authentification

* Endpoint : `POST /token`
* Fournir un `username` et un `password`
* Récupérer le `access_token`

Cliquer ensuite sur **Authorize** et renseigner :

```
Bearer <access_token>
```

---

### 2. Entraîner un modèle

* Endpoint : `POST /train`

Comportement attendu :

* création d’un répertoire `/app/data/processed/<timestamp>/`
* entraînement du modèle
* sauvegarde du modèle dans :

```
/app/models/<timestamp>/text_classifier.pkl
```

---

### 3. Vérifier l’état du modèle

* Endpoint : `GET /info`

Retourne notamment :

* si un modèle est disponible (`ready`)
* le chemin du modèle utilisé
* le dernier jeu de données traité

---

### 4. Faire une prédiction

* Endpoint : `POST /predict`

Payload attendu :

```json
{
  "designation": "Très joli pull pour enfants",
  "top_k": 3
}
```

---

## Tests en ligne de commande (curl)

> L’option `-k` est nécessaire en cas de certificat TLS auto-signé.

### Récupérer un token

```bash
curl -k -X POST https://localhost/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=julien&password=admin123"
```

---

### Lancer un entraînement

```bash
curl -k -X POST https://localhost/train \
  -H "Authorization: Bearer <TOKEN>"
```

---

### Informations sur le modèle

```bash
curl -k https://localhost/info \
  -H "Authorization: Bearer <TOKEN>"
```

---

### Prédiction

```bash
curl -k -X POST https://localhost/predict \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"designation":"Très joli pull pour enfants","top_k":3}'
```

---

## Nginx / TLS

Pour générer un certificat auto-signé (exemple avec `mkcert`) :

```bash
mkcert -key-file deployments/certs/nginx.key \
      -cert-file deployments/certs/nginx.crt \
      localhost 127.0.0.1 ::1
```

---

## Commandes Makefile (Docker)

Commandes principales :

* `make docker-up`
  Build et démarre l’ensemble des services

* `make docker-down`
  Arrête les services (volumes conservés)

* `make docker-down-v`
  Arrête les services **et supprime les volumes** (⚠️ destructif)

* `make docker-cp-traincsv`
  Injecte `rakuten_train.csv` dans le volume Docker

* `make docker-logs`
  Affiche les logs des conteneurs

* `make swagger`
  Ouvre Swagger dans le navigateur

---

## Mots de passe

* `jane` : `password`
* `john` : `password`
* `julien` : `admin123`
* `claudia` : `admin456`
* `samuel` : `admin789`
