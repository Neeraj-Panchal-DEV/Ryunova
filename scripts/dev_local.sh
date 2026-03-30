#!/usr/bin/env bash
# Local development helper (repo root). Does not start long-running servers.
#
# What it does:
#   - pip install backend + web requirements (current Python)
#   - django manage.py migrate (session DB)
#   - optional: apply pending SQL from db/migrations/order.txt via local psql
#
# Usage:
#   ./scripts/dev_local.sh
#   ./scripts/dev_local.sh --sql        # also run Postgres files in order.txt (needs PG* env)
#
# After this, start processes manually (see LOCAL_DEVELOPMENT.md):
#   Terminal A: cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
#   Terminal B: cd web && python manage.py runserver 0.0.0.0:8001
#
# Docker (same compose as server, ports 8010/8011):
#   cp deploy/local.docker.env.example .env   # edit DATABASE_URL / secrets
#   ./scripts/dev_local_docker.sh
#
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

DO_SQL=0
if [ "${1:-}" = "--sql" ]; then DO_SQL=1; fi

VENV="${ROOT}/.venv"
if [ ! -d "${VENV}" ]; then
  echo "--- Creating ${VENV} ---"
  python3 -m venv "${VENV}"
fi
# shellcheck source=/dev/null
source "${VENV}/bin/activate"

echo "--- pip install (backend + web) ---"
python -m pip install -q -U pip
python -m pip install -q -r backend/requirements.txt
python -m pip install -q -r web/requirements.txt

echo "--- Django migrate (SQLite sessions) ---"
python web/manage.py migrate --noinput

if [ "$DO_SQL" = "1" ]; then
  if [ -z "${PGDATABASE:-}" ] || [ -z "${PGUSER:-}" ]; then
    echo "❌ For --sql set PGHOST PGPORT PGUSER PGPASSWORD PGDATABASE (or use ~/.pgpass)."
    exit 1
  fi
  echo "--- Apply SQL migrations (local psql) ---"
  export PGPASSWORD="${PGPASSWORD:-}"
  ORDER_FILE="${ROOT}/db/migrations/order.txt"
  while IFS= read -r line || [ -n "${line}" ]; do
    line="${line#"${line%%[![:space:]]*}"}"
    line="${line%"${line##*[![:space:]]}"}"
    [ -z "${line}" ] && continue
    [[ "${line}" =~ ^# ]] && continue
    rel="${line}"
    SQL_PATH="${ROOT}/db/${rel}"
    if [ ! -f "${SQL_PATH}" ]; then
      echo "❌ Missing ${SQL_PATH}"
      exit 1
    fi
    base="$(basename "${rel}")"
    done="$(psql -tAc "SELECT 1 FROM ryunova.ryunova_schema_migrations WHERE migration_name='${base}'" 2>/dev/null | tr -d '[:space:]' || true)"
    if [ "${done}" = "1" ]; then
      echo "  skip (recorded): ${base}"
      continue
    fi
    echo "  applying: ${base}"
    psql -v ON_ERROR_STOP=1 -f "${SQL_PATH}"
    base_esc="${base//\'/''}"
    psql -v ON_ERROR_STOP=1 -c "INSERT INTO ryunova.ryunova_schema_migrations (migration_name) VALUES ('${base_esc}');" 2>/dev/null || {
      echo "⚠️  If ryunova_schema_migrations is missing, run db/mvp1_schema.sql first."
      exit 1
    }
  done < "${ORDER_FILE}"
  echo "✅ SQL migrations applied (or skipped if already recorded)."
fi

echo ""
echo "✅ Local prep done."
echo "   API:  cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"
echo "   Web:  cd web && python manage.py runserver 0.0.0.0:8001"
echo "   Or:   ./scripts/dev_local_docker.sh"
