import re
"""Shared utility helpers for MaterialHub."""

from functools import wraps
from flask import flash, redirect, url_for, request
from flask_login import current_user
from models import AccessLevel


def role_required(*roles):
    """
    Decorator to restrict access to specific AccessLevel values.

    Usage:
        @role_required(AccessLevel.purchase, AccessLevel.project_manager)
        def some_view():
            ...
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                flash('Please log in to access this page.', 'warning')
                return redirect(url_for('auth.login'))

            if current_user.is_admin:
                return f(*args, **kwargs)

            if current_user.access_level not in roles:
                flash('You do not have permission to access this page.', 'danger')
                return redirect(url_for('index'))

            return f(*args, **kwargs)
        return decorated_function
    return decorator


def generate_document_number(prefix: str, last_number: int = 0) -> str:
    """
    Generate sequential document numbers like MR-0001, PO-0001, etc.

    Args:
        prefix: Document prefix (e.g. 'MR', 'PO', 'DLV', 'WH')
        last_number: The last used numeric part (default 0)

    Returns:
        Formatted document number string
    """
    next_num = last_number + 1
    return f"{prefix}-{next_num:04d}"


def _next_from_last_value(prefix, raw):
    if raw:
        match = re.search(r"(\d+)$", str(raw))
        if match:
            return generate_document_number(prefix, int(match.group(1)))
    return generate_document_number(prefix, 0)


def _query_last_document(model, field_name, company_name=None):
    from flask import current_app
    db = current_app.extensions.get("sqlalchemy")
    if db is None:
        return None
    query = db.session.query(model)
    if company_name and hasattr(model, "company_name"):
        query = query.filter(getattr(model, "company_name") == company_name)
    return query.order_by(model.id.desc()).first()


def generate_next_mr_no(company_name=None):
    """Return the next Material Requisition number.

    Accepts an optional company_name so callers can scope sequences per tenant.
    Falls back to MR-0001 when no application/database context is available.
    """
    try:
        from models import MaterialRequisition
        last = _query_last_document(MaterialRequisition, "mr_no", company_name)
        raw = getattr(last, "mr_no", None) if last else None
        return _next_from_last_value("MR", raw)
    except Exception:
        return "MR-0001"


def generate_next_po_no(company_name=None):
    try:
        from models import PurchaseOrder
        last = _query_last_document(PurchaseOrder, "order_no", company_name)
        raw = getattr(last, "order_no", None) if last else None
        return _next_from_last_value("PO", raw)
    except Exception:
        return "PO-0001"


def generate_next_delivery_id(company_name=None):
    try:
        from models import Delivery
        last = _query_last_document(Delivery, "delivery_id", company_name)
        raw = getattr(last, "delivery_id", None) if last else None
        return _next_from_last_value("DLV", raw)
    except Exception:
        return "DLV-0001"


def generate_next_warehouse_id(company_name=None):
    try:
        from models import WarehouseInventory
        last = _query_last_document(WarehouseInventory, "warehouse_id", company_name)
        raw = getattr(last, "warehouse_id", None) if last else None
        return _next_from_last_value("WH", raw)
    except Exception:
        return "WH-0001"


def parse_enum(enum_cls, value, default=None):
    """Coerce a string or enum into an Enum member."""
    if value is None or value == "":
        return default
    if isinstance(value, enum_cls):
        return value
    try:
        return enum_cls(value)
    except ValueError:
        try:
            return enum_cls[str(value).lower()]
        except KeyError:
            return default


def csrf_token_from_request():
    """Read a CSRF token from JSON, form or headers."""
    token = request.headers.get("X-CSRFToken") or request.headers.get("X-CSRF-Token")
    if not token and request.form:
        token = request.form.get("csrf_token")
    if not token and request.is_json:
        payload = request.get_json(silent=True) or {}
        token = payload.get("csrf_token")
    return token
