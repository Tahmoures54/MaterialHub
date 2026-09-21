from flask import Blueprint, render_template, request
from flask_login import login_required, current_user
from sqlalchemy import or_
from models import MaterialRequisition, PurchaseOrderItem, PurchaseOrder, Delivery, WarehouseInventory

material_reconciliation_bp = Blueprint('material_reconciliation', __name__, template_folder='../templates')


def _tenant(query, model):
    if not current_user.is_admin:
        query = query.filter(model.company_name == current_user.company_name)
    return query


def _build_rows(project_no=None, status='all', search=''):
    mrs = _tenant(MaterialRequisition.query, MaterialRequisition).order_by(
        MaterialRequisition.project_no.asc(), MaterialRequisition.item_code.asc(), MaterialRequisition.id.asc()
    ).all()

    if project_no:
        mrs = [m for m in mrs if m.project_no == project_no]

    po_items = PurchaseOrderItem.query.all()
    if not current_user.is_admin:
        po_items = [x for x in po_items if x.purchase_order and x.purchase_order.company_name == current_user.company_name]

    by_mr = {}
    po_ids = set()
    for item in po_items:
        by_mr.setdefault(item.material_requisition_id, []).append(item)
        po_ids.add(item.purchase_order_id)

    deliveries = Delivery.query.all()
    if not current_user.is_admin:
        deliveries = [d for d in deliveries if d.company_name == current_user.company_name]
    delivery_to_po = {d.delivery_id: d.order_id for d in deliveries}
    po_delivery_ids = {}
    for d in deliveries:
        po_delivery_ids.setdefault(d.order_id, set()).add(d.delivery_id)

    warehouse = WarehouseInventory.query.all()
    if not current_user.is_admin:
        warehouse = [w for w in warehouse if w.company_name == current_user.company_name]

    rows = []
    for mr in mrs:
        items = by_mr.get(mr.id, [])
        ordered = sum(float(x.quantity or 0) for x in items)
        po_numbers = []
        related_po_ids = set()
        for item in items:
            po = item.purchase_order
            if po:
                related_po_ids.add(po.id)
                if po.order_no not in po_numbers:
                    po_numbers.append(po.order_no)

        received_entries = []
        related_delivery_ids = set()
        for po_id in related_po_ids:
            related_delivery_ids.update(po_delivery_ids.get(po_id, set()))
        if related_delivery_ids:
            received_entries.extend(w for w in warehouse if w.delivery_id in related_delivery_ids)

        # Also support legacy/direct warehouse receipts that carry the MR's
        # material code and project but are not connected to a Delivery yet.
        existing_ids = {w.id for w in received_entries}
        code = (mr.item_code or '').strip()
        if code:
            for w in warehouse:
                if w.id in existing_ids:
                    continue
                if w.project_no == mr.project_no and (w.item_code or '').strip() == code:
                    received_entries.append(w)
                    existing_ids.add(w.id)

        received = sum(float(w.received_qty or 0) for w in received_entries)
        required = float(mr.quantity or 0)
        shortage = max(required - received, 0)
        surplus = max(received - required, 0)
        procurement_gap = max(required - ordered, 0)

        if received >= required and required > 0:
            row_status = 'complete' if surplus == 0 else 'surplus'
        elif received > 0:
            row_status = 'shortage'
        elif ordered > 0:
            row_status = 'ordered'
        else:
            row_status = 'not_ordered'

        text_blob = ' '.join([
            mr.item_code or '', mr.material_description or '', mr.project_no or '',
            mr.mr_no or '', ' '.join(po_numbers)
        ]).lower()
        if search and search.lower() not in text_blob:
            continue
        if status != 'all' and row_status != status:
            continue

        rows.append({
            'mr': mr,
            'required': required,
            'ordered': ordered,
            'received': received,
            'shortage': shortage,
            'surplus': surplus,
            'procurement_gap': procurement_gap,
            'status': row_status,
            'po_numbers': po_numbers,
            'delivery_count': len(received_entries),
        })

    return rows


@material_reconciliation_bp.get('/material-reconciliation')
@login_required
def dashboard():
    project_no = (request.args.get('project') or '').strip()
    status = (request.args.get('status') or 'all').strip()
    search = (request.args.get('q') or '').strip()

    rows = _build_rows(project_no=project_no, status=status, search=search)

    projects = sorted({r['mr'].project_no for r in _build_rows() if r['mr'].project_no})
    totals = {
        'required': sum(r['required'] for r in rows),
        'ordered': sum(r['ordered'] for r in rows),
        'received': sum(r['received'] for r in rows),
        'shortage': sum(r['shortage'] for r in rows),
        'surplus': sum(r['surplus'] for r in rows),
        'procurement_gap': sum(r['procurement_gap'] for r in rows),
    }
    return render_template(
        'material_reconciliation/dashboard.html',
        rows=rows, totals=totals, projects=projects,
        project_no=project_no, status=status, search=search,
    )
