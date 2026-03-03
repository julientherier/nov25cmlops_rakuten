from __future__ import annotations

"""
docker_utils.py — Version Docker de la synchronisation DVC + Git.

Transport : docker container.exec_run.
Utilise sync_core.sync_git_dvc() pour la logique commune.

Remplace l'ancien utils/docker.py.
"""

from typing import Any

import docker
from loguru import logger
from pathlib import Path

from mlops_rakuten.utils.sync_core import sync_git_dvc,read_training_artifacts


GIT_RUNNER_CONTAINER = "rakuten-git-runner"
DVC_RUNNER_CONTAINER = "rakuten-dvc-runner"

docker_client = docker.from_env()


# ─────────────────────────────────────────────────────────────────────────────
# Transport Docker
# ─────────────────────────────────────────────────────────────────────────────

def _dvc(cmd: str) -> str:
    """Exécute une commande DVC dans le container dvc-runner."""
    logger.info(f"[DVC] {cmd}")
    try:
        container = docker_client.containers.get(DVC_RUNNER_CONTAINER)
        exit_code, output = container.exec_run(
            f"bash -c 'cd /app && {cmd}'",
            stream=False,
            demux=False,
        )
        output_str = output.decode("utf-8") if output else ""
        if output_str.strip():
            for line in output_str.strip().split("\n"):
                logger.debug(f"   {line}")
        if exit_code != 0:
            logger.error(f"[DVC] FAILED exit_code={exit_code}")
            raise RuntimeError(f"DVC failed: {output_str}")
        logger.success(f"[DVC] {cmd}")
        return output_str
    except docker.errors.NotFound:
        raise RuntimeError(f"Container {DVC_RUNNER_CONTAINER} introuvable")
    except Exception as e:
        logger.error(f"[DVC] Error: {e}")
        raise


def _git(cmd: str) -> str:
    """Exécute une commande Git dans le container git-runner."""
    logger.info(f"[Git] {cmd}")
    try:
        container = docker_client.containers.get(GIT_RUNNER_CONTAINER)
        exit_code, output = container.exec_run(
            f"bash -c 'cd /app && {cmd}'",
            stream=False,
            demux=False,
        )
        output_str = output.decode("utf-8") if output else ""
        if output_str.strip():
            for line in output_str.strip().split("\n"):
                logger.debug(f"   {line}")
        if exit_code != 0:
            logger.error(f"[Git] FAILED exit_code={exit_code}")
            raise RuntimeError(f"Git failed: {output_str}")
        logger.success(f"[Git] {cmd}")
        return output_str
    except docker.errors.NotFound:
        raise RuntimeError(f"Container {GIT_RUNNER_CONTAINER} introuvable")
    except Exception as e:
        logger.error(f"[Git] Error: {e}")
        raise


# ─────────────────────────────────────────────────────────────────────────────
# Commandes spécialisées — même interface que sync_utils
# ─────────────────────────────────────────────────────────────────────────────

def sync_ingest_data(
    uploaded_filename: str,
    mode: str | None = None,
) -> dict[str, Any]:
    prefix = mode or "Docker-in-Docker"
    logger.info(f"[Ingest] Sync post-ingestion : {uploaded_filename} [{prefix}]")

    return sync_git_dvc(
        run_dvc=_dvc,
        run_git=_git,
        commit_prefix=f"{prefix}:ingest",
        commit_message=f"batch={Path(uploaded_filename).stem}",
        git_paths=[
            "data/interim/rakuten_train.csv.dvc",
            "dvc.lock",
            ".dvc/",
        ],
        dvc_files=["data/interim/rakuten_train.csv"],
        push=True,
    )


def sync_training_results(mode: str | None = None) -> dict[str, Any]:
    
    artifacts = read_training_artifacts()
    prefix = mode or "Docker-in-Docker"  

    return sync_git_dvc(
        run_dvc=_dvc,
        run_git=_git,
        commit_prefix=f"{prefix}:train",
        commit_message=f"model v{artifacts['version']}, f1_macro={artifacts['f1']}, run_id={artifacts['run_id']}",
        git_paths=["mlops_rakuten/"],
        dvc_files=None,
        push=True,
    )

def sync_init(
    force: bool = False,
    mode: str | None = None,
) -> dict[str, Any]:
    prefix = mode or "Docker-in-Docker"
    label = "force-rebuild" if force else "normal"
    logger.info(f"[Init] Sync post-seed [{label}] [{prefix}]")

    return sync_git_dvc(
        run_dvc=_dvc,
        run_git=_git,
        commit_prefix=f"{prefix}:init",
        commit_message=f"seed dataset [{label}]",
        git_paths=[
            "data/interim/rakuten_train.csv.dvc",
            "dvc.lock",
            ".dvc/",
        ],
        dvc_files=["data/interim/rakuten_train.csv"],
        push=True,
    )