#!/usr/bin/env bash
# Runs once on a fresh Postgres data volume (official image entrypoint).
# Not a substitute for Alembic. Keycloak DB/user are prepared for T05.
set -euo pipefail

: "${STOCKPILOT_MIGRATOR_PASSWORD:?STOCKPILOT_MIGRATOR_PASSWORD is required}"
: "${STOCKPILOT_APP_PASSWORD:?STOCKPILOT_APP_PASSWORD is required}"
: "${KEYCLOAK_DB_PASSWORD:?KEYCLOAK_DB_PASSWORD is required}"

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<EOSQL
CREATE ROLE stockpilot_migrator LOGIN PASSWORD '${STOCKPILOT_MIGRATOR_PASSWORD}' NOSUPERUSER NOBYPASSRLS;
CREATE ROLE stockpilot_app LOGIN PASSWORD '${STOCKPILOT_APP_PASSWORD}' NOSUPERUSER NOBYPASSRLS;
CREATE ROLE keycloak LOGIN PASSWORD '${KEYCLOAK_DB_PASSWORD}' NOSUPERUSER NOBYPASSRLS;

CREATE DATABASE stockpilot OWNER stockpilot_migrator;
CREATE DATABASE keycloak OWNER keycloak;

GRANT CONNECT ON DATABASE stockpilot TO stockpilot_app;
EOSQL

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "stockpilot" <<EOSQL
-- Runtime role must not own application schemas/tables (prepared for RLS in T06).
REVOKE ALL ON SCHEMA public FROM PUBLIC;
REVOKE ALL ON SCHEMA public FROM stockpilot_app;
GRANT USAGE ON SCHEMA public TO stockpilot_app;
GRANT CREATE ON SCHEMA public TO stockpilot_migrator;
EOSQL

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "keycloak" <<EOSQL
GRANT ALL ON SCHEMA public TO keycloak;
EOSQL
