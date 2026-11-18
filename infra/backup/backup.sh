#!/usr/bin/env bash
# One-shot encrypted backup: globals + stockpilot + keycloak + media → restic.
# Runs as stockpilot_backup (BYPASSRLS + pg_read_all_data). Never uses superuser/migrator.
set -euo pipefail
# shellcheck source=/dev/null
source /usr/local/bin/lib.sh

require_backup_env

RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-$$"
STAGING="${STOCKPILOT_BACKUP_SCRATCH}/${RUN_ID}"
mkdir -p "$STAGING"
trap 'cleanup_scratch "$STAGING"' EXIT

echo "backup start run_id=${RUN_ID}"

ensure_restic_repo

echo "dumping globals (no role passwords)"
pg_dumpall --globals-only --no-role-passwords -f "${STAGING}/globals.sql"

echo "dumping stockpilot (custom format)"
pg_dump -Fc --dbname=stockpilot -f "${STAGING}/stockpilot.dump"
pg_restore -l "${STAGING}/stockpilot.dump" >/dev/null

echo "dumping keycloak (custom format)"
pg_dump -Fc --dbname=keycloak -f "${STAGING}/keycloak.dump"
pg_restore -l "${STAGING}/keycloak.dump" >/dev/null

SCHEMA_REV="$(schema_revision)"
META="${STAGING}/backup-meta.json"
cat >"$META" <<EOF
{"run_id":"${RUN_ID}","schema":"${SCHEMA_REV}","app_image":"${STOCKPILOT_IMAGE_TAG}","created_at":"$(date -u +%Y-%m-%dT%H:%M:%SZ)"}
EOF

MEDIA_DIR="${STOCKPILOT_MEDIA_DIR}"
if [[ ! -d "$MEDIA_DIR" ]]; then
  echo "media dir missing: ${MEDIA_DIR}" >&2
  exit 1
fi

echo "restic backup (dumps + media)"
# Paths relative tags; include staging contents and media tree.
SNAPSHOT_OUT="$(
  restic backup \
    --tag "app_image=${STOCKPILOT_IMAGE_TAG}" \
    --tag "schema=${SCHEMA_REV}" \
    --tag "run_id=${RUN_ID}" \
    "$STAGING" \
    "$MEDIA_DIR"
)"
echo "$SNAPSHOT_OUT"
SNAPSHOT_ID="$(echo "$SNAPSHOT_OUT" | sed -n 's/.*snapshot \([a-f0-9]*\) saved.*/\1/p' | tail -n1)"
if [[ -z "$SNAPSHOT_ID" ]]; then
  # Fallback: latest snapshot short id
  SNAPSHOT_ID="$(restic snapshots --json | sed -n 's/.*"short_id":"\([^"]*\)".*/\1/p' | tail -n1)"
fi
echo "restic snapshot_id=${SNAPSHOT_ID}"

echo "restic forget (keep-daily 14, keep-monthly 3)"
restic forget --keep-daily 14 --keep-monthly 3

COUNTER_FILE="${STOCKPILOT_BACKUP_SCRATCH}/.run_counter"
COUNT=0
if [[ -f "$COUNTER_FILE" ]]; then
  COUNT="$(cat "$COUNTER_FILE" 2>/dev/null || echo 0)"
fi
COUNT=$((COUNT + 1))
echo "$COUNT" >"$COUNTER_FILE"
CHECK_EVERY="${STOCKPILOT_BACKUP_CHECK_EVERY_N:-14}"
if (( COUNT % CHECK_EVERY == 0 )); then
  echo "restic prune + check (every ${CHECK_EVERY} runs; count=${COUNT})"
  restic prune
  restic check
else
  echo "skip prune/check (count=${COUNT}, every=${CHECK_EVERY})"
fi

DETAILS_JSON=$(printf '{"snapshot_id":"%s","schema":"%s","app_image":"%s","run_id":"%s"}' \
  "$SNAPSHOT_ID" "$SCHEMA_REV" "$STOCKPILOT_IMAGE_TAG" "$RUN_ID")
echo "recording backup heartbeat"
record_backup_heartbeat "$DETAILS_JSON"

# Explicit cleanup before trap (unencrypted staging must not remain).
cleanup_scratch "$STAGING"
trap - EXIT

echo "backup complete snapshot_id=${SNAPSHOT_ID}"
