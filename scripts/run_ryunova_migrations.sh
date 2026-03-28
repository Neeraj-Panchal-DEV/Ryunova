#!/usr/bin/env bash
# Run on EC2 (or anywhere with docker + psql client image). Used by .github/workflows/deploy-prod.yml.
#
# - Optionally creates the target database if missing (admin must have CREATEDB or be superuser).
# - Ensures app role exists with password (FinText-style shared cluster user).
# - Applies db/*.sql listed in db/migrations/order.txt (typically mvp1_schema.sql only); records each in ryunova.ryunova_schema_migrations.
# - Grants DML on ryunova.<ryunova_*> app tables to the app role (not ryunova_schema_migrations).
#
# Required env: ADMIN_USER ADMIN_PW APPL_USER APPL_PW DB_HOST DB_PORT DB_NAME REPO_DIR

set -euo pipefail

: "${ADMIN_USER:?Set ADMIN_USER}"
: "${ADMIN_PW:?Set ADMIN_PW}"
: "${APPL_USER:?Set APPL_USER}"
: "${APPL_PW:?Set APPL_PW}"
: "${DB_HOST:?Set DB_HOST}"
: "${DB_PORT:?Set DB_PORT}"
: "${DB_NAME:?Set DB_NAME}"
: "${REPO_DIR:?Set REPO_DIR}"

ORDER_FILE="${REPO_DIR}/db/migrations/order.txt"
PG_IMG="${PG_IMAGE:-postgres:14}"

psql_admin() {
  # Args: database name, then psql args
  local db="$1"
  shift
  docker run --rm -e PGPASSWORD="${ADMIN_PW}" "${PG_IMG}" \
    psql -h "${DB_HOST}" -p "${DB_PORT}" -U "${ADMIN_USER}" -d "${db}" -v ON_ERROR_STOP=1 "$@"
}

psql_admin_file() {
  local db="$1"
  local file="$2"
  docker run --rm -e PGPASSWORD="${ADMIN_PW}" -v "${file}:/tmp/m.sql:ro" "${PG_IMG}" \
    psql -h "${DB_HOST}" -p "${DB_PORT}" -U "${ADMIN_USER}" -d "${db}" -v ON_ERROR_STOP=1 -1 -f /tmp/m.sql
}

echo "--- RyuNova DB: ensure postgres image ---"
docker pull "${PG_IMG}" >/dev/null 2>&1 || true

echo "--- RyuNova DB: ensure database exists ---"
DB_EXISTS="$(psql_admin postgres -tAc "SELECT 1 FROM pg_database WHERE datname = '${DB_NAME}'" | tr -d '[:space:]' || true)"
if [ "${DB_EXISTS}" != "1" ]; then
  echo "Creating database ${DB_NAME}..."
  psql_admin postgres -c "CREATE DATABASE \"${DB_NAME}\";" || {
    echo "⚠️ CREATE DATABASE failed (permissions?). Create the database manually and re-run deploy."
    exit 1
  }
else
  echo "Database ${DB_NAME} already exists."
fi

echo "--- RyuNova DB: ensure app role ---"
APPL_PW_ESC=$(echo "${APPL_PW}" | sed "s/'/''/g")
psql_admin "${DB_NAME}" -c "CREATE ROLE \"${APPL_USER}\" LOGIN PASSWORD '${APPL_PW_ESC}';" 2>/dev/null || true
psql_admin "${DB_NAME}" -c "ALTER ROLE \"${APPL_USER}\" WITH LOGIN PASSWORD '${APPL_PW_ESC}';"

echo "--- RyuNova DB: migration tracking table (schema ryunova) ---"
psql_admin "${DB_NAME}" -c "
CREATE SCHEMA IF NOT EXISTS ryunova;
CREATE TABLE IF NOT EXISTS ryunova.ryunova_schema_migrations (
  id SERIAL PRIMARY KEY,
  migration_name TEXT NOT NULL UNIQUE,
  applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
"

echo "--- RyuNova DB: apply pending migrations from ${ORDER_FILE} ---"
if [ ! -f "${ORDER_FILE}" ]; then
  echo "❌ Missing ${ORDER_FILE}"
  exit 1
fi

while IFS= read -r line || [ -n "${line}" ]; do
  line="${line#"${line%%[![:space:]]*}"}"
  line="${line%"${line##*[![:space:]]}"}"
  [ -z "${line}" ] && continue
  [[ "${line}" =~ ^# ]] && continue
  rel="${line}"
  base="$(basename "${rel}")"
  SQL_PATH="${REPO_DIR}/db/${rel}"
  if [ ! -f "${SQL_PATH}" ]; then
    echo "❌ Missing SQL file: ${SQL_PATH}"
    exit 1
  fi
  DONE="$(psql_admin "${DB_NAME}" -tAc "SELECT 1 FROM ryunova.ryunova_schema_migrations WHERE migration_name='${base}'" | tr -d '[:space:]' || true)"
  if [ "${DONE}" = "1" ]; then
    echo "  skip (already applied): ${base}"
    continue
  fi
  echo "  applying: ${base}"
  psql_admin_file "${DB_NAME}" "${SQL_PATH}"
  BASE_ESC=$(echo "${base}" | sed "s/'/''/g")
  psql_admin "${DB_NAME}" -c "INSERT INTO ryunova.ryunova_schema_migrations (migration_name) VALUES ('${BASE_ESC}');"
  echo "  ✅ ${base}"
done < "${ORDER_FILE}"

echo "--- RyuNova DB: grants on schema ryunova (app tables only) ---"
psql_admin "${DB_NAME}" -c "
GRANT USAGE ON SCHEMA ryunova TO \"${APPL_USER}\";
DO \$\$
DECLARE r RECORD;
BEGIN
  FOR r IN
    SELECT tablename FROM pg_tables
    WHERE schemaname = 'ryunova'
      AND tablename LIKE 'ryunova_%'
      AND tablename <> 'ryunova_schema_migrations'
  LOOP
    EXECUTE format('GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE ryunova.%I TO %I', r.tablename, '${APPL_USER}');
  END LOOP;
  FOR r IN
    SELECT c.relname AS name
    FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = 'ryunova' AND c.relkind = 'S'
      AND c.relname LIKE 'ryunova_%'
  LOOP
    EXECUTE format('GRANT USAGE, SELECT ON SEQUENCE ryunova.%I TO %I', r.name, '${APPL_USER}');
  END LOOP;
END
\$\$;
"

echo "--- RyuNova DB: verify app user can connect ---"
docker run --rm -e PGPASSWORD="${APPL_PW}" "${PG_IMG}" \
  psql -h "${DB_HOST}" -p "${DB_PORT}" -U "${APPL_USER}" -d "${DB_NAME}" -v ON_ERROR_STOP=1 \
  -c "SELECT 1 AS app_ok;"

echo "✅ RyuNova database migrations complete."
