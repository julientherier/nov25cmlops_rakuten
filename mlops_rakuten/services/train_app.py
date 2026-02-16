from __future__ import annotations

from typing import Any, Dict

from fastapi import FastAPI, HTTPException
from loguru import logger
import docker


app = FastAPI(title="Rakuten Train API", version="1.0.0")
DVC_RUNNER_CONTAINER = "rakuten-dvc-runner"

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


def git_runner(cmd: str) -> str:
    """Exécute une commande Git dans le conteneur dédié et retourne la sortie."""
    try:
        container = docker_client.containers.get(DVC_RUNNER_CONTAINER)
        
        # Exécute la commande
        exit_code, output = container.exec_run(
            f"bash -c 'cd /app && {cmd}'",
            stream=False
        )
        
        output_str = output.decode('utf-8')
        for line in output_str.split('\n'):
            if not line.strip():
                continue
            if 'ERROR' in line or 'fatal' in line:
                logger.error(line)
            else:
                logger.info(line)
        
        if exit_code != 0:
            if exit_code == 1 and "nothing to commit" in output_str:  # Traiter exit code 1 + "nothing to commit" comme un succès silencieux :
                return output_str  # Pas une erreur
            raise RuntimeError(f"Git failed with exit code {exit_code}")
        
        logger.info(f"{cmd} completed successfully")
        return output_str
    
    except docker.errors.NotFound:
        logger.error(f"Container {DVC_RUNNER_CONTAINER} not found")
        raise HTTPException(status_code=503, detail="Git runner not available")
    except Exception as e:
        logger.error(f"Docker error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def sync_training_results() -> Dict[str, Any]:
    """
    Sync training results to Git and DVC remotes.
    
    Steps:
    1. DVC push (push models + metrics to DagsHub)
    2. Git add (stage dvc.lock)
    3. Git commit (commit training results)
    4. Git push (push to GitHub)
    """
    try:
        logger.info("[Sync] Starting Git+DVC synchronization...")
        
        # Step 1: Push to DVC remote
        logger.info("[Sync] Step 1: Pushing to DVC remote...")
        dvc_runner("dvc push")
        
        # Step 2: Stage DVC files
        logger.info("[Sync] Step 2: Staging files with Git...")
        git_runner("git add dvc.lock")
        
        # Step 3: Commit
        logger.info("[Sync] Step 3: Committing with message...")
        commit_msg = "training: Model training pipeline complete"
        commit_output = git_runner(f'git commit -m "{commit_msg}"')
        
        nothing_to_commit = any(
            msg in commit_output
            for msg in ["nothing to commit", "nothing added to commit"]
        )

        if nothing_to_commit:
            logger.info("[Sync] Nothing new to commit (dvc.lock unchanged) — skipping git push")
            return {
                "status": "synced",
                "dvc_push": "✓",
                "git_commit": "skipped (nothing to commit)",
                "git_push": "skipped (no new commit)"
            }

        
        # Step 4: Push to GitHub
        logger.info("[Sync] Step 4: Pushing to GitHub...")
        # Get current branch
        branch = git_runner("git rev-parse --abbrev-ref HEAD").strip()
        git_runner(f"git push myfork {branch}")
        
        logger.success("[Sync] ✓ All files synced to Git and DVC!")
        
        return {
            "status": "synced",
            "dvc_push": "✓",
            "git_commit": "✓",
            "git_push": "✓"
        }
    
    except RuntimeError as e:
        logger.error(f"[Sync] Failed: {e}")
        return {
            "status": "error",
            "error": str(e)
        }
    except Exception as e:
        logger.error(f"[Sync] Unexpected error: {e}")
        return {
            "status": "error",
            "error": str(e)
        }


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.post("/train")
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
        logger.info("🚀 Starting Training Pipeline...")
        logger.info("=" * 80)

        # Step 1: Reset to dvc.lock state (safe path)
        # Since /init or /ingest already synchronized dvc.lock, this is always safe
        logger.info("Step 1: Resetting to dvc.lock state...")
        dvc_runner("dvc checkout")
        
        # Step 2: Download missing data (no conflicts expected)
        logger.info("Step 2: Pulling latest data from DVC remote...")
        dvc_runner("dvc pull")
        
        # Step 3: Run DVC pipeline
        # Only reruns stages that changed since /init or /ingest
        logger.info("Step 3: Running DVC pipeline (preprocess → transform → train → evaluate)...")
        dvc_runner("dvc repro")
        
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