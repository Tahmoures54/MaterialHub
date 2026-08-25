from flask import Blueprint, render_template, redirect, url_for, jsonify
from flask_login import current_user, login_required

from models import (
    MaterialRequisition, PurchaseOrder, SupplierMaterial, Delivery,
    WarehouseInventory, QualityControl, Tender, User, AccessLevel,
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


def workspace_kpis(role):
    counts = {
        "materials": _company_query(SupplierMaterial).count(),
        "material_requisitions": _company_query(MaterialRequisition).count(),
        "purchase_orders": _company_query(PurchaseOrder).count(),
        "suppliers": User.query.filter_by(access_level=AccessLevel.supplier).count(),
        "deliveries": _company_query(Delivery).count(),
        "inventory": _company_query(WarehouseInventory).count(),
        "quality_controls": _company_query(QualityControl).count(),
        "tenders": _company_query(Tender).count(),
    }
    mapping = {
        "project_manager": [("Material Records", counts["materials"]), ("Open Requisitions", counts["material_requisitions"]), ("Purchase Orders", counts["purchase_orders"]), ("Deliveries", counts["deliveries"])],
        "engineering": [("Materials", counts["materials"]), ("Material Requisitions", counts["material_requisitions"]), ("Technical Documents", 0), ("Readiness Reviews", 0)],
        "procurement": [("Open Requisitions", counts["material_requisitions"]), ("Purchase Orders", counts["purchase_orders"]), ("Suppliers", counts["suppliers"]), ("RFQs / Tenders", counts["tenders"])],
        "warehouse": [("Inventory Records", counts["inventory"]), ("Deliveries", counts["deliveries"]), ("Materials", counts["materials"]), ("Pending Receipts", 0)],
        "quality": [("QC Records", counts["quality_controls"]), ("Materials", counts["materials"]), ("Pending Inspections", 0), ("Document Reviews", 0)],
        "supplier": [("Supplier Materials", counts["materials"]), ("RFQs / Tenders", counts["tenders"]), ("Purchase Orders", counts["purchase_orders"]), ("Delivery Records", counts["deliveries"])],
        "admin": [("Users", User.query.count()), ("Materials", counts["materials"]), ("Purchase Orders", counts["purchase_orders"]), ("Suppliers", counts["suppliers"])],
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
    return render_template(WORKSPACE_TEMPLATES[requested], workspace_role=requested, workspace_kpis=workspace_kpis(requested))


@role_workspace_bp.get("/api/kpis")
@login_required
def api_kpis():
    role = user_role()
    return jsonify({"role": role, "kpis": workspace_kpis(role)})
