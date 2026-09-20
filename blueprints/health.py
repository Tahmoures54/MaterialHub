import os

from flask import Blueprint, jsonify, current_app
from sqlalchemy import text

health_bp = Blueprint("health", __name__)


def _check_database():
    db = current_app.extensions.get("sqlalchemy")
    if not db:
        return False, "database extension unavailable"
    try:
        db.session.execute(text("SELECT 1"))
        return True, "ok"
    except Exception:
        db.session.rollback()
        return False, "error"


def _check_redis():
    uri = current_app.config.get("RATELIMIT_STORAGE_URI", "")
    if not uri.startswith(("redis://", "rediss://")):
        return True, "not_configured"
    try:
        import redis
        client = redis.from_url(uri, socket_connect_timeout=2, socket_timeout=2)
        client.ping()
        return True, "ok"
    except Exception:
        return False, "error"


@health_bp.get("/health")
def health():
    return jsonify({"status": "ok", "service": "materialhub", "check": "basic"})


@health_bp.get("/health/live")
def live():
    return jsonify({"status":"ok","service":"materialhub","check":"liveness"})


@health_bp.get("/health/ready")
def ready():
    db_ok, db_status = _check_database()
    redis_ok, redis_status = _check_redis()
    checks = {"database": db_status, "redis": redis_status}
    if db_ok and redis_ok:
        return jsonify({"status":"ready", "checks": checks})
    return jsonify({"status":"not_ready", "checks": checks}), 503
