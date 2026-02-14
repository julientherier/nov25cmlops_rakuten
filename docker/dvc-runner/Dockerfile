FROM python:3.12-slim

WORKDIR /app

# Dépendances système
RUN apt-get update && apt-get install -y --no-install-recommends \
    git curl \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1

# Copier et installer
COPY . .
RUN pip install --upgrade pip && pip install -r requirements.txt

# Git config
RUN git config --global user.email "dvc@rakuten.local" && \
    git config --global user.name "DVC Runner"

    
CMD ["sleep", "infinity"]