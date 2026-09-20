from flask import Blueprint, jsonify, current_app
from sqlalchemy import text

health_bp = Blueprint("health", __name__)

@health_bp.get("/health/live")
def live():
    return jsonify({"status":"ok","service":"materialhub","check":"liveness"})

@health_bp.get("/health/ready")
def ready():
    db = current_app.extensions.get("sqlalchemy")
    if not db:
        return jsonify({"status":"not_ready","reason":"database extension unavailable"}), 503
    try:
        db.session.execute(text("SELECT 1"))
        return jsonify({"status":"ready","database":"ok"})
    except Exception:
        return jsonify({"status":"not_ready","database":"error"}), 503
