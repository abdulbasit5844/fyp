#!/usr/bin/env bash
# Installs / updates the app on the Pi as the normal user (no sudo).
# Run after pi-setup.sh; deploy.sh calls this automatically.
set -euo pipefail
APP=~/dms
cd "$APP"

echo "==> backend dependencies"
(cd backend && npm ci --omit=dev --no-fund --no-audit --loglevel=error)
if [[ ! -f backend/.env ]]; then
  secret=$(node -e "console.log(require('crypto').randomBytes(48).toString('hex'))")
  sed -e "s/^NODE_ENV=.*/NODE_ENV=production/" -e "s/^JWT_SECRET=.*/JWT_SECRET=$secret/" \
    backend/.env.example > backend/.env
  chmod 600 backend/.env
  echo "   created backend/.env with a new JWT secret"
fi

echo "==> edge Python environment"
if [[ ! -x edge/.venv/bin/python ]]; then
  # System site-packages gives the venv apt's OpenCV, NumPy, picamera2 and gpiozero.
  python3 -m venv --system-site-packages edge/.venv
fi
# MediaPipe 1.x crashes on the Pi 4 (needs ARMv8 AES); its face mesh model runs on LiteRT instead.
edge/.venv/bin/pip uninstall --quiet --yes mediapipe 2>/dev/null || true
edge/.venv/bin/pip install --quiet --disable-pip-version-check ai-edge-litert onnxruntime
edge/.venv/bin/python edge/scripts/download_models.py

echo "==> user services"
mkdir -p ~/.config/systemd/user
cp deploy/systemd/*.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable dms-backend dms-edge >/dev/null
systemctl --user restart dms-backend dms-edge
sleep 3
systemctl --user --no-pager --lines=0 status dms-backend dms-edge | grep -E "●|Active:"
