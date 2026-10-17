#!/usr/bin/env bash
# From the laptop, after the Pi boots the fresh drive: system setup, deploy,
# smoke test. Usage: bash deploy/bring-up.sh [user@host]
set -euo pipefail
TARGET="${1:-vision@pi.local}"
HOST="${TARGET#*@}"
cd "$(dirname "$0")/.."

echo "== waiting for $HOST"
ssh-keygen -R "$HOST" >/dev/null 2>&1 || true   # fresh OS has a new host key
until ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=accept-new -o BatchMode=yes "$TARGET" true 2>/dev/null; do sleep 5; done
echo "   connected"

echo "== waiting for first-boot setup (cloud-init) to finish"
ssh "$TARGET" 'cloud-init status --wait >/dev/null 2>&1 || true'

echo "== copying code"
tar -czf /tmp/dms.tgz --exclude=node_modules --exclude=.venv --exclude=__pycache__ \
  --exclude='edge/models' --exclude='edge/clips' --exclude='.env' --exclude='edge/training/output' \
  backend edge deploy docs
scp -q /tmp/dms.tgz "$TARGET:/tmp/dms.tgz"
ssh "$TARGET" 'mkdir -p ~/dms && tar -xzf /tmp/dms.tgz -C ~/dms && rm /tmp/dms.tgz'
rm -f /tmp/dms.tgz

echo "== system setup (sudo)"
read -rsp "Pi sudo password: " PW; echo
ssh "$TARGET" "echo '$PW' | sudo -S -p '' bash ~/dms/deploy/pi-setup.sh" | grep -E '^==>|^v[0-9]|db version|error|Error' || true

echo "== app install + services"
ssh "$TARGET" 'bash ~/dms/deploy/install-app.sh'

echo "== smoke test"
ssh "$TARGET" 'bash ~/dms/deploy/smoke-test.sh'
