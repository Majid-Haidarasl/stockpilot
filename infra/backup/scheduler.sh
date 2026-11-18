#!/usr/bin/env bash
# Long-running backup loop (Compose backup-scheduler). No Docker socket.
set -euo pipefail

INTERVAL="${STOCKPILOT_BACKUP_INTERVAL_SECONDS:-43200}"
echo "backup-scheduler interval_seconds=${INTERVAL}"

while true; do
  if /usr/local/bin/backup.sh; then
    echo "backup-scheduler: success"
  else
    echo "backup-scheduler: backup failed (exit=$?); will retry after interval" >&2
  fi
  sleep "$INTERVAL"
done
