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

# initialisaiton de git et dvc dans le container : identifiants par defaut pour le moment, a personnaliuser si besoin de git push de facon automatique.
RUN git init && \
    git config user.email "dvc@container.local" && \
    git config user.name "DVC Container" && \
    dvc init

# script d'initialisation dvc-dagshub
COPY docker/api-service/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/app/entrypoint.sh"]
# Commande surchargée par docker-compose pour chaque service
CMD ["uvicorn", "mlops_rakuten.services.predict_app:app", "--host", "0.0.0.0", "--port", "8000"]