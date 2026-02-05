from __future__ import annotations

from typing import Any, Dict

from fastapi import FastAPI

from mlops_rakuten.pipelines.data_preprocessing import DataPreprocessingPipeline
from mlops_rakuten.pipelines.data_transformation import DataTransformationPipeline
from mlops_rakuten.pipelines.model_evaluation import ModelEvaluationPipeline
from mlops_rakuten.pipelines.model_trainer import ModelTrainerPipeline

app = FastAPI(title="Rakuten Train API", version="1.0.0")


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.post("/train")
def train() -> Dict[str, Any]:
    # chaîne training (dataset déjà présent via volume)
    preprocessing_path = DataPreprocessingPipeline().run()
    transformation_path = DataTransformationPipeline().run()
    model_path = ModelTrainerPipeline().run()
    eval_report = ModelEvaluationPipeline().run()

    return {
        "status": "trained",
        "preprocessing_path": str(preprocessing_path),
        "transformation_path": str(transformation_path),
        "model_path": str(model_path),
        "evaluation_report": str(eval_report),
    }
