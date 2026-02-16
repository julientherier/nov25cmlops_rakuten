from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException, status
from loguru import logger

from mlops_rakuten.pipelines.prediction import PredictionPipeline
from mlops_rakuten.services.schemas import (
    CategoryScore,
    PredictionRequest,
    PredictionResponse,
)

app = FastAPI(title="Rakuten Predict API", version="1.0.0")


class PredictionService:
    """
    Service de prédiction avec cache intégré.
    
    Utilise un attribut de classe pour cacher le pipeline.
    Évite l'utilisation de variables globales.
    """
    
    _pipeline: Optional[PredictionPipeline] = None
    
    @classmethod
    def get_pipeline(cls) -> PredictionPipeline:
        """
        Lazy load + cache le PredictionPipeline.
        
        Avantages:
        - Premier appel: charge le pipeline depuis MLflow
        - Appels suivants: utilise le cache (instantané)
        - Pas de variable globale
        """
        if cls._pipeline is None:
            logger.info("Initialisation du PredictionPipeline...")
            cls._pipeline = PredictionPipeline()
            logger.success("PredictionPipeline prêt (en cache)")
        
        return cls._pipeline
    
    @classmethod
    def predict(cls, texts: list[str], top_k: int | None = None) -> list:
        """Prédiction avec pipeline en cache"""
        pipeline = cls.get_pipeline()
        return pipeline.run(texts=texts, top_k=top_k)
    
    @classmethod
    def get_model_info(cls) -> Dict[str, Any]:
        """Infos modèle avec pipeline en cache"""
        pipeline = cls.get_pipeline()
        return pipeline.get_model_info()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/predict", response_model=PredictionResponse)
def predict(payload: PredictionRequest) -> PredictionResponse:
    """Prédiction via le service en cache"""
    results_per_text = PredictionService.predict(
        texts=[payload.designation], 
        top_k=payload.top_k
    )
    preds_raw = results_per_text[0]

    preds = [
        CategoryScore(
            prdtypecode=p["prdtypecode"],
            category_name=p.get("category_name"),
            proba=p["proba"],
        )
        for p in preds_raw
    ]

    return PredictionResponse(designation=payload.designation, predictions=preds)


@app.get("/info")
def model_info() -> Dict[str, Any]:
    """Infos du modèle en production"""
    info = PredictionService.get_model_info()
    
    if info and info.get("status") != "error":
        return {
            "status": "ok",
            "model": info,
            "cached": True
        }
    else:
        return {
            "status": "error",
            "message": "Pas de modèle en production",
            "error_details": info.get("error") if info else None
        }