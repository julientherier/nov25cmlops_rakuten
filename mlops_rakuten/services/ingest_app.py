from __future__ import annotations
from loguru import logger

from pathlib import Path
import shutil
from typing import Any, Dict

from fastapi import FastAPI, File, HTTPException, UploadFile, status, Query
import docker

from mlops_rakuten.config.constants import (
    UPLOADS_DATA_DIR,
)

DVC_RUNNER_CONTAINER = "rakuten-dvc-runner"

from mlops_rakuten.pipelines.data_ingestion import DataIngestionPipeline
from mlops_rakuten.pipelines.data_seeding import DataSeedingPipeline
from mlops_rakuten.utils import create_directories
from mlops_rakuten.docker_utils import dvc_operation, sync_ingest_data

app = FastAPI(title="Rakuten Ingest API", version="1.0.0")

# Initialisation du client Docker
docker_client = docker.from_env()

@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.get("/status")
def pipeline_status() -> Dict[str, Any]:
    """
    Vérifie l'état actuel du pipeline DVC.
    
    **Retourne:**
    - `status`: "clean" (aucun changement) ou "dirty" (changements détectés)
    - `details`: Sortie de `dvc status` pour diagnostic
    """
    try:
        logger.info("Checking pipeline status...")
        result = dvc_operation("dvc status", return_output=True)
        
        is_clean = not result.strip()
        
        return {
            "status": "clean" if is_clean else "dirty",
            "pipeline_state": "All stages up-to-date" if is_clean else "Some stages need update",
            "dvc_status_output": result if result.strip() else "No changes detected",
            "timestamp": str(Path.cwd())
        }
    except Exception as e:
        logger.error(f"Status check failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to check pipeline status: {str(e)}"
        ) from e


@app.post("/init")
def init_dataset(
    force: bool = Query(
        False,
        description="Force la régénération complète du pipeline (ignore le cache DVC)",
        title="Force Rebuild"
    )
) -> Dict[str, Any]:
    """
    Initialise le dataset + Track + Sync with Git+DagsHub.
    
    **Modes de fonctionnement:**
    - `force=false` (défaut): Réutilise les données en cache si elles existent - plus rapide
    - `force=true`: Régénère tous les stages from scratch - force rebuild complet
    
    **Étapes exécutées:**
    1. Pull des données brutes via DVC
    2. Exécution du stage `seed` (génère rakuten_train.csv)
    3. Tracking du dataset avec DVC
    4. Synchronisation Git+DVC+DagsHub
    """
    try:
        mode_label = "FORCE REBUILD" if force else "Normal Init"
        logger.info(f"{mode_label} - Initialisation du dataset rakuten via le seeding")
        
        # Pull les données brutes
        logger.info("Pulling raw data from DVC remote...")
        dvc_operation("dvc pull 2>&1 || true")
        
        # Exécute la stage seed
        logger.info(f"Running seed stage {mode_label}...")
        seed_cmd = "dvc repro seed --force" if force else "dvc repro seed"
        dvc_operation(seed_cmd)

        # Track de rakuten_train.csv avec DVC
        logger.info("Tracking rakuten_train with DVC...")
        dvc_operation("dvc add data/interim/rakuten_train.csv")
        
        # ============================================================================
        # Git+DVC synchronization
        # ============================================================================
        logger.info("Starting Git+DVC synchronization...")
        
        sync_results = sync_ingest_data("rakuten_train.csv")
        
        if not sync_results["summary"]["success"]:
            logger.error(f"Sync had errors: {sync_results['errors']}")
            raise HTTPException(
                status_code=500,
                detail=f"Git+DVC sync failed: {sync_results['errors']}"
            )
        
        logger.success("Git+DVC synchronization complete!")
        
        return {
            "status": "initialisation_complete",
            "mode": "force_rebuild" if force else "normal",
            "message": "Seed CSV ingéré, tracké et synchro avec Git+DVC+DagsHub",
            "sync_details": sync_results["summary"],
            "pipeline_ready": True
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error during init: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/ingest")
async def ingest_csv(file: UploadFile = File(...)) -> Dict[str, Any]:
    """
    Ingest CSV + Track with DVC + Sync to Git+DagsHub.
    """
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(
            status_code=400, detail="Le fichier doit être un .csv")

    create_directories([UPLOADS_DATA_DIR])

    uploads_path = Path(UPLOADS_DATA_DIR) / file.filename
    with uploads_path.open("wb") as f:
        shutil.copyfileobj(file.file, f)

    try:
        logger.info(f"Ingesting CSV from {uploads_path}...")
        ingested_dataset_path = DataIngestionPipeline().run(uploaded_csv_path=uploads_path)
        logger.info(f"✓ Ingestion completed: {ingested_dataset_path}")
    except Exception as e:
        logger.error(f"Ingestion failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Ingestion failed: {e}"
        ) from e
    
    # ============================================================================
    # Synchroniser avec Git+DVC+DagsHub
    # ============================================================================
    try:
        logger.info("Starting Git+DVC synchronization...")
        
        # DVC operations
        dvc_operation("dvc add data/interim/rakuten_train.csv")
        
        # Git+DVC sync (handles commit + push)
        sync_results = sync_ingest_data(file.filename)
        
        if not sync_results["summary"]["success"]:
            logger.error(f"Sync had errors: {sync_results['errors']}")
            raise HTTPException(
                status_code=500,
                detail=f"Git+DVC sync failed: {sync_results['errors']}"
            )
        
        logger.success("Git+DVC synchronization complete!")
        
        return {
            "status": "ingested_and_synced",
            "dataset_path": str(ingested_dataset_path),
            "message": "Dataset ingéré, tracké et synchro avec Git+DVC+DagsHub",
            "sync_details": sync_results["summary"]
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Sync operation failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Git+DVC operation failed: {str(e)}"
        ) from e