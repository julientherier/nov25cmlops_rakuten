from __future__ import annotations

import json
from pathlib import Path

from loguru import logger
import typer

from mlops_rakuten.pipelines.data_ingestion import DataIngestionPipeline
from mlops_rakuten.config.config_manager import ConfigurationManager
from mlops_rakuten.pipelines.prediction import PredictionPipeline
from mlops_rakuten.utils.cli import (
    _dvc,               
    sync_init,
    sync_ingest_data,
    sync_training_results,
)

app = typer.Typer()


# ─────────────────────────────────────────────────────────────────────────────
# Helpers locaux (lecture de fichiers uniquement, pas de transport)
# ─────────────────────────────────────────────────────────────────────────────

def _read_train_metadata(model_dir: Path) -> dict:
    """Lit mlflow_run_metadata.json → run_id (7 chars) et version."""
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
    """Lit val_f1_macro depuis le fichier de métriques."""
    if not metrics_path.exists():
        return "?"
    with open(metrics_path) as f:
        return str(round(json.load(f).get("val_f1_macro", 0), 4))


def _check_sync(results: dict, step: str) -> None:
    """Lève une erreur Typer si la sync a échoué."""
    if not results["summary"]["success"]:
        logger.error(f"[{step}] Sync failed : {results['errors']}")
        raise typer.Exit(code=1)


# ─────────────────────────────────────────────────────────────────────────────
# Commands
# ─────────────────────────────────────────────────────────────────────────────

@app.command()
def init(
    force: bool = typer.Option(
        False, "--force", "-f",
        help="Force la régénération complète (ignore le cache DVC)",
    )
) -> None:
    """
    Initialise le dataset depuis DagsHub via le stage seed DVC.

    Workflow :
      1. dvc pull         → récupère raw + interim depuis DagsHub S3
      2. dvc repro seed   → génère data/interim/rakuten_train.csv
      3. sync_init()      → dvc add + dvc push + git commit CLI:init

    À exécuter une seule fois au démarrage, ou avec --force pour repartir
    d'un état propre.
    """
    mode = "force-rebuild" if force else "normal"
    logger.info(f"Init dataset [{mode}]")

    _dvc("dvc pull 2>&1 || true")
    _dvc("dvc repro seed --force" if force else "dvc repro seed")

    results = sync_init(force=force)
    _check_sync(results, "init")

    logger.success("Init terminé — prêt pour `ingest` ou `train`.")


@app.command()
def ingest(
    uploaded_csv_path: str = typer.Argument(..., help="Chemin vers le CSV à ingérer")
) -> None:
    """
    Ingère un nouveau batch CSV dans le dataset et synchronise.

    Workflow :
      1. DataIngestionPipeline  → fusionne le CSV dans rakuten_train.csv
      2. dvc repro preprocess   → propage le changement, met à jour dvc.lock
      3. sync_ingest_data()     → dvc add + dvc push + git commit CLI:ingest

    Ne déclenche PAS l'entraînement. Lancer `train` ensuite.
    """
    csv_path = Path(uploaded_csv_path)
    if not csv_path.exists():
        logger.error(f"Fichier introuvable : {csv_path}")
        raise typer.Exit(code=1)
    if csv_path.suffix.lower() != ".csv":
        logger.error("Le fichier doit être un .csv")
        raise typer.Exit(code=1)

    logger.info(f"Ingestion de {csv_path.name}...")
    ingested_path = DataIngestionPipeline().run(uploaded_csv_path=csv_path)
    logger.success(f"Dataset mis à jour : {ingested_path}")

    _dvc("dvc repro preprocess")

    results = sync_ingest_data(csv_path.name)
    _check_sync(results, "ingest")

    logger.success("Ingestion terminée — lancer `train` pour réentraîner.")

@app.command()
def train() -> None:
    logger.info("Lancement du pipeline d'entraînement")

    _dvc("dvc pull")
    _dvc("dvc repro")
    _dvc("dvc push")

    config = ConfigurationManager()
    model_path   = Path(config.get_model_trainer_config().model_path)
    metrics_path = Path(config.get_model_evaluation_config().metrics_path)

    meta = _read_train_metadata(model_path.parent)
    f1   = _read_val_f1(metrics_path)

    results = sync_training_results(
        model_version=meta["version"],
        f1=f1,
        run_id=meta["run_id"],
    )
    _check_sync(results, "train")

    logger.success(f"Training terminé — modèle v{meta['version']}, f1={f1}, run_id={meta['run_id']}")


@app.command()
def predict(
    text: str = typer.Argument(..., help="Texte produit à classifier"),
    top_k: int = typer.Option(10, "--top-k", "-k", help="Nombre de catégories à retourner"),
) -> None:
    """
    Inférence depuis le modèle @production MLflow.

    PredictionPipeline → Prediction._load_artifacts() charge automatiquement
    modèle + vectorizer + label encoder + mapping depuis MLflow @production.
    Fallback local si MLflow est indisponible.

    Exemple :
        python -m mlops_rakuten.main predict "Super aspirateur sans fil" --top-k 3
    """
    logger.info("Chargement des artefacts depuis MLflow (@production)...")
    pipeline = PredictionPipeline()

    logger.info(f"Inférence sur : {text!r}")
    results = pipeline.run(texts=[text], top_k=top_k)[0]

    for r in results:
        logger.success(f"  [{r['prdtypecode']}] {r['category_name']} : {r['proba'] * 100:.1f}%")


if __name__ == "__main__":
    app()