import re
"""Shared utility helpers for MaterialHub."""

from functools import wraps
from flask import flash, redirect, url_for, request, abort
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


# ---------------------------------------------------------------------------
# Tenant isolation helpers
# ---------------------------------------------------------------------------

def company_filter(query, model, *, allow_admin: bool = False):
    """Apply tenant scope to a SQLAlchemy query.

    By default every authenticated non-admin user only sees rows belonging
    to their own ``company_name``.  Pass ``allow_admin=True`` when an
    administrative cross-tenant view is intentionally required (and
    preferably protected by additional checks / audit logging).

    Prefer this helper over hand-written ``filter_by(company_name=...)`` so
    that tenant scoping stays consistent and easy to audit.
    """
    if not hasattr(model, 'company_name'):
        return query
    if allow_admin and getattr(current_user, 'is_admin', False):
        return query
    return query.filter(model.company_name == current_user.company_name)


def tenant_query(model, *, allow_admin: bool = False):
    """Return a tenant-scoped base query for *model*.

    Equivalent to ``company_filter(model.query, model, allow_admin=...)``.
    Use this as the starting point for every business-data read.
    """
    return company_filter(model.query, model, allow_admin=allow_admin)


def require_same_tenant(record, *, allow_admin: bool = False):
    """Abort with 404 when *record* belongs to a different tenant.

    Call after fetching a single row by primary key so that IDOR attempts
    cannot leak foreign-tenant data.  Returns the record unchanged when
    the check passes (convenient for chaining).
    """
    if record is None:
        abort(404)
    if not hasattr(record, 'company_name'):
        return record
    if allow_admin and getattr(current_user, 'is_admin', False):
        return record
    if record.company_name != current_user.company_name:
        abort(404)
    return record


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


def _last_number_of(raw):
    """Extract the trailing integer part of a document number (e.g. MR-0007 -> 7)."""
    if raw:
        match = re.search(r"(\d+)$", str(raw))
        if match:
            return int(match.group(1))
    return 0


def _query_last_document(model, field_name, company_name=None):
    from flask import current_app
    db = current_app.extensions.get("sqlalchemy")
    if db is None:
        return None
    query = db.session.query(model)
    if company_name and hasattr(model, "company_name"):
        query = query.filter(getattr(model, "company_name") == company_name)
    return query.order_by(model.id.desc()).first()


# Document type -> (model, number column). The model lookup is deferred so
# this module stays importable without a database.
_DOCUMENT_TYPES = {
    "MR": ("MaterialRequisition", "mr_no"),
    "MAT": ("MaterialMaster", "material_code"),
    "PO": ("PurchaseOrder", "order_no"),
    "DLV": ("Delivery", "delivery_id"),
    "WH": ("WarehouseInventory", "warehouse_id"),
    "TND": ("Tender", "tender_no"),
}


def _allocate_document_number(key, company_name):
    """Atomically allocate the next document number for a tenant.

    Uses the ``document_sequence`` counter so concurrent requests from the
    same company cannot be handed the same number. The counter is seeded
    from existing documents on first use, so pre-existing data keeps its
    numbering.
    """
    from sqlalchemy.exc import IntegrityError
    from flask import current_app
    db = current_app.extensions.get("sqlalchemy")
    if db is None:
        raise RuntimeError("no application context")

    from models import DocumentSequence
    seq = db.session.get(DocumentSequence, (key, company_name))
    if seq is None:
        model_name, field_name = _DOCUMENT_TYPES[key]
        from models import MaterialRequisition, PurchaseOrder, Delivery, WarehouseInventory, MaterialMaster, Tender
        model = {
            "MaterialRequisition": MaterialRequisition,
            "PurchaseOrder": PurchaseOrder,
            "Delivery": Delivery,
            "WarehouseInventory": WarehouseInventory,
            "MaterialMaster": MaterialMaster,
            "Tender": Tender,
        }[model_name]
        last = _query_last_document(model, field_name, company_name)
        seed = _last_number_of(getattr(last, field_name, None) if last else None)
        try:
            with db.session.begin_nested():
                db.session.add(DocumentSequence(key=key, company_name=company_name, last_value=seed))
        except IntegrityError:
            # A concurrent request seeded the row first; the UPDATE below
            # will wait for it and continue from the committed value.
            pass
    seq = db.session.get(DocumentSequence, (key, company_name))
    if seq is None:
        raise RuntimeError(f"document sequence {key}/{company_name} unavailable")
    # next_value() returns the number being claimed (not the previous one),
    # so format it directly instead of calling generate_document_number(),
    # which would increment once more.
    return f"{key}-{seq.next_value():04d}"



def generate_next_material_code(company_name=None):
    """Return a stable tenant-scoped Material Master code (MAT-000001)."""
    try:
        return _allocate_document_number("MAT", company_name or "")
    except Exception:
        return "MAT-000001"


def generate_next_mr_no(company_name=None):
    """Return the next Material Requisition number.

    Sequences are scoped per tenant. Falls back to MR-0001 when no
    application/database context is available.
    """
    try:
        return _allocate_document_number("MR", company_name or "")
    except Exception:
        return "MR-0001"


def generate_next_po_no(company_name=None):
    try:
        return _allocate_document_number("PO", company_name or "")
    except Exception:
        return "PO-0001"


def generate_next_delivery_id(company_name=None):
    try:
        return _allocate_document_number("DLV", company_name or "")
    except Exception:
        return "DLV-0001"


def generate_next_warehouse_transaction_no(company_name=None):
    try:
        return _allocate_document_number("WT", company_name or "")
    except Exception:
        return "WT-0001"


def generate_next_packing_list_no(company_name=None):
    try:
        return _allocate_document_number("PL", company_name or "")
    except Exception:
        return "PL-0001"


def generate_next_goods_receipt_no(company_name=None):
    try:
        return _allocate_document_number("GR", company_name or "")
    except Exception:
        return "GR-0001"


def generate_next_osd_no(company_name=None):
    try:
        return _allocate_document_number("OSD", company_name or "")
    except Exception:
        return "OSD-0001"


def generate_next_warehouse_id(company_name=None):
    try:
        return _allocate_document_number("WH", company_name or "")
    except Exception:
        return "WH-0001"


def generate_next_tender_no(company_name=None):
    """Return the next tenant-scoped tender number (TND-0001).

    Matches Tender.validate pattern ``TND-XXXX`` (at least 4 digits).
    """
    try:
        return _allocate_document_number("TND", company_name or "")
    except Exception:
        return "TND-0001"


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
