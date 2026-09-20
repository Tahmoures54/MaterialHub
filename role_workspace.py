from flask import Blueprint, render_template, redirect, url_for, jsonify
from flask_login import current_user, login_required
from datetime import date

from models import (
    MaterialRequisition, PurchaseOrder, SupplierMaterial, Delivery,
    WarehouseInventory, QualityControl, Tender, User, AccessLevel,
    ApprovalStatus, PurchaseOrderStatus, DeliveryStatus, InspectionStatus,
    WorkflowStatus,
)

role_workspace_bp = Blueprint("role_workspace", __name__, url_prefix="/workspace")

ROLE_ALIASES = {
    "owner": "admin", "administrator": "admin", "admin": "admin",
    "project manager": "project_manager", "project_manager": "project_manager",
    "engineering": "engineering", "engineer": "engineering",
    "procurement": "procurement", "purchasing": "procurement", "buyer": "procurement", "purchase": "procurement",
    "warehouse": "warehouse", "storekeeper": "warehouse", "stores": "warehouse", "delivery": "warehouse",
    "quality": "quality", "qc": "quality", "qa": "quality",
    "supplier": "supplier", "vendor": "supplier",
}

WORKSPACE_TEMPLATES = {
    "admin": "workspaces/admin.html",
    "project_manager": "workspaces/project_manager.html",
    "engineering": "workspaces/engineering.html",
    "procurement": "workspaces/procurement.html",
    "warehouse": "workspaces/warehouse.html",
    "quality": "workspaces/quality.html",
    "supplier": "workspaces/supplier.html",
}


def normalize_role(value):
    key = str(getattr(value, "value", value) or "").strip().lower().replace("-", " ").replace("_", " ")
    return ROLE_ALIASES.get(key, "project_manager")


def user_role():
    if getattr(current_user, "is_admin", False):
        return "admin"
    access = getattr(current_user, "access_level", None)
    if access is not None:
        return normalize_role(access)
    for attr in ("role", "user_role", "role_name"):
        value = getattr(current_user, attr, None)
        if value:
            return normalize_role(value)
    return "project_manager"


def _company_query(model):
    query = model.query
    if not getattr(current_user, "is_admin", False) and hasattr(model, "company_name"):
        query = query.filter(model.company_name == current_user.company_name)
    return query


def _safe_count(builder):
    try:
        return int(builder() or 0)
    except Exception:
        return 0


def workspace_kpis(role):
    today = date.today()
    pending_mrs = _safe_count(lambda: _company_query(MaterialRequisition).filter(
        MaterialRequisition.status == ApprovalStatus.pending).count())
    overdue_mrs = _safe_count(lambda: _company_query(MaterialRequisition).filter(
        MaterialRequisition.required_date < today,
        MaterialRequisition.status != ApprovalStatus.rejected).count())
    open_pos = _safe_count(lambda: _company_query(PurchaseOrder).filter(
        PurchaseOrder.status.in_([PurchaseOrderStatus.pending, PurchaseOrderStatus.issued])).count())
    delayed_deliveries = _safe_count(lambda: _company_query(Delivery).filter(
        Delivery.status == DeliveryStatus.delayed).count())
    pending_receipts = _safe_count(lambda: _company_query(Delivery).filter(
        Delivery.status == DeliveryStatus.delivered).count())
    inventory_lines = _safe_count(lambda: _company_query(WarehouseInventory).count())
    low_stock = _safe_count(lambda: _company_query(WarehouseInventory).filter(
        WarehouseInventory.received_qty < 20).count())
    pending_qc = _safe_count(lambda: _company_query(QualityControl).filter(
        QualityControl.status == InspectionStatus.pending).count())
    failed_qc = _safe_count(lambda: _company_query(QualityControl).filter(
        QualityControl.status == InspectionStatus.failed).count())
    open_tenders = _safe_count(lambda: _company_query(Tender).count())
    materials = _safe_count(lambda: _company_query(SupplierMaterial).count())
    suppliers = _safe_count(lambda: User.query.filter_by(access_level=AccessLevel.supplier).count())
    users = _safe_count(lambda: User.query.count())
    pending_warehouse = _safe_count(lambda: _company_query(WarehouseInventory).filter(
        WarehouseInventory.workflow_status == WorkflowStatus.warehouse).count())

    mapping = {
        "project_manager": [
            ("Pending Approvals", pending_mrs),
            ("Overdue Requisitions", overdue_mrs),
            ("Open Purchase Orders", open_pos),
            ("Delayed Deliveries", delayed_deliveries),
        ],
        "engineering": [
            ("Open Requisitions", pending_mrs),
            ("Overdue Need Dates", overdue_mrs),
            ("Materials Catalog", materials),
            ("Readiness Reviews", overdue_mrs),
        ],
        "procurement": [
            ("Pending Requisitions", pending_mrs),
            ("Open Purchase Orders", open_pos),
            ("RFQs / Tenders", open_tenders),
            ("Delayed Deliveries", delayed_deliveries),
        ],
        "warehouse": [
            ("Inventory Records", inventory_lines),
            ("Low Stock", low_stock),
            ("Pending Receipts", pending_receipts),
            ("Awaiting Approval", pending_warehouse),
        ],
        "quality": [
            ("Pending Inspections", pending_qc),
            ("Failed Inspections", failed_qc),
            ("Delayed Deliveries", delayed_deliveries),
            ("Low Stock Lots", low_stock),
        ],
        "supplier": [
            ("Listed Materials", materials),
            ("Open Tenders", open_tenders),
            ("Purchase Orders", open_pos),
            ("Deliveries", delayed_deliveries),
        ],
        "admin": [
            ("Users", users),
            ("Suppliers", suppliers),
            ("Open Purchase Orders", open_pos),
            ("Low Stock", low_stock),
        ],
    }
    return [{"label": label, "value": value} for label, value in mapping.get(role, mapping["project_manager"])]


@role_workspace_bp.get("/")
@login_required
def my_workspace():
    return redirect(url_for("role_workspace.role", role=user_role()))


@role_workspace_bp.get("/<role>")
@login_required
def role(role):
    requested = normalize_role(role)
    actual = user_role()
    if requested != actual and actual != "admin":
        requested = actual
    return render_template(
        WORKSPACE_TEMPLATES[requested],
        workspace_role=requested,
        workspace_kpis=workspace_kpis(requested),
    )


@role_workspace_bp.get("/api/kpis")
@login_required
def api_kpis():
    role = user_role()
    return jsonify({"role": role, "kpis": workspace_kpis(role)})
