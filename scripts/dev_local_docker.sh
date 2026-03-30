#!/usr/bin/env bash
# Build and run RyuNova with Docker Compose (repo root). Uses docker-compose.app-only.yml.
#
# Prerequisites:
#   - Docker + Compose v2
#   - A .env file in the repo root with at least DATABASE_URL for the API (and Django) pointing at Postgres
#     reachable from containers (often host.docker.internal:5432 on Mac/Windows).
#
# Quick start (copy and edit):
#   cp deploy/local.docker.env.example .env
#   ./scripts/dev_local_docker.sh
#
# URLs: API http://127.0.0.1:8010/health  Web http://127.0.0.1:8011/
#
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [ ! -f .env ]; then
  echo "❌ Missing .env in repo root. Copy deploy/local.docker.env.example to .env and set values."
  exit 1
fi

echo "--- docker compose build + up ---"
docker compose -p ryunova -f docker-compose.app-only.yml up -d --build

echo "--- Django migrate (web) ---"
for i in $(seq 1 25); do
  if docker compose -p ryunova -f docker-compose.app-only.yml exec -T web python manage.py migrate --noinput; then
    echo "✅ Django migrate OK"
    break
  fi
  echo "waiting for web ($i/25)..."
  sleep 2
done

echo "--- API health ---"
curl -sS -f http://127.0.0.1:8010/health && echo "" || echo "⚠️ API not ready yet — check: docker compose -p ryunova logs api"
echo "✅ Stack running. Web: http://127.0.0.1:8011/"
