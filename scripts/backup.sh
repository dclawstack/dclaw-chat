#!/usr/bin/env bash
# One-command backup: database dump + uploaded files (#34).
#
# Usage:   DATABASE_URL=postgresql://user:pass@host:5432/db ./scripts/backup.sh [output-dir]
# Output:  <output-dir>/db.dump           (pg_dump custom format)
#          <output-dir>/uploads.tar.gz    (file uploads, if any)
#          <output-dir>/MANIFEST          (timestamp + alembic revision)
#
# Docker Compose: run on the host with DATABASE_URL pointing at the published
# port, or `docker compose exec backend ./scripts/backup.sh` inside the image.
set -euo pipefail

DATABASE_URL="${DATABASE_URL:?Set DATABASE_URL to the postgres URL to back up}"
# The app uses an async driver URL; pg tools want a plain postgres:// URL.
PG_URL="${DATABASE_URL/postgresql+asyncpg:\/\//postgresql://}"
UPLOADS_DIR="${UPLOADS_DIR:-backend/uploads}"
OUT="${1:-backups/$(date +%Y%m%d-%H%M%S)}"

mkdir -p "$OUT"

echo "→ dumping database"
pg_dump --format=custom --no-owner --dbname="$PG_URL" --file="$OUT/db.dump"

if [ -d "$UPLOADS_DIR" ] && [ -n "$(ls -A "$UPLOADS_DIR" 2>/dev/null)" ]; then
  echo "→ archiving uploads from $UPLOADS_DIR"
  tar -czf "$OUT/uploads.tar.gz" -C "$UPLOADS_DIR" .
else
  echo "→ no uploads to archive"
fi

{
  echo "created_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "alembic_revision=$(psql "$PG_URL" -tAc 'SELECT version_num FROM alembic_version' 2>/dev/null || echo unknown)"
} > "$OUT/MANIFEST"

echo "✓ backup complete: $OUT"
cat "$OUT/MANIFEST"
