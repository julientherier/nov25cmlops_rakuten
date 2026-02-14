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

## ============================================================================
# 2. SSH Configuration for GitHub
# ============================================================================

mkdir -p ~/.ssh
chmod 700 ~/.ssh
ssh-keyscan -H github.com >> ~/.ssh/known_hosts 2>/dev/null || true

if [ -f "/root/.ssh/id_github" ]; then
    chmod 600 /root/.ssh/id_github
    echo "[SSH] GitHub SSH key configured"
fi

git config --global url."git@github.com:".insteadOf "https://github.com/"
echo "[Git] Configured to use SSH for GitHub"

export GIT_SSH_COMMAND="ssh -i /root/.ssh/id_github"
git config --global core.sshCommand "ssh -i /root/.ssh/id_github"
echo "[SSH] Git configured to use SSH key"

# ============================================================================
# 3. DVC Configuration (IMPORTANT!)
# ============================================================================

if [ -d "/app/.dvc" ]; then
    # Enable autostage
    dvc config core.autostage true
    echo "[DVC] autostage enabled"
    
    # Show DVC remotes
    echo "[DVC] Configured remotes:"
    dvc remote list || echo "[DVC] No remotes configured"
else
    echo "[Warning] .dvc directory not found - DVC may not be initialized"
fi


# ============================================================================
# Ready!
# ============================================================================

echo "[Setup] ✓ Git + DVC + Docker ready!"
if [ -n "$GITHUB_USER" ]; then
    echo "  GitHub:  $GITHUB_USER"
fi
if [ -n "$DAGSHUB_USER" ]; then
    echo "  DagsHub: $DAGSHUB_USER"
fi
echo ""

# Execute the passed command
exec "$@"
