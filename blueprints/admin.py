# Admin Blueprint
from flask import Blueprint

admin_bp = Blueprint("admin", __name__)

# Add routes from original app.py (admin, add_user, etc.)