import re
"""Shared utility helpers for MaterialHub."""

from functools import wraps
from datetime import date, timedelta
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


# ---------------------------------------------------------------------------
# Supplier performance / OTIF
# ---------------------------------------------------------------------------

def compute_supplier_performance(supplier_id, *, buyer_company=None, sla_days=30, persist=True):
    """Compute On-Time In-Full and quality metrics for a supplier.

    OTIF definition (practical):
    - Consider closed POs: status ``delivered`` OR ``delivered_date`` set.
    - On-time when actual delivery is on/before issued_date + sla_days
      (default 30). If no issued_date, fall back to created_at date.
    - In-full: treated as full when the PO reached delivered status
      (line-level partial receipts are not yet modelled on PO).
    - OTIF% = on_time_orders / evaluated_orders * 100

    When *persist* is True, upserts ``SupplierScore`` for the current month.

    Returns a dict with otif_score, quality_score, overall_score, counts.
    """
    from models import (
        PurchaseOrder, PurchaseOrderStatus, Delivery, DeliveryStatus,
        QualityControl, InspectionStatus, User,
    )
    from models_intelligence import SupplierScore
    from extensions import db

    supplier = User.query.get(supplier_id)
    if not supplier:
        return {
            'supplier_id': supplier_id,
            'otif_score': 0.0,
            'quality_score': 0.0,
            'overall_score': 0.0,
            'orders_count': 0,
            'evaluated_count': 0,
            'on_time_count': 0,
            'delayed_count': 0,
            'period': date.today().strftime('%Y-%m'),
        }

    order_query = PurchaseOrder.query.filter_by(supplier_id=supplier_id)
    if buyer_company:
        order_query = order_query.filter_by(company_name=buyer_company)
    orders = order_query.all()

    on_time = 0
    delayed = 0
    evaluated = 0
    detail_rows = []

    for po in orders:
        delivered_date = po.delivered_date
        # Prefer linked delivery dates when PO date is missing
        if not delivered_date:
            deliveries = Delivery.query.filter_by(order_id=po.id).all()
            for d in deliveries:
                if d.delivered_date:
                    delivered_date = d.delivered_date
                    break
                if d.status == DeliveryStatus.delivered and d.updated_at:
                    delivered_date = d.updated_at.date()
                    break

        is_closed = (
            po.status == PurchaseOrderStatus.delivered
            or delivered_date is not None
        )
        if not is_closed:
            # Still open – skip for OTIF denominator
            continue

        evaluated += 1
        baseline = po.issued_date
        if not baseline and po.created_at:
            baseline = po.created_at.date()
        if not baseline:
            baseline = date.today()

        deadline = baseline + timedelta(days=sla_days)
        late = False
        # Explicit delayed delivery status counts as late
        late_delivery = Delivery.query.filter_by(
            order_id=po.id, status=DeliveryStatus.delayed
        ).first()
        if late_delivery:
            late = True
        elif delivered_date and delivered_date > deadline:
            late = True

        if late:
            delayed += 1
        else:
            on_time += 1

        detail_rows.append({
            'order_no': po.order_no,
            'status': po.status.value if po.status else None,
            'issued_date': baseline.isoformat() if baseline else None,
            'delivered_date': delivered_date.isoformat() if delivered_date else None,
            'on_time': not late,
        })

    otif = round(100.0 * on_time / evaluated, 1) if evaluated else 0.0

    # Quality from QC records linked to this supplier's POs (via company + supplier)
    quality = 100.0
    try:
        qc_query = QualityControl.query
        if buyer_company:
            qc_query = qc_query.filter_by(company_name=buyer_company)
        # Prefer QC rows tied to the supplier user when available
        qcs = qc_query.filter(
            (QualityControl.user_id == supplier_id)
        ).all()
        if not qcs and buyer_company:
            # Fallback: any QC under buyer company is not supplier-specific; skip
            qcs = []
        if qcs:
            passed = sum(1 for q in qcs if q.status == InspectionStatus.passed)
            quality = round(100.0 * passed / len(qcs), 1)
    except Exception:
        quality = 100.0

    overall = round(0.55 * otif + 0.35 * quality + 0.10 * 100, 1)
    period = date.today().strftime('%Y-%m')
    score_company = buyer_company or supplier.company_name

    if persist and score_company:
        s = SupplierScore.query.filter_by(
            supplier_id=supplier_id,
            period=period,
            company_name=score_company,
        ).first()
        if not s:
            s = SupplierScore(
                supplier_id=supplier_id,
                period=period,
                company_name=score_company,
            )
            db.session.add(s)
        s.otif_score = otif
        s.quality_score = quality
        s.price_score = 100.0
        s.responsiveness_score = 100.0
        s.lead_time_score = round(otif, 1)
        s.overall_score = overall
        s.orders_count = len(orders)
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()

    return {
        'supplier_id': supplier_id,
        'supplier_name': getattr(supplier, 'full_name', None) or getattr(supplier, 'company_name', None),
        'company_name': supplier.company_name,
        'otif_score': otif,
        'quality_score': quality,
        'overall_score': overall,
        'orders_count': len(orders),
        'evaluated_count': evaluated,
        'on_time_count': on_time,
        'delayed_count': delayed,
        'period': period,
        'sla_days': sla_days,
        'orders': detail_rows[:50],
    }


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
