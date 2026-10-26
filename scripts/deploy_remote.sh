#!/usr/bin/env bash
# Запускается НА сервере (myserver) из GitHub Actions (см. .github/workflows/ci.yml).
# Ожидает чистый checkout main и уже созданный .venv с правами пользователя admin.
set -euo pipefail

APP_DIR=/var/www/alina-privat-telegram
SERVICE=alina-telegram-bot

cd "$APP_DIR"

git fetch origin main
git reset --hard origin/main

.venv/bin/pip install --quiet --disable-pip-version-check -r requirements.txt

sudo /usr/bin/systemctl restart "$SERVICE"

sleep 5
systemctl is-active --quiet "$SERVICE"

echo "deploy ok: $(git rev-parse --short HEAD), service: $(systemctl is-active "$SERVICE")"
