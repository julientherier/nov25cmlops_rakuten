from __future__ import annotations
from loguru import logger

from pathlib import Path
import shutil
from typing import Any, Dict

from fastapi import FastAPI, File, HTTPException, UploadFile, status
import docker

from mlops_rakuten.config.constants import (
    UPLOADS_DATA_DIR,
)

DVC_RUNNER_CONTAINER = "rakuten-dvc-runner"

from mlops_rakuten.pipelines.data_ingestion import DataIngestionPipeline
from mlops_rakuten.pipelines.data_seeding import DataSeedingPipeline
from mlops_rakuten.utils import create_directories

app = FastAPI(title="Rakuten Ingest API", version="1.0.0")

# Initialisation du client Docker
docker_client = docker.from_env()

# Fonction pour exécuter des commandes DVC dans le conteneur dédié
def dvc_runner(cmd: str) -> str:
    """Exécute une commande DVC dans le conteneur DVC dédié et retourne la sortie."""
    try:
        container = docker_client.containers.get(DVC_RUNNER_CONTAINER)
        
        # Exécute la commande
        exit_code, output = container.exec_run(
            f"bash -c 'cd /app && {cmd}'",
            stream=False  # Attends la fin
        )
        
        output_str = output.decode('utf-8')
        for line in output_str.split('\n'):
            if not line.strip():
                continue
            if 'ERROR' in line:
                logger.error(line)
            elif 'SUCCESS' in line:
                logger.success(line)
            elif 'WARNING' in line:
                logger.warning(line)
            else:
                logger.info(line)
        
        if exit_code != 0:
            raise RuntimeError(f"DVC echoue avec code de sortie {exit_code}")
        
        logger.info(f"{cmd} terminé avec succès")
        return output_str
    
    except docker.errors.NotFound:
        logger.error(f"Container {DVC_RUNNER_CONTAINER} non trouvé")
        raise HTTPException(status_code=503, detail="DVC runner non disponible")
    except Exception as e:
        logger.error(f"Docker error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.post("/ingest")
async def ingest_csv(file: UploadFile = File(...)) -> Dict[str, Any]:
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(
            status_code=400, detail="Le fichier doit être un .csv")

    create_directories([UPLOADS_DATA_DIR])

    uploads_path = Path(UPLOADS_DATA_DIR) / file.filename
    with uploads_path.open("wb") as f:
        shutil.copyfileobj(file.file, f)

    try:
        ingested_dataset_path = DataIngestionPipeline().run(uploaded_csv_path=uploads_path)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Ingestion failed: {e}"
        ) from e

    return {"status": "ingested", "dataset_path": str(ingested_dataset_path)}


@app.post("/init")
def init_dataset() -> Dict[str, Any]:
    """
    Initialise le dataset.
    Déclenche le seeding DVC et tracke le dataset résultat du stage seeding.
    """
    try:
        logger.info("Initialisation du dataset rakuten via le seeding")
        
        # Pull les données brutes nécessaires, possible grace au remote DVC/Dagshub et au pointeur .dvc
        logger.info("Pulling raw data...")
        dvc_runner("dvc pull data/raw/rakuten/X_train_update.csv data/raw/rakuten/Y_train_CVw08PX.csv data/raw/product_categories.csv")
        
        # Exécute la stage seed, on force pour être sûr de l'exécuter si l'on veut aussi re-initialiser
        logger.info("Running seed stage...")
        dvc_runner("dvc repro seed --force")

        # Track de rakuten_train.csv, il faut ajouter ce fichier sur le host pour qu'il soit tracké via git commit et push
        logger.info("Tracking rakuten_train with DVC...")
        dvc_runner("dvc add data/interim/rakuten_train.csv")
        
        # Push kes changements vers le remote DVC et Dagshub, reste à faire le git commit + git push sur le host
        logger.info("Pushing to DVC remote...")
        dvc_runner("dvc push")
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    return {
        "status": "initialisation",
        "message": "Seed CSV ingéré et tracké avec succès."
    }