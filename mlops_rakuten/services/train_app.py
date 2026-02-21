from __future__ import annotations

from typing import Any, Dict

from fastapi import FastAPI, HTTPException
from loguru import logger
import docker
from mlops_rakuten.utils.docker import sync_training_results,dvc_operation


app = FastAPI(title="Rakuten Train API", version="1.0.0")
DVC_RUNNER_CONTAINER = "rakuten-dvc-runner"

# Initialisation du client Docker
docker_client = docker.from_env()


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}



@app.post("/train")
def train() -> Dict[str, Any]:
    """
    Execute the full training pipeline.
    
    **Simplified workflow (dvc.lock is synchronized after /init or /ingest):**
    1. dvc checkout (revert to dvc.lock state - SAFE)
    2. dvc pull (download missing data - no conflicts)
    3. dvc repro (run all stages: preprocess → transform → train → evaluate)
       - Only reruns stages that actually changed
       - Fast! Because dvc.lock was updated by /init or /ingest
    4. Sync results to Git+DVC
    
    **Why is this fast?**
    - /init or /ingest already ran preprocess and updated dvc.lock
    - /train only reruns stages that changed since then
    - No unnecessary preprocess reruns
    """
    try:
        logger.info("=" * 80)
        logger.info("Starting Training Pipeline...")
        logger.info("=" * 80)

        # Step 1: Reset to dvc.lock state (safe path)
        # Since /init or /ingest already synchronized dvc.lock, this is always safe
        logger.info("Step 1: Resetting to dvc.lock state...")
        dvc_operation("dvc checkout")
        
        # Step 2: Download missing data (no conflicts expected)
        logger.info("Step 2: Pulling latest data from DVC remote...")
        dvc_operation("dvc pull")
        
        # Step 3: Run DVC pipeline
        # Only reruns stages that changed since /init or /ingest
        logger.info("Step 3: Running DVC pipeline (preprocess → transform → train → evaluate)...")
        dvc_operation("dvc repro")
        
        # Step 4: Sync results
        logger.info("Step 4: Syncing training results to Git and DVC...")
        sync_results = sync_training_results()
        
        if not sync_results["summary"]["success"]:
            logger.error(f"Sync failed: {sync_results['errors']}")
            return {
                "status": "training_complete_sync_failed",
                "stages": ["preprocess", "transform", "train", "evaluate"],
                "message": "Training succeeded but git+dvc sync failed",
                "sync_errors": sync_results["errors"],
                "manual_steps": [
                    "1. git add dvc.lock models/ reports/",
                    "2. git commit -m 'training: Model training pipeline complete'",
                    "3. git push origin <branch>"
                ]
            }
        
        logger.success("=" * 80)
        logger.success("Training Pipeline Complete!")
        logger.success("=" * 80)
        
        return {
            "status": "complete",
            "stages": ["transform", "train", "evaluate"],
            "message": "All stages executed and synced successfully ",
            "sync_summary": sync_results["summary"],
        }
        
    except RuntimeError as e:
        logger.error(f"DVC pipeline failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        raise HTTPException(status_code=500, detail=str(e))