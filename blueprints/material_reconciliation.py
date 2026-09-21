from collections import defaultdict

from flask import Blueprint, render_template, request
from flask_login import login_required, current_user
from models import (
    Delivery,
    MaterialRequisition,
    PurchaseOrderItem,
    WarehouseInventory,
)

material_reconciliation_bp = Blueprint('material_reconciliation', __name__, template_folder='../templates')


def _tenant(query, model):
    if not current_user.is_admin:
        query = query.filter(model.company_name == current_user.company_name)
    return query


def _build_rows(project_no=None, status='all', search=''):
    """Build one reconciliation row per project/material, avoiding double-counting.

    A material may have multiple MRs and multiple PO lines. Receipts are aggregated
    once from warehouse records for the same tenant + project + item code, then
    compared with the combined engineering requirement.
    """
    mrs = _tenant(MaterialRequisition.query, MaterialRequisition).order_by(
        MaterialRequisition.project_no.asc(),
        MaterialRequisition.item_code.asc(),
        MaterialRequisition.id.asc(),
    ).all()

    if project_no:
        mrs = [m for m in mrs if m.project_no == project_no]

    po_items = PurchaseOrderItem.query.all()
    if not current_user.is_admin:
        po_items = [
            x for x in po_items
            if x.purchase_order and x.purchase_order.company_name == current_user.company_name
        ]

    by_material = defaultdict(list)
    for item in po_items:
        if item.material_requisition_id:
            by_material[item.material_requisition_id].append(item)

    po_ids = {item.purchase_order_id for item in po_items if item.purchase_order_id}
    deliveries = _tenant(Delivery.query, Delivery).filter(
        Delivery.order_id.in_(po_ids) if po_ids else Delivery.id == -1
    ).all()
    deliveries_by_po = defaultdict(list)
    for delivery in deliveries:
        deliveries_by_po[delivery.order_id].append(delivery)

    warehouse = _tenant(WarehouseInventory.query, WarehouseInventory).all()
    received_by_material = defaultdict(float)
    last_receipt_by_material = {}
    for receipt in warehouse:
        key = (receipt.project_no, (receipt.item_code or '').strip())
        received_by_material[key] += float(receipt.received_qty or 0)
        current_date = receipt.receipt_date
        if (
            key not in last_receipt_by_material
            or current_date > last_receipt_by_material[key].receipt_date
        ):
            last_receipt_by_material[key] = receipt

    grouped = {}
    for mr in mrs:
        key = (mr.project_no, (mr.item_code or '').strip())
        if key not in grouped:
            grouped[key] = {
                'mrs': [],
                'required': 0.0,
                'ordered': 0.0,
                'po_numbers': [],
                'delivery_ids': [],
                'delivery_statuses': [],
                'unit': mr.unit_of_measure or 'EA',
                'item_code': (mr.item_code or '').strip(),
                'material_description': mr.material_description or mr.subject or '',
                'project_no': mr.project_no,
            }

        group = grouped[key]
        group['mrs'].append(mr)
        group['required'] += float(mr.quantity or 0)

        for item in by_material.get(mr.id, []):
            group['ordered'] += float(item.quantity or 0)
            po = item.purchase_order
            if po and po.order_no not in group['po_numbers']:
                group['po_numbers'].append(po.order_no)
            if po:
                for delivery in deliveries_by_po.get(po.id, []):
                    if delivery.delivery_id not in group['delivery_ids']:
                        group['delivery_ids'].append(delivery.delivery_id)
                    if delivery.status.value not in group['delivery_statuses']:
                        group['delivery_statuses'].append(delivery.status.value)

    rows = []
    for group in grouped.values():
        key = (group['project_no'], group['item_code'])
        received = received_by_material.get(key, 0.0)
        required = group['required']
        ordered = group['ordered']
        shortage = max(required - received, 0.0)
        surplus = max(received - required, 0.0)
        procurement_gap = max(required - ordered, 0.0)

        if received >= required and required > 0:
            row_status = 'complete' if surplus == 0 else 'surplus'
        elif received > 0:
            row_status = 'shortage'
        elif ordered > 0:
            row_status = 'ordered'
        else:
            row_status = 'not_ordered'

        mr_numbers = [mr.mr_no for mr in group['mrs'] if mr.mr_no]
        text_blob = ' '.join([
            group['item_code'],
            group['material_description'],
            group['project_no'] or '',
            ' '.join(mr_numbers),
            ' '.join(group['po_numbers']),
        ]).lower()
        if search and search.lower() not in text_blob:
            continue
        if status != 'all' and status != row_status:
            continue

        last_receipt = last_receipt_by_material.get(key)
        rows.append({
            'mrs': group['mrs'],
            'mr_numbers': mr_numbers,
            'item_code': group['item_code'],
            'material_description': group['material_description'],
            'project_no': group['project_no'],
            'unit': group['unit'],
            'required': required,
            'ordered': ordered,
            'received': received,
            'shortage': shortage,
            'surplus': surplus,
            'procurement_gap': procurement_gap,
            'status': row_status,
            'po_numbers': group['po_numbers'],
            'delivery_ids': group['delivery_ids'],
            'delivery_statuses': group['delivery_statuses'],
            'last_receipt': last_receipt,
        })

    rows.sort(key=lambda r: (r['project_no'] or '', r['item_code'] or ''))
    return rows


@material_reconciliation_bp.get('/material-reconciliation')
@login_required
def dashboard():
    project_no = (request.args.get('project') or '').strip()
    status = (request.args.get('status') or 'all').strip()
    search = (request.args.get('q') or '').strip()

    rows = _build_rows(project_no=project_no, status=status, search=search)

    projects = sorted({
        r['project_no']
        for r in _build_rows()
        if r['project_no']
    })
    totals = {
        'required': sum(r['required'] for r in rows),
        'ordered': sum(r['ordered'] for r in rows),
        'received': sum(r['received'] for r in rows),
        'shortage': sum(r['shortage'] for r in rows),
        'surplus': sum(r['surplus'] for r in rows),
        'procurement_gap': sum(r['procurement_gap'] for r in rows),
    }
    problem_count = sum(
        1 for r in rows if r['status'] in {'shortage', 'not_ordered', 'surplus'}
    )
    return render_template(
        'material_reconciliation/dashboard.html',
        rows=rows,
        totals=totals,
        projects=projects,
        project_no=project_no,
        status=status,
        search=search,
        problem_count=problem_count,
    )


@material_reconciliation_bp.get('/material-reconciliation/detail')
@login_required
def detail():
    """Show the full trace for one project/material without changing the reconciliation math."""
    project_no = (request.args.get('project') or '').strip()
    item_code = (request.args.get('item') or '').strip()
    if not project_no or not item_code:
        return dashboard()

    mrs = _tenant(MaterialRequisition.query, MaterialRequisition).filter(
        MaterialRequisition.project_no == project_no,
        MaterialRequisition.item_code == item_code,
    ).order_by(MaterialRequisition.required_date.asc(), MaterialRequisition.id.asc()).all()
    if not mrs:
        return render_template(
            'material_reconciliation/detail.html',
            project_no=project_no,
            item_code=item_code,
            mrs=[], po_groups=[], deliveries=[], receipts=[], totals={
                'required': 0.0, 'ordered': 0.0, 'received': 0.0,
                'shortage': 0.0, 'surplus': 0.0,
            },
        )

    mr_ids = {mr.id for mr in mrs}
    po_items = PurchaseOrderItem.query.all()
    po_items = [
        item for item in po_items
        if item.material_requisition_id in mr_ids
        and item.purchase_order
        and (current_user.is_admin or item.purchase_order.company_name == current_user.company_name)
    ]

    po_groups = {}
    for item in po_items:
        po = item.purchase_order
        if po.id not in po_groups:
            po_groups[po.id] = {
                'po': po,
                'quantity': 0.0,
                'mr_numbers': [],
            }
        po_groups[po.id]['quantity'] += float(item.quantity or 0)
        if item.material_requisition and item.material_requisition.mr_no not in po_groups[po.id]['mr_numbers']:
            po_groups[po.id]['mr_numbers'].append(item.material_requisition.mr_no)

    po_ids = set(po_groups)
    deliveries = _tenant(Delivery.query, Delivery).filter(
        Delivery.order_id.in_(po_ids) if po_ids else Delivery.id == -1
    ).order_by(Delivery.delivered_date.desc(), Delivery.id.desc()).all()

    delivery_ids = {delivery.delivery_id for delivery in deliveries}
    receipts = _tenant(WarehouseInventory.query, WarehouseInventory).filter(
        WarehouseInventory.project_no == project_no,
        WarehouseInventory.item_code == item_code,
    ).order_by(WarehouseInventory.receipt_date.desc(), WarehouseInventory.id.desc()).all()

    delivery_by_id = {delivery.delivery_id: delivery for delivery in deliveries}
    for receipt in receipts:
        receipt.matched_delivery = delivery_by_id.get(receipt.delivery_id)

    required = sum(float(mr.quantity or 0) for mr in mrs)
    ordered = sum(group['quantity'] for group in po_groups.values())
    received = sum(float(receipt.received_qty or 0) for receipt in receipts)
    shortage = max(required - received, 0.0)
    surplus = max(received - required, 0.0)
    return render_template(
        'material_reconciliation/detail.html',
        project_no=project_no,
        item_code=item_code,
        material_description=mrs[0].material_description or mrs[0].subject,
        unit=mrs[0].unit_of_measure or 'EA',
        mrs=mrs,
        po_groups=sorted(po_groups.values(), key=lambda group: group['po'].order_no),
        deliveries=deliveries,
        receipts=receipts,
        delivery_ids=delivery_ids,
        totals={
            'required': required,
            'ordered': ordered,
            'received': received,
            'shortage': shortage,
            'surplus': surplus,
        },
    )
