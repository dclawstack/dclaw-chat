#!/usr/bin/env bash
# Restore a backup produced by scripts/backup.sh (#34).
#
# Usage:   DATABASE_URL=postgresql://user:pass@host:5432/db ./scripts/restore.sh <backup-dir>
#
# The target database must exist (createdb first if needed). --clean drops
# and recreates objects, so restoring over a half-broken schema is safe.
# Stop the backend before restoring; start it again afterwards.
set -euo pipefail

BACKUP_DIR="${1:?Usage: restore.sh <backup-dir>}"
DATABASE_URL="${DATABASE_URL:?Set DATABASE_URL to the postgres URL to restore into}"
PG_URL="${DATABASE_URL/postgresql+asyncpg:\/\//postgresql://}"
UPLOADS_DIR="${UPLOADS_DIR:-backend/uploads}"

[ -f "$BACKUP_DIR/db.dump" ] || { echo "No db.dump in $BACKUP_DIR" >&2; exit 1; }

echo "→ restoring database"
pg_restore --clean --if-exists --no-owner --dbname="$PG_URL" "$BACKUP_DIR/db.dump"

if [ -f "$BACKUP_DIR/uploads.tar.gz" ]; then
  echo "→ restoring uploads into $UPLOADS_DIR"
  mkdir -p "$UPLOADS_DIR"
  tar -xzf "$BACKUP_DIR/uploads.tar.gz" -C "$UPLOADS_DIR"
fi

echo "✓ restore complete from $BACKUP_DIR"
[ -f "$BACKUP_DIR/MANIFEST" ] && cat "$BACKUP_DIR/MANIFEST"
