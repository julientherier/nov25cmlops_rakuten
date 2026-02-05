FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl git \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# deps
COPY pyproject.toml README.md /app/
COPY mlops_rakuten /app/mlops_rakuten
COPY requirements.txt /app/requirements.txt
RUN pip install --upgrade pip && pip install -r requirements.txt

EXPOSE 8000

# Commande surchargée par docker-compose pour chaque service
CMD ["uvicorn", "mlops_rakuten.services.predict_app:app", "--host", "0.0.0.0", "--port", "8000"]