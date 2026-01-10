#!/bin/bash
set -e

# Check si la remote existe déjà
if ! dvc remote list | grep -q "^origin"; then
    echo "Ajout de Dagshub s3 remote..."
    dvc init --no-scm
    dvc remote add -d origin "s3://dvc"
    
    dvc remote modify origin \
        endpointurl "https://dagshub.com/${DAGSHUB_USER}/${DAGSHUB_REPO}.s3"
fi

# On modifie toujours les credientials, au cas où elles changeraient
dvc remote modify origin --local \
    access_key_id "${DAGSHUB_TOKEN}"

dvc remote modify origin --local \
    secret_access_key "${DAGSHUB_TOKEN}"

echo "Pulling latest DVC data..."
dvc pull -r origin || true

exec "$@"