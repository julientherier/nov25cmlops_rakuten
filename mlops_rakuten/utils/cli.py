from __future__ import annotations

"""
Version CLI de la synchronisation DVC + Git.

Transport : subprocess (commandes locales).
Utilise sync_core.sync_git_dvc() pour la logique commune.
"""

import subprocess
from pathlib import Path
from typing import Any

from loguru import logger

from mlops_rakuten.utils.sync_core import sync_git_dvc


# ─────────────────────────────────────────────────────────────────────────────
# Transport local
# ─────────────────────────────────────────────────────────────────────────────

def _dvc(cmd: str) -> str:
    """Exécute une commande DVC en local."""
    logger.info(f"[DVC] {cmd}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.stdout.strip():
        for line in result.stdout.strip().split("\n"):
            logger.debug(f"   {line}")
    if result.returncode != 0:
        logger.error(result.stderr.strip())
        raise RuntimeError(f"DVC failed: {result.stderr.strip()}")
    return result.stdout


def _git(cmd: str) -> str:
    """Exécute une commande Git en local."""
    logger.info(f"[Git] {cmd}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        logger.error(result.stderr.strip())
        raise RuntimeError(f"Git failed: {result.stderr.strip()}")
    return result.stdout


# ─────────────────────────────────────────────────────────────────────────────
# Commandes spécialisées — même interface que docker_utils
# ─────────────────────────────────────────────────────────────────────────────

def sync_ingest_data(uploaded_filename: str) -> dict[str, Any]:
    """
    Après une ingestion CLI, synchronise rakuten_train.csv avec DVC + Git.

    Usage dans main.py :
        sync_ingest_data("rakuten_batch_007.csv")
    """
    logger.info(f"[Ingest] Sync post-ingestion : {uploaded_filename}")

    return sync_git_dvc(
        run_dvc=_dvc,
        run_git=_git,
        commit_prefix="CLI:ingest",
        commit_message=f"batch={Path(uploaded_filename).stem}",
        git_paths=[
            "data/interim/rakuten_train.csv.dvc",
            "dvc.lock",
            ".dvc/",
        ],
        dvc_files=["data/interim/rakuten_train.csv"],
        push=True,
    )


def sync_training_results(model_version: str, f1: str, run_id: str) -> dict[str, Any]:
    """
    Après un entraînement CLI, synchronise dvc.lock et mlflow_run_metadata.

    Usage dans main.py :
        sync_training_results(model_version="3", f1="0.821", run_id="d4e9a1b")
    """
    logger.info("[Train] Sync post-entraînement")

    return sync_git_dvc(
        run_dvc=_dvc,
        run_git=_git,
        commit_prefix="CLI:train",
        commit_message=f"model v{model_version}, f1_macro={f1}, run_id={run_id}",
        git_paths=["mlops_rakuten/"],
        dvc_files=None,
        push=True,
    )


def sync_init(force: bool = False) -> dict[str, Any]:
    """
    Après un seed CLI, synchronise rakuten_train.csv avec DVC + Git.

    Usage dans main.py :
        sync_init(force=True)
    """
    mode = "force-rebuild" if force else "normal"
    logger.info(f"[Init] Sync post-seed [{mode}]")

    return sync_git_dvc(
        run_dvc=_dvc,
        run_git=_git,
        commit_prefix="CLI:init",
        commit_message=f"seed dataset [{mode}]",
        git_paths=[
            "data/interim/rakuten_train.csv.dvc",
            "dvc.lock",
            ".dvc/",
        ],
        dvc_files=["data/interim/rakuten_train.csv"],
        push=True,
    )