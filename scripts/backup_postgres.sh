#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
if [[ ! -f .env.prod ]]; then
  echo "Missing .env.prod" >&2
  exit 1
fi

umask 077
mkdir -p backups
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
backup="backups/materialhub_${stamp}.dump"
tmp="${backup}.tmp"
if [[ -e "$backup" || -e "${backup}.sha256" ]]; then
  echo "Backup path already exists; refusing to overwrite: $backup" >&2
  exit 1
fi
trap 'rm -f "$tmp" "${tmp}.sha256"' EXIT
docker compose --env-file .env.prod -f docker-compose.production.yml exec -T db \
  sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom' > "$tmp"
if [[ ! -s "$tmp" ]]; then
  echo "pg_dump returned an empty backup" >&2
  exit 1
fi
sha256sum "$tmp" | awk '{print $1}' > "${tmp}.sha256"
mv "$tmp" "$backup"
mv "${tmp}.sha256" "${backup}.sha256"
trap - EXIT
echo "Backup created: $backup"
echo "SHA-256 file: ${backup}.sha256"
