"""
git_sync_utils.py - Synchronisation Git+DVC pour les APIs Rakuten

Utilise git-runner pour synchroniser les changements DVC avec Git+DagsHub
"""

from __future__ import annotations
from loguru import logger
from typing import Dict, Any
import docker
import subprocess

GIT_RUNNER_CONTAINER = "rakuten-git-runner"
DVC_RUNNER_CONTAINER = "rakuten-dvc-runner"

docker_client = docker.from_env()


def dvc_operation(cmd: str) -> str:
    """Exécute une commande DVC dans le conteneur dvc-runner."""
    logger.info(f"[DVC] Executing: {cmd}")
    
    try:
        container = docker_client.containers.get(DVC_RUNNER_CONTAINER)
        exit_code, output = container.exec_run(
            f"bash -c 'cd /app && {cmd}'",
            stream=False,
            demux=False
        )
        
        output_str = output.decode('utf-8') if output else ""
        
        if output_str.strip():
            for line in output_str.split('\n'):
                if line.strip():
                    logger.info(f"   {line}")
        
        if exit_code != 0:
            logger.error(f"[DVC] FAILED with exit code {exit_code}")
            raise RuntimeError(f"DVC failed: {output_str}")
        
        logger.success(f"[DVC] {cmd}")
        return output_str
    
    except docker.errors.NotFound:
        logger.error(f"[DVC] Container {DVC_RUNNER_CONTAINER} not found")
        raise RuntimeError(f"Container {DVC_RUNNER_CONTAINER} not available")
    except Exception as e:
        logger.error(f"[DVC] Error: {e}")
        raise


def git_operation(cmd: str) -> str:
    """Exécute une commande Git dans le conteneur git-runner."""
    logger.info(f"[Git] Executing: {cmd}")
    
    try:
        container = docker_client.containers.get(GIT_RUNNER_CONTAINER)
        exit_code, output = container.exec_run(
            f"bash -c 'cd /app && {cmd}'",
            stream=False,
            demux=False
        )
        
        output_str = output.decode('utf-8') if output else ""
        
        if output_str.strip():
            for line in output_str.split('\n'):
                if line.strip():
                    logger.info(f"   {line}")
        
        if exit_code != 0:
            logger.error(f"[Git] FAILED with exit code {exit_code}")
            raise RuntimeError(f"Git failed: {output_str}")
        
        logger.success(f"[Git] {cmd}")
        return output_str
    
    except docker.errors.NotFound:
        logger.error(f"[Git] Container {GIT_RUNNER_CONTAINER} not found")
        raise RuntimeError(f"Container {GIT_RUNNER_CONTAINER} not available")
    except Exception as e:
        logger.error(f"[Git] Error: {e}")
        raise


def sync_git_dvc(
    files_to_add: list[str],
    commit_message: str,
    dvc_files: list[str] | None = None,
    push: bool = True
) -> Dict[str, Any]:
    """
    Synchronise les changements DVC avec Git et pousse vers DagsHub.
    
    Args:
        files_to_add: Fichiers/dossiers à tracker avec Git (ex: ["mlops_rakuten/"])
        commit_message: Message du commit Git
        dvc_files: Fichiers/dossiers à tracker avec DVC (ex: ["data/interim/rakuten_train.csv"])
        push: Si True, pousse vers Git et DVC remotes
    
    Returns:
        Dict avec status et messages
    
    Example:
        sync_git_dvc(
            files_to_add=["mlops_rakuten/"],
            commit_message="feat: Update model training",
            dvc_files=["data/processed/", "models/"],
            push=True
        )
    """
    results = {
        "dvc_operations": [],
        "git_operations": [],
        "errors": []
    }
    
    try:
        # ============================================================================
        # 1. DVC: Tracker les données
        # ============================================================================
        if dvc_files:
            logger.info(f"[Sync] Step 1: Adding {len(dvc_files)} items to DVC...")
            
            for dvc_file in dvc_files:
                try:
                    output = dvc_operation(f"dvc add {dvc_file}")
                    results["dvc_operations"].append({
                        "file": dvc_file,
                        "status": "success",
                        "output": output
                    })
                except Exception as e:
                    error_msg = f"Failed to add {dvc_file} to DVC: {str(e)}"
                    logger.error(error_msg)
                    results["errors"].append(error_msg)
        
        # ============================================================================
        # 2. GIT: Stage les fichiers Python + les .dvc files
        # ============================================================================
        logger.info(f"[Sync] Step 2: Staging files with Git...")
        
        # D'abord, stage les fichiers Python/config
        for file in files_to_add:
            try:
                output = git_operation(f"git add {file}")
                results["git_operations"].append({
                    "operation": f"add {file}",
                    "status": "success",
                    "output": output
                })
            except Exception as e:
                error_msg = f"Failed to git add {file}: {str(e)}"
                logger.error(error_msg)
                results["errors"].append(error_msg)
        
        # Ensuite, stage les .dvc files et .gitignore
        if dvc_files:
            try:
                output = git_operation("git add *.dvc .gitignore")
                results["git_operations"].append({
                    "operation": "add *.dvc .gitignore",
                    "status": "success",
                    "output": output
                })
            except Exception as e:
                error_msg = f"Failed to git add .dvc files: {str(e)}"
                logger.error(error_msg)
                results["errors"].append(error_msg)
        
        # ============================================================================
        # 3. GIT: Commit
        # ============================================================================
        logger.info(f"[Sync] Step 3: Committing with message: {commit_message}")
        
        try:
            output = git_operation(f'git commit -m "{commit_message}"')
            results["git_operations"].append({
                "operation": "commit",
                "status": "success",
                "message": commit_message,
                "output": output
            })
        except Exception as e:
            error_msg = str(e)
            
            # Si working tree est clean (nothing to commit), c'est normal, pas une erreur
            if "nothing to commit" in error_msg.lower() or "working tree clean" in error_msg.lower():
                logger.info(f"[Sync] No new changes to commit (working tree clean) - skipping")
                results["git_operations"].append({
                    "operation": "commit",
                    "status": "skipped",
                    "reason": "working tree clean - no changes",
                    "message": commit_message
                })
            else:
                # Sinon, c'est une vraie erreur
                logger.error(f"Failed to git commit: {error_msg}")
                results["errors"].append(f"Failed to git commit: {error_msg}")
        
        # ============================================================================
        # 4. PUSH: DVC push + Git push
        # ============================================================================
        if push:
            logger.info(f"[Sync] Step 4: Pushing to remotes...")
            
            # DVC push
            if dvc_files:
                try:
                    output = dvc_operation("dvc push -v")
                    results["dvc_operations"].append({
                        "operation": "push",
                        "status": "success",
                        "output": output
                    })
                except Exception as e:
                    error_msg = f"Failed DVC push: {str(e)}"
                    logger.error(error_msg)
                    results["errors"].append(error_msg)
            
            # Git push (s'il y a eu un commit)
            # Vérifier s'il y a un commit à pousser
            has_commit = any(
                op.get("operation") == "commit" and op.get("status") == "success"
                for op in results["git_operations"]
            )
            
            if has_commit:
                try:
                    # Récupérer la branche courante
                    branch = git_operation("git rev-parse --abbrev-ref HEAD").strip()
                    output = git_operation(f"git push myfork {branch}")
                    results["git_operations"].append({
                        "operation": "push",
                        "branch": branch,
                        "status": "success",
                        "output": output
                    })
                except Exception as e:
                    error_msg = f"Failed git push: {str(e)}"
                    logger.error(error_msg)
                    results["errors"].append(error_msg)
            else:
                logger.info("[Sync] No commits to push (skipping git push)")
                results["git_operations"].append({
                    "operation": "push",
                    "status": "skipped",
                    "reason": "no commits to push"
                })
        
        # ============================================================================
        # Summary
        # ============================================================================
        results["summary"] = {
            "total_dvc_ops": len(results["dvc_operations"]),
            "total_git_ops": len(results["git_operations"]),
            "total_errors": len(results["errors"]),
            "success": len(results["errors"]) == 0
        }
        
        return results
    
    except Exception as e:
        logger.error(f"[Sync] Unexpected error: {e}")
        results["errors"].append(str(e))
        results["summary"] = {
            "total_dvc_ops": len(results["dvc_operations"]),
            "total_git_ops": len(results["git_operations"]),
            "total_errors": len(results["errors"]),
            "success": False
        }
        return results


# ============================================================================
# Commandes spécialisées pour les APIs Rakuten
# ============================================================================

def sync_ingest_data(uploaded_filename: str) -> Dict[str, Any]:
    """
    Après l'ingestion, synchronise les données avec Git+DVC+DagsHub.
    
    Usage dans ingest_app.py:
        sync_ingest_data("rakuten_batch_0005.csv")
    """
    logger.info(f"[Ingest] Syncing ingested data: {uploaded_filename}")
    
    return sync_git_dvc(
        files_to_add=[],  # Pas de changement de code
        commit_message=f"data: Ingest {uploaded_filename}",
        dvc_files=["data/interim/rakuten_train.csv"],
        push=True
    )


def sync_training_results() -> Dict[str, Any]:
    """
    Après le training, synchronise les modèles et métriques.
    
    Usage dans train_app.py:
        sync_training_results()
    """
    logger.info("[Train] Syncing training results")
    
    return sync_git_dvc(
        files_to_add=["mlops_rakuten/"],  # Code changes
        commit_message="feat: Model training complete",
        dvc_files=[
            "data/processed/",
            "models/",
            "reports/"
        ],
        push=True
    )


def sync_prediction_results(batch_name: str) -> Dict[str, Any]:
    """
    Après les prédictions, synchronise les résultats.
    
    Usage dans predict_app.py:
        sync_prediction_results("batch_2024_01")
    """
    logger.info(f"[Predict] Syncing predictions: {batch_name}")
    
    return sync_git_dvc(
        files_to_add=[],
        commit_message=f"data: Predictions for {batch_name}",
        dvc_files=["reports/predictions/"],
        push=True
    )