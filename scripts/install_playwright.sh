#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

echo "== Playwright installer for SAKU_BOT =="

if [[ -x "${REPO_ROOT}/venv/bin/python" ]]; then
  PYTHON="${REPO_ROOT}/venv/bin/python"
  echo "Using venv python: $PYTHON"
else
  PYTHON="$(command -v python3 || command -v python)"
  echo "No venv found. Using system python: $PYTHON"
fi

if [[ $(id -u) -eq 0 ]]; then
  if command -v apt-get >/dev/null 2>&1; then
    echo "Installing system deps for Playwright..."
    apt-get update
    apt-get install -y --no-install-recommends \
      ca-certificates fonts-liberation libasound2 libatk1.0-0 libcups2 \
      libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 libxrandr2 libgbm1 \
      libgtk-3-0 libnss3 lsb-release xdg-utils wget
  fi
fi

if [[ -f "requirements.txt" ]]; then
  echo "Installing Python requirements..."
  "$PYTHON" -m pip install --upgrade pip
  "$PYTHON" -m pip install -r requirements.txt
fi

echo "Downloading Playwright Chromium..."
"$PYTHON" -m playwright install chromium

echo ""
echo "Installation finished."
echo "Now make sure pm2 uses the same interpreter:"
echo "  pm2 stop saku_bot"
echo "  pm2 start main.py --name saku_bot --interpreter $PYTHON"
echo "  pm2 logs saku_bot --lines 80"
