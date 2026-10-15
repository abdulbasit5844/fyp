#!/usr/bin/env bash
# Copies the backend, edge pipeline and deploy files to the Pi and (re)starts
# the services. Run from the project root on the laptop (Git Bash):
#   bash deploy/deploy.sh [user@host]
set -euo pipefail
TARGET="${1:-vision@pi.local}"
cd "$(dirname "$0")/.."

tar -czf /tmp/dms.tgz \
  --exclude=node_modules --exclude=.venv --exclude=__pycache__ --exclude='edge/models' \
  --exclude='edge/clips' --exclude='.env' --exclude='edge/training/output' \
  backend edge deploy docs

scp -q /tmp/dms.tgz "$TARGET:/tmp/dms.tgz"
ssh "$TARGET" 'mkdir -p ~/dms && tar -xzf /tmp/dms.tgz -C ~/dms && rm /tmp/dms.tgz && bash ~/dms/deploy/install-app.sh'
rm -f /tmp/dms.tgz
