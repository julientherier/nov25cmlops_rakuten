from __future__ import annotations

from pathlib import Path
import shutil
from typing import Any, Dict

from fastapi import FastAPI, File, HTTPException, UploadFile, status

from mlops_rakuten.config.constants import (
    INTERIM_DATA_DIR,
    PROCESSED_DATA_DIR,
    RAW_DATA_DIR,
    UPLOADS_DATA_DIR,
)
from mlops_rakuten.pipelines.data_ingestion import DataIngestionPipeline
from mlops_rakuten.pipelines.data_seeding import DataSeedingPipeline
from mlops_rakuten.utils import create_directories

app = FastAPI(title="Rakuten Ingest API", version="1.0.0")


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

    # Append au dataset courant
    try:
        ingested_dataset_path = DataIngestionPipeline().run(uploaded_csv_path=uploads_path)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail=f"Ingestion failed: {e}") from e

    return {"status": "ingested", "dataset_path": str(ingested_dataset_path)}


@app.post("/init")
def init_dataset() -> Dict[str, Any]:
    # crée les dossiers attendus (au cas où)
    #    create_directories([RAW_DATA_DIR, INTERIM_DATA_DIR, PROCESSED_DATA_DIR])
    #
    #    try:
    #        out = DataSeedingPipeline().run()
    #    except FileNotFoundError as e:
    #        raise HTTPException(
    #            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
    #            detail=f"Init impossible: fichier source introuvable ({e})",
    #        ) from e
    #    except Exception as e:
    #        raise HTTPException(status_code=500, detail=f"Init failed: {e}") from e
    #
    #    return {"status": "initialized", "output": str(out)}
    return {"status": "Work-in-progress", "message": "Use DVC to copy /data/interim/rakuten_train.csv"}
