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

from mlops_rakuten.utils.sync_core import sync_git_dvc


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

def sync_ingest_data(uploaded_filename: str) -> dict[str, Any]:
    """
    Après une ingestion via API Docker, synchronise rakuten_train.csv.

    Usage dans ingest_app.py :
        sync_ingest_data("rakuten_batch_0005.csv")
    """
    logger.info(f"[Ingest] Sync post-ingestion : {uploaded_filename}")

    return sync_git_dvc(
        run_dvc=_dvc,
        run_git=_git,
        commit_prefix="Docker-in-Docker:ingest",
        commit_message=f"batch={uploaded_filename}",
        git_paths=[
            "data/interim/rakuten_train.csv.dvc",
            "dvc.lock",
            ".dvc/",
        ],
        dvc_files=["data/interim/rakuten_train.csv"],
        push=True,
    )


def _read_train_metadata(model_dir: Path) -> dict:
    metadata_path = model_dir / "mlflow_run_metadata.json"
    if not metadata_path.exists():
        return {"run_id": "unknown", "version": "?"}
    with open(metadata_path) as f:
        data = json.load(f)
    return {
        "run_id": data.get("run_id", "unknown")[:7],
        "version": data.get("model_version", "?"),
    }

def _read_val_f1(metrics_path: Path) -> str:
    if not metrics_path.exists():
        return "?"
    with open(metrics_path) as f:
        return str(round(json.load(f).get("val_f1_macro", 0), 4))


def sync_training_results() -> dict[str, Any]:
    """Docker-in-Docker : lit les artefacts via config puis sync."""
    config      = ConfigurationManager()
    model_dir   = Path(config.get_model_trainer_config().model_dir)
    metrics_path = Path(config.get_model_evaluation_config().metrics_path)

    meta = _read_train_metadata(model_dir)
    f1   = _read_val_f1(metrics_path)

    return sync_git_dvc(
        run_dvc=_dvc,
        run_git=_git,
        commit_prefix="Docker-in-Docker:train",   # DID = Docker-in-Docker
        commit_message=f"model v{meta['version']}, f1_macro={f1}, run_id={meta['run_id']}",
        git_paths=["mlops_rakuten/"],
        dvc_files=None,
        push=True,
    )

def sync_init(force: bool = False) -> dict[str, Any]:
    """Ajoute init manquant pour le mode Docker-in-Docker."""
    mode = "force-rebuild" if force else "normal"
    return sync_git_dvc(
        run_dvc=_dvc,
        run_git=_git,
        commit_prefix="Docker-in-Docker:init",
        commit_message=f"seed dataset [{mode}]",
        git_paths=["data/interim/rakuten_train.csv.dvc", "dvc.lock", ".dvc/"],
        dvc_files=["data/interim/rakuten_train.csv"],
        push=True,
    )