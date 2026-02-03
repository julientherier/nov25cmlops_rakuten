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


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.post("/train")
def train() -> Dict[str, Any]:
    try:
        logger.info("Starting Pipeline...")

        # Pull latest data and code from DagsHub
        logger.info("Pulling from DVC remote...")
        dvc_runner("dvc pull 2>&1 || true")
        
        #DVC repro exécute tous les stages depuis le preprocess, si rakuten train a changé, tout sera relancé depuis le preprocess
        logger.info("Running DVC pipeline...")
        dvc_runner("dvc repro")
        
        # Push outputs vers DagsHub
        logger.info("Pushing to DVC remote...")
        dvc_runner("dvc push")
        
        return {
            "status": "complete",
            "stages": ["preprocess", "transform", "train", "evaluate"],
            "message": "All stages executed successfully",
            "next_steps": [
                "Commit and push changes to Git:",
                "git add dvc.lock",
                "git commit -m 'Training pipeline complete'",
                "git push"
            ]
        }
        
    except RuntimeError as e:
        logger.error(f"DVC pipeline failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        raise HTTPException(status_code=500, detail=str(e))