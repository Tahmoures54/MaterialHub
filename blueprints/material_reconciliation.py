from collections import defaultdict

from flask import Blueprint, render_template, request
from flask_login import login_required, current_user
from models import MaterialRequisition, PurchaseOrderItem, WarehouseInventory

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
