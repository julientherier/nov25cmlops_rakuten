#!/bin/bash
set -e

echo "[Setup] Configuring Git and DVC..."

# ============================================================================
# 1. Git Configuration
# ============================================================================

if [ -n "$GIT_AUTHOR_NAME" ]; then
    git config --global user.name "$GIT_AUTHOR_NAME"
    echo "[Git] user.name = $GIT_AUTHOR_NAME"
fi

if [ -n "$GIT_AUTHOR_EMAIL" ]; then
    git config --global user.email "$GIT_AUTHOR_EMAIL"
    echo "[Git] user.email = $GIT_AUTHOR_EMAIL"
fi

git config --global core.fileMode false
git config --global init.defaultBranch main

# ============================================================================
# 2. SSH Configuration
# ============================================================================

# Pas de chmod — le mount WSL2 est en lecture seule pour les permissions
# SSH fonctionne en root dans Docker sans vérification stricte des permissions

if [ -f "/root/.ssh/id_github" ]; then
    export GIT_SSH_COMMAND="ssh -i /root/.ssh/id_github -o StrictHostKeyChecking=no -o IdentitiesOnly=yes"
    git config --global core.sshCommand "ssh -i /root/.ssh/id_github -o StrictHostKeyChecking=no -o IdentitiesOnly=yes"
    echo "[SSH] Git configured with id_github"
else
    echo "[Warning] /root/.ssh/id_github not found — git push via SSH may fail"
fi

git config --global url."git@github.com:".insteadOf "https://github.com/"
echo "[Git] Configured to use SSH for GitHub"

# ============================================================================
# 3. DVC Configuration
# ============================================================================

if [ -d "/app/.dvc" ]; then
    dvc config core.autostage true
    echo "[DVC] autostage enabled"
    echo "[DVC] Configured remotes:"
    dvc remote list || echo "[DVC] No remotes configured"
else
    echo "[Warning] .dvc directory not found"
fi

# ============================================================================
# Ready!
# ============================================================================

echo "[Setup] ✓ Git + DVC ready!"
[ -n "$GITHUB_USER"  ] && echo "  GitHub:  $GITHUB_USER"
[ -n "$DAGSHUB_USER" ] && echo "  DagsHub: $DAGSHUB_USER"
echo ""

exec "$@"