#!/bin/sh
set -eu

if [ -f /run/secrets/postgres_password ]; then
  POSTGRES_PASSWORD="$(cat /run/secrets/postgres_password)"
fi

: "${POSTGRES_USER:?POSTGRES_USER is required}"
: "${POSTGRES_DB:?POSTGRES_DB is required}"
: "${POSTGRES_PASSWORD:?Postgres password secret is required}"

ENCODED_PASSWORD="$(python -c 'import os; from urllib.parse import quote; print(quote(os.environ["POSTGRES_PASSWORD"], safe=""))')"
export DATABASE_URL="postgresql+psycopg2://${POSTGRES_USER}:${ENCODED_PASSWORD}@db:5432/${POSTGRES_DB}"
unset POSTGRES_PASSWORD

exec "$@"
