#!/bin/bash
# Backup cashew graph.db every 6 hours, keep last 4 (24hr window)
set -euo pipefail

DB="${CASHEW_DB:-./data/graph.db}"
BACKUP_DIR="$(dirname "$DB")/backups"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)

mkdir -p "$BACKUP_DIR"

# Only backup if DB exists and is non-empty
if [ ! -f "$DB" ] || [ ! -s "$DB" ]; then
  echo "WARN: DB missing or empty at $DB — skipping backup"
  exit 1
fi

# SQLite-safe backup (not just cp — handles WAL/journal)
sqlite3 "$DB" ".backup '${BACKUP_DIR}/graph-${TIMESTAMP}.db'"

echo "Backed up to ${BACKUP_DIR}/graph-${TIMESTAMP}.db ($(du -h "${BACKUP_DIR}/graph-${TIMESTAMP}.db" | cut -f1))"

# Prune: keep only last 4 backups
ls -1t "${BACKUP_DIR}"/graph-*.db 2>/dev/null | tail -n +5 | while read old; do
  echo "Pruning old backup: $old"
  rm "$old"
done

echo "Done. $(ls -1 "${BACKUP_DIR}"/graph-*.db 2>/dev/null | wc -l | tr -d ' ') backups retained."
