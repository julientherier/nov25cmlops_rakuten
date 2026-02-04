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
# 2. Git Credentials (HTTPS Token-based Authentication)
# ============================================================================

# Create .git-credentials file with HTTPS tokens
touch ~/.git-credentials

# Add GitHub credentials (for: git push origin)
if [ -n "$GITHUB_USER" ] && [ -n "$GITHUB_TOKEN" ]; then
    echo "https://${GITHUB_USER}:${GITHUB_TOKEN}@github.com" >> ~/.git-credentials
    echo "[Git] GitHub token configured"
fi

# Add DagsHub credentials (for: git operations + dvc)
if [ -n "$DAGSHUB_USER" ] && [ -n "$DAGSHUB_TOKEN" ]; then
    echo "https://${DAGSHUB_USER}:${DAGSHUB_TOKEN}@dagshub.com" >> ~/.git-credentials
    echo "[Git] DagsHub token configured"
fi

# Set permissions and configure credential helper
chmod 600 ~/.git-credentials
git config --global credential.helper store
git config --global credential.useHttpPath true

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
