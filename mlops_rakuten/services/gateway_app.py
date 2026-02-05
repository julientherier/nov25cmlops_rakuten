from __future__ import annotations

from typing import Any, Dict

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile, status
from fastapi.security import OAuth2PasswordRequestForm
import httpx

from mlops_rakuten.auth.auth_simple import (
    authenticate_user,
    create_access_token,
    require_admin,
    require_user,
)
from mlops_rakuten.services.schemas import PredictionRequest, PredictionResponse

app = FastAPI(title="Rakuten Gateway", version="1.0.0")

PREDICT_URL = "http://api-predict:8000"
INGEST_URL = "http://api-ingest:8000"
TRAIN_URL = "http://api-train:8000"


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.post("/token")
async def token(form_data: OAuth2PasswordRequestForm = Depends()):
    user = authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Identifiants invalides",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = create_access_token(
        username=user["username"], role=user["role"])
    return {"access_token": access_token, "token_type": "bearer"}


@app.post("/init")
async def proxy_init(_=Depends(require_admin)) -> Any:
    async with httpx.AsyncClient(timeout=600) as client:
        r = await client.post(f"{INGEST_URL}/init")
    if r.status_code >= 400:
        raise HTTPException(status_code=r.status_code, detail=r.text)
    return r.json()


@app.post("/ingest")
async def proxy_ingest(file: UploadFile = File(...), _=Depends(require_admin)) -> Any:
    files = {"file": (file.filename, await file.read(), file.content_type or "text/csv")}
    async with httpx.AsyncClient(timeout=300) as client:
        r = await client.post(f"{INGEST_URL}/ingest", files=files)
    if r.status_code >= 400:
        raise HTTPException(status_code=r.status_code, detail=r.text)
    return r.json()


@app.post("/train")
async def proxy_train(_=Depends(require_admin)) -> Any:
    async with httpx.AsyncClient(timeout=3600) as client:
        r = await client.post(f"{TRAIN_URL}/train")
    if r.status_code >= 400:
        raise HTTPException(status_code=r.status_code, detail=r.text)
    return r.json()


@app.get("/info")
async def proxy_info(_=Depends(require_user)):
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(f"{PREDICT_URL}/info")
    if r.status_code >= 400:
        raise HTTPException(status_code=r.status_code, detail=r.text)
    return r.json()


@app.post("/predict", response_model=PredictionResponse)
async def proxy_predict(payload: PredictionRequest, _=Depends(require_user)) -> PredictionResponse:
    data = payload.model_dump() if hasattr(
        payload, "model_dump") else payload.dict()

    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(f"{PREDICT_URL}/predict", json=data)

    if r.status_code >= 400:
        raise HTTPException(status_code=r.status_code, detail=r.text)

    return r.json()
