#!/usr/bin/env bash
# MaterialHub production helper
# Usage: ./scripts/prod_up.sh [build|up|migrate|seed|status|logs]
set -euo pipefail

COMPOSE="docker compose -f docker-compose.production.yml"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

cmd="${1:-up}"

case "$cmd" in
  build)
    $COMPOSE build
    ;;
  up)
    if [[ ! -f .env.prod ]]; then
      echo "Missing .env.prod — copy from .env.prod.example and fill values."
      exit 1
    fi
    if [[ ! -f secrets/postgres_password ]]; then
      echo "Missing secrets/postgres_password"
      exit 1
    fi
    $COMPOSE up -d
    echo "Waiting for health..."
    sleep 8
    $COMPOSE ps
    ;;
  migrate)
    $COMPOSE exec web flask db upgrade
    ;;
  seed)
    $COMPOSE exec -e SEED_DEMO=1 web python scripts/seed_demo.py
    ;;
  status)
    $COMPOSE ps
    echo
    curl -fsS http://127.0.0.1/health/live 2>/dev/null || curl -k -fsS https://127.0.0.1/health/live || true
    ;;
  logs)
    $COMPOSE logs --tail=100 -f web nginx
    ;;
  *)
    echo "Usage: $0 {build|up|migrate|seed|status|logs}"
    exit 1
    ;;
esac
