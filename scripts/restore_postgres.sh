#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
if [[ ! -f .env.prod ]]; then
  echo "Missing .env.prod" >&2
  exit 1
fi
if [[ $# -ne 2 ]]; then
  echo "Usage: bash scripts/restore_postgres.sh BACKUP.dump NEW_DATABASE_NAME" >&2
  exit 2
fi

backup="$(realpath "$1")"
target_db="$2"
if [[ ! -f "$backup" || ! -s "$backup" ]]; then
  echo "Backup file is missing or empty: $backup" >&2
  exit 1
fi
if [[ ! "$target_db" =~ ^[A-Za-z0-9_]+$ ]]; then
  echo "Target database name may contain only letters, digits and underscores." >&2
  exit 2
fi
if [[ ! -f "${backup}.sha256" ]]; then
  echo "Missing checksum file: ${backup}.sha256" >&2
  exit 1
fi
expected="$(tr -d '[:space:]' < "${backup}.sha256")"
actual="$(sha256sum "$backup" | awk '{print $1}')"
if [[ "$expected" != "$actual" ]]; then
  echo "Backup checksum mismatch; refusing restore." >&2
  exit 1
fi

compose=(docker compose --env-file .env.prod -f docker-compose.production.yml)
# Never overwrite a database. Restore only into a new, isolated target DB.
if ! "${compose[@]}" exec -T -e TARGET_DB="$target_db" db \
  sh -c 'createdb -U "$POSTGRES_USER" "$TARGET_DB"'; then
  echo "Could not create target database '$target_db'. It may already exist; no existing database was overwritten." >&2
  exit 1
fi

if ! "${compose[@]}" exec -T -e TARGET_DB="$target_db" db \
  sh -c 'pg_restore -U "$POSTGRES_USER" -d "$TARGET_DB" --no-owner --no-privileges' < "$backup"; then
  echo "Restore failed. The new target database '$target_db' may be partial; inspect and drop it manually after review." >&2
  exit 1
fi
echo "Restore completed into new database: $target_db"
