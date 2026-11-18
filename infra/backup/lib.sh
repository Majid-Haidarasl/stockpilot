#!/usr/bin/env bash
# Shared helpers for StockPilot backup/restore. Never echo secrets.
set -euo pipefail

require_env() {
  local name="$1"
  if [[ -z "${!name:-}" ]]; then
    echo "missing required env: ${name}" >&2
    exit 1
  fi
}

require_backup_env() {
  require_env PGHOST
  require_env PGUSER
  require_env PGPASSWORD
  require_env RESTIC_REPOSITORY
  require_env RESTIC_PASSWORD
  : "${PGPORT:=5432}"
  : "${STOCKPILOT_IMAGE_TAG:=local}"
  : "${STOCKPILOT_MEDIA_DIR:=/var/lib/stockpilot/media}"
  : "${STOCKPILOT_BACKUP_SCRATCH:=/var/lib/stockpilot/backup-scratch}"
  : "${RESTIC_CACHE_DIR:=${STOCKPILOT_BACKUP_SCRATCH}/.restic-cache}"
  export RESTIC_CACHE_DIR
  mkdir -p "$RESTIC_CACHE_DIR"
}

psql_backup() {
  psql -v ON_ERROR_STOP=1 "$@"
}

ensure_restic_repo() {
  if ! restic snapshots >/dev/null 2>&1; then
    echo "restic: initializing repository (first run)"
    restic init
  fi
}

schema_revision() {
  psql_backup -Atqc "SELECT version_num FROM alembic_version LIMIT 1" -d stockpilot \
    || echo "unknown"
}

record_backup_heartbeat() {
  local details_json="$1"
  # details_json must be a single-line JSON object; quote safely for SQL.
  local escaped
  escaped=$(printf '%s' "$details_json" | sed "s/'/''/g")
  psql_backup -d stockpilot -c \
    "SELECT platform.record_backup_heartbeat('${escaped}'::jsonb);"
}

cleanup_scratch() {
  local dir="${1:-}"
  if [[ -n "$dir" && -d "$dir" ]]; then
    rm -rf "$dir"
    echo "scratch cleaned: ${dir}"
  fi
}
