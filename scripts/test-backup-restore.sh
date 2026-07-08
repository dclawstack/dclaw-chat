#!/usr/bin/env bash
# Automated proof of the backup/restore cycle (#34):
# seed → backup → destroy → restore → verify.
#
# Needs a reachable Postgres superuser-ish URL (defaults to local dev) and the
# backend's alembic setup. Uses throwaway databases and directories only.
#
# Usage: ./scripts/test-backup-restore.sh [admin-postgres-url]
set -euo pipefail

ADMIN_URL="${1:-postgresql://postgres:postgres@localhost:5432/postgres}"
TEST_DB="dclaw_backup_cycle_test"
BASE_URL="${ADMIN_URL%/*}"
TEST_URL="$BASE_URL/$TEST_DB"
WORKDIR="$(mktemp -d)"
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
trap 'psql "$ADMIN_URL" -qc "DROP DATABASE IF EXISTS $TEST_DB" || true; rm -rf "$WORKDIR"' EXIT

echo "== 1. seed: fresh DB at migration head + sample rows + an upload"
psql "$ADMIN_URL" -qc "DROP DATABASE IF EXISTS $TEST_DB"
psql "$ADMIN_URL" -qc "CREATE DATABASE $TEST_DB"
(cd "$REPO_ROOT/backend" && DATABASE_URL="postgresql+asyncpg://${TEST_URL#postgresql://}" uv run alembic upgrade head -q 2>/dev/null || \
 (cd "$REPO_ROOT/backend" && DATABASE_URL="postgresql+asyncpg://${TEST_URL#postgresql://}" uv run alembic upgrade head))
psql "$TEST_URL" -qc "INSERT INTO workspaces (id, name, created_by) VALUES ('ws-1', 'Backup Test WS', 'tester')"
psql "$TEST_URL" -qc "INSERT INTO channels (id, name, type, workspace_id) VALUES ('ch-1', 'general', 'public', 'ws-1')"
psql "$TEST_URL" -qc "INSERT INTO channel_messages (id, channel_id, user_id, user_name, content, reply_count) VALUES ('m-1', 'ch-1', 'tester', 'Tester', 'precious message', 0)"
mkdir -p "$WORKDIR/uploads/file-1"
echo "precious attachment" > "$WORKDIR/uploads/file-1/doc.txt"

echo "== 2. backup"
DATABASE_URL="$TEST_URL" UPLOADS_DIR="$WORKDIR/uploads" \
  "$REPO_ROOT/scripts/backup.sh" "$WORKDIR/backup"

echo "== 3. destroy: drop the database and delete uploads"
psql "$ADMIN_URL" -qc "DROP DATABASE $TEST_DB"
rm -rf "$WORKDIR/uploads"

echo "== 4. restore into a recreated empty database"
psql "$ADMIN_URL" -qc "CREATE DATABASE $TEST_DB"
DATABASE_URL="$TEST_URL" UPLOADS_DIR="$WORKDIR/uploads" \
  "$REPO_ROOT/scripts/restore.sh" "$WORKDIR/backup"

echo "== 5. verify"
MSG=$(psql "$TEST_URL" -tAc "SELECT content FROM channel_messages WHERE id='m-1'")
[ "$MSG" = "precious message" ] || { echo "FAIL: message not restored (got: $MSG)" >&2; exit 1; }
WS=$(psql "$TEST_URL" -tAc "SELECT count(*) FROM workspaces WHERE id='ws-1'")
[ "$WS" = "1" ] || { echo "FAIL: workspace row not restored" >&2; exit 1; }
REV=$(psql "$TEST_URL" -tAc "SELECT version_num FROM alembic_version")
[ -n "$REV" ] || { echo "FAIL: alembic_version not restored" >&2; exit 1; }
grep -q "precious attachment" "$WORKDIR/uploads/file-1/doc.txt" || { echo "FAIL: upload not restored" >&2; exit 1; }

echo "✓ backup/restore cycle verified (revision $REV)"
