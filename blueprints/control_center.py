from datetime import date
from flask import Blueprint, jsonify, render_template
from flask_login import login_required, current_user

from models import (
    db, MaterialRequisition, PurchaseOrder, Delivery, WarehouseInventory,
    SupplierMaterial, Tender, ApprovalStatus, DeliveryStatus, PurchaseOrderStatus
)
from ai_analysis import predict_delivery_risk

control_center_bp = Blueprint('control_center', __name__)


def _company_filter(query, model):
    if current_user.is_admin:
        return query
    return query.filter(model.company_name == current_user.company_name)


def build_overview():
    mr_q = _company_filter(MaterialRequisition.query, MaterialRequisition)
    po_q = _company_filter(PurchaseOrder.query, PurchaseOrder)
    dlv_q = _company_filter(Delivery.query, Delivery)
    inv_q = _company_filter(WarehouseInventory.query, WarehouseInventory)
    mat_q = _company_filter(SupplierMaterial.query, SupplierMaterial)
    tender_q = _company_filter(Tender.query, Tender)

    requisitions = mr_q.order_by(MaterialRequisition.created_at.desc()).limit(8).all()
    deliveries = dlv_q.order_by(Delivery.updated_at.desc()).limit(12).all()
    inventory = inv_q.order_by(WarehouseInventory.updated_at.desc()).limit(200).all()

    low_stock = [i for i in inventory if (i.received_qty or 0) < 20]
    delayed = [d for d in deliveries if d.status == DeliveryStatus.delayed or predict_delivery_risk(d) >= 0.65]

    pending_mr = mr_q.filter(MaterialRequisition.status == ApprovalStatus.pending).count()
    open_po = po_q.filter(PurchaseOrder.status.in_([PurchaseOrderStatus.pending, PurchaseOrderStatus.issued])).count()

    total_inventory_qty = round(sum((i.received_qty or 0) for i in inventory), 2)
    total_pipeline_value = round(sum((po.total_price or 0) for po in po_q.all()), 2)

    return {
        'counts': {
            'requisitions': mr_q.count(),
            'pending_requisitions': pending_mr,
            'purchase_orders': po_q.count(),
            'open_purchase_orders': open_po,
            'deliveries': dlv_q.count(),
            'delayed_deliveries': len(delayed),
            'inventory_lines': inv_q.count(),
            'low_stock': len(low_stock),
            'supplier_materials': mat_q.count(),
            'open_tenders': tender_q.count(),
        },
        'total_inventory_qty': total_inventory_qty,
        'total_pipeline_value': total_pipeline_value,
        'requisitions': [
            {'no': r.mr_no, 'description': r.material_description, 'status': r.status.value,
             'required_date': r.required_date.isoformat() if r.required_date else None,
             'priority': r.priority, 'project': r.project_no}
            for r in requisitions
        ],
        'delivery_risks': [
            {'id': d.delivery_id, 'risk': predict_delivery_risk(d), 'status': d.status.value,
             'expected': d.delivered_date.isoformat() if d.delivered_date else None}
            for d in delayed[:8]
        ],
        'low_stock': [
            {'item_code': i.item_code, 'description': i.material_description,
             'qty': i.received_qty, 'unit': i.unit, 'location': i.storage_location_id}
            for i in low_stock[:8]
        ]
    }


@control_center_bp.route('/control-center')
@login_required
def dashboard():
    overview = build_overview()
    return render_template('dashboard/control_center.html', overview=overview, today=date.today())


@control_center_bp.route('/api/overview')
@login_required
def api_overview():
    return jsonify(build_overview())
