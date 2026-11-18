#!/usr/bin/env bash
# Restore restic snapshot into the *current* Postgres + media mounts.
# Intended only for -p stockpilot-restore. Never down -v.
#
# Dumps were taken as stockpilot_backup. pg_restore needs a privileged role
# (Postgres superuser) to re-apply owners/privileges (do not strip ownership).
set -euo pipefail
# shellcheck source=/dev/null
source /usr/local/bin/lib.sh

require_env STOCKPILOT_RESTORE_CONFIRM
if [[ "${STOCKPILOT_RESTORE_CONFIRM}" != "stockpilot-restore" ]]; then
  echo "refusing restore: STOCKPILOT_RESTORE_CONFIRM must be exactly 'stockpilot-restore'" >&2
  exit 1
fi

require_env RESTIC_REPOSITORY
require_env RESTIC_PASSWORD
require_env PGHOST
require_env PGPASSWORD
: "${PGUSER:=postgres}"
: "${PGPORT:=5432}"
: "${STOCKPILOT_MEDIA_DIR:=/var/lib/stockpilot/media}"
: "${STOCKPILOT_BACKUP_SCRATCH:=/var/lib/stockpilot/backup-scratch}"
: "${RESTIC_SNAPSHOT:=latest}"
: "${RESTIC_CACHE_DIR:=${STOCKPILOT_BACKUP_SCRATCH}/.restic-cache}"
export RESTIC_CACHE_DIR
mkdir -p "$RESTIC_CACHE_DIR"

STAGING="${STOCKPILOT_BACKUP_SCRATCH}/restore-$$"
mkdir -p "$STAGING"
trap 'cleanup_scratch "$STAGING"' EXIT

echo "restore start snapshot=${RESTIC_SNAPSHOT} as PGUSER=${PGUSER}"

restic restore "${RESTIC_SNAPSHOT}" --target "$STAGING"

DUMP_FILE="$(find "$STAGING" -type f -name 'stockpilot.dump' | head -n1 || true)"
if [[ -z "${DUMP_FILE}" ]]; then
  echo "stockpilot.dump not found in restored tree" >&2
  exit 1
fi
DUMP_ROOT="$(dirname "$DUMP_FILE")"
echo "dump_root=${DUMP_ROOT}"

GLOBALS="${DUMP_ROOT}/globals.sql"
if [[ -f "$GLOBALS" ]]; then
  echo "verifying expected roles from globals.sql (reference only; not replaying)"
  for role in stockpilot_migrator stockpilot_app stockpilot_relay stockpilot_metrics stockpilot_backup keycloak; do
    if grep -Eq "ROLE[[:space:]]+(\"${role}\"|${role})" "$GLOBALS"; then
      echo "  globals lists role: ${role}"
    else
      echo "  warning: globals.sql does not list role ${role}" >&2
    fi
    exists="$(psql -v ON_ERROR_STOP=1 -Atqc "SELECT 1 FROM pg_roles WHERE rolname='${role}'" -d postgres || true)"
    if [[ "$exists" != "1" ]]; then
      echo "role missing in cluster (run ensure-db-roles / wait for init): ${role}" >&2
      exit 1
    fi
  done
else
  echo "globals.sql missing; continuing with ensure-db-roles expectation" >&2
fi

echo "pg_restore stockpilot (keep owners and privileges)"
pg_restore --clean --if-exists --dbname=stockpilot "${DUMP_ROOT}/stockpilot.dump"

echo "pg_restore keycloak (keep owners and privileges)"
pg_restore --clean --if-exists --dbname=keycloak "${DUMP_ROOT}/keycloak.dump"

echo "restoring media into ${STOCKPILOT_MEDIA_DIR}"
MEDIA_SRC="$(find "$STAGING" -type d -path '*/var/lib/stockpilot/media' | head -n1 || true)"
if [[ -z "$MEDIA_SRC" ]]; then
  MEDIA_SRC="$(find "$STAGING" -type d -name media | head -n1 || true)"
fi
if [[ -z "$MEDIA_SRC" ]]; then
  echo "media tree not found in snapshot" >&2
  exit 1
fi
mkdir -p "${STOCKPILOT_MEDIA_DIR}"
find "${STOCKPILOT_MEDIA_DIR}" -mindepth 1 -maxdepth 1 -exec rm -rf {} +
cp -a "${MEDIA_SRC}/." "${STOCKPILOT_MEDIA_DIR}/"

cleanup_scratch "$STAGING"
trap - EXIT
echo "restore complete"
