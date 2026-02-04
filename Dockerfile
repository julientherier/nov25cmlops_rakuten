FROM python:3.12-slim

# ============================================================================
# Environment Variables
# ============================================================================

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# ============================================================================
# System Dependencies
# ============================================================================

RUN apt-get update && apt-get install -y --no-install-recommends \
    docker.io \
    build-essential curl git \
    openssh-client \
    && rm -rf /var/lib/apt/lists/*

# ============================================================================
# Python Dependencies
# ============================================================================

WORKDIR /app

COPY pyproject.toml README.md requirements.txt /app/
COPY mlops_rakuten /app/mlops_rakuten

RUN pip install --upgrade pip && \
    pip install -r requirements.txt && \
    pip install docker dvc

# ============================================================================
# Copy Entrypoint Script (External File)
# ============================================================================

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# ============================================================================
# Configuration
# ============================================================================

EXPOSE 8000

ENTRYPOINT ["/entrypoint.sh"]

# Allow mounted git repos to work with any user
RUN git config --global --add safe.directory /app
CMD ["uvicorn", "mlops_rakuten.services.predict_app:app", "--host", "0.0.0.0", "--port", "8000"]
