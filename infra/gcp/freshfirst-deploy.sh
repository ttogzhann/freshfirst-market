#!/usr/bin/env bash
set -Eeuo pipefail

APP_DIR=/opt/freshfirst

cd "$APP_DIR"
git fetch --depth=1 origin feature/render-deployment
git reset --hard origin/feature/render-deployment

docker compose build --pull
docker compose --profile https up -d
docker compose ps
