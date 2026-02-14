FROM python:3.11-slim

# Installer dépendances système
RUN apt-get update && apt-get install -y \
    git \
    curl \
    openssh-client \
    && rm -rf /var/lib/apt/lists/*

# Installer DVC
RUN pip install --no-cache-dir dvc

WORKDIR /app

# Copier requirements
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Git config par défaut
RUN git config --global user.name "Rakuten MLOps" && \
    git config --global user.email "mlops@rakuten.local" && \
    git config --global core.fileMode false

# Simple entrypoint
CMD ["/bin/bash"]
