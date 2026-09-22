from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, Response, current_app
from flask_login import login_required, current_user
from extensions import db
from models import (
    ReportShare, MaterialRequest, MaterialRequisition, PurchaseOrder,
    Delivery, WarehouseInventory, AccessLevel, PackingList, PackingListLine, GoodsReceipt, GoodsReceiptLine, OSDReport, PurchaseOrderItem, PurchaseOrderStatus, DeliveryStatus, ReceivingStatus, WarehouseTransaction
)
import csv, io, secrets
from datetime import datetime, timedelta
import pytz
import qrcode
import base64

reports_bp = Blueprint('reports', __name__, template_folder='../templates')


TYPES = {
    'MR': ('Material Requisition', MaterialRequisition, 'mr_no'),
    'PO': ('Purchase Order', PurchaseOrder, 'order_no'),
    'DEL': ('Delivery / Packing List', Delivery, 'delivery_id'),
    'WH': ('Warehouse Receipt', WarehouseInventory, 'warehouse_id'),
}


def _query_model(model):
    q = model.query
    if not current_user.is_admin:
        q = q.filter_by(company_name=current_user.company_name)
    return q


def _record(kind, record_id):
    if kind not in TYPES:
        abort(404)
    model = TYPES[kind][1]
    q = _query_model(model)
    return q.filter_by(id=record_id).first_or_404()


def _value(obj, field):
    value = getattr(obj, field, '')
    if hasattr(value, 'value'):
        value = value.value
    if hasattr(value, 'isoformat'):
        value = value.isoformat()
    return '' if value is None else value


def _qr_data_uri(target):
    img = qrcode.make(target)
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return 'data:image/png;base64,' + base64.b64encode(buf.getvalue()).decode('ascii')


def _record_rows(kind, obj):
    if kind == 'MR':
        return [
            ('Document', obj.mr_no), ('Subject', obj.subject), ('Project', obj.project_no),
            ('Item', obj.item_code), ('Description', obj.material_description),
            ('Quantity', f'{obj.quantity:g} {obj.unit_of_measure}'),
            ('Priority', obj.priority), ('Status', _value(obj.status)),
            ('Required date', _value(obj.required_date)), ('Discipline', obj.discipline),
            ('Remarks', obj.remarks or '')
        ]
    if kind == 'PO':
        supplier = getattr(obj, 'supplier', None)
        project = getattr(obj, 'project', None)
        return [
            ('Document', obj.order_no), ('Project', getattr(project, 'project_no', '')),
            ('Supplier', getattr(supplier, 'full_name', '') or getattr(supplier, 'company_email', '')),
            ('Total', obj.total_price), ('Status', _value(obj.status)),
            ('Issued', _value(obj.issued_date)), ('Delivered', _value(obj.delivered_date)),
            ('Remarks', obj.remarks or '')
        ]
    if kind == 'DEL':
        return [('Document', obj.delivery_id), ('PO', getattr(obj, 'order_id', '')),
                ('Status', _value(obj.status)), ('Remarks', obj.remarks or ''),
                ('Created', _value(obj.created_at))]
    return [('Document', obj.warehouse_id), ('Delivery', obj.delivery_id),
            ('Item', obj.item_code), ('Description', obj.material_description),
            ('Quantity', obj.received_qty), ('Unit', obj.unit),
            ('Project', obj.project_no), ('Location', obj.storage_location_id or ''),
            ('Status', _value(obj.workflow_status)), ('Remarks', obj.remarks or '')]


def _number(kind, obj):
    return _value(obj, TYPES[kind][2])



# Operational receiving / traceability print packs
REPORT_TYPES = {
    'PL': ('Packing List Register', PackingList, 'packing_list_no'),
    'GR': ('Goods Receipt', GoodsReceipt, 'receipt_no'),
    'OSD': ('OSD / OS&D Report', OSDReport, 'osd_no'),
    'RR': ('Receiving Report', GoodsReceipt, 'receipt_no'),
    'TRACE': ('Material Traceability', GoodsReceiptLine, 'id'),
}

def _operational_query(model):
    return model.query.filter_by(company_name=current_user.company_name)

def _operational_record(kind, record_id):
    meta = REPORT_TYPES.get(kind)
    if not meta:
        abort(404)
    return _operational_query(meta[1]).filter_by(id=record_id).first_or_404()

def _operational_payload(kind, obj):
    if kind == 'PL':
        lines = list(getattr(obj, 'lines', []) or [])
        return {
            'number': obj.packing_list_no, 'subtitle': 'Packing List Register / Inbound Package Manifest',
            'meta': [('Packing List Date', _value(obj.packing_list_date)), ('PO', getattr(obj.order, 'order_no', obj.order_id or '')),
                     ('Delivery', getattr(obj.delivery, 'delivery_id', obj.delivery_id or '')), ('Supplier', getattr(obj.supplier, 'full_name', '') or getattr(obj.supplier, 'company_email', '')),
                     ('Vehicle', obj.vehicle_no or ''), ('Packages', obj.package_count or ''), ('Gross Weight', obj.gross_weight or ''), ('Net Weight', obj.net_weight or ''), ('Status', obj.status)],
            'headers': ['#','Item Code','Description','Qty','Unit','Package','Lot','Heat','Serial'],
            'table': [[i+1,l.item_code,l.material_description,l.quantity,l.unit,l.package_no or '',l.lot_no or '',l.heat_no or '',l.serial_no or ''] for i,l in enumerate(lines)],
            'notes': obj.remarks or ''
        }
    if kind in {'GR','RR'}:
        lines = list(getattr(obj, 'lines', []) or [])
        return {
            'number': obj.receipt_no, 'subtitle': 'Inbound Material Receiving Record' if kind == 'RR' else 'Goods Receipt',
            'meta': [('Receipt Date', _value(obj.receipt_date)), ('Packing List', getattr(obj.packing_list, 'packing_list_no', obj.packing_list_id or '')),
                     ('PO', getattr(obj.order, 'order_no', obj.order_id or '')), ('Delivery', getattr(obj.delivery, 'delivery_id', obj.delivery_id or '')),
                     ('Warehouse', obj.warehouse_id), ('Received By', getattr(obj.receiver, 'full_name', '') or getattr(obj.receiver, 'company_email', '')), ('Status', _value(obj.status))],
            'headers': ['#','Item Code','Description','Expected','Received','Variance','Unit','Location','Inspection','Lot / Heat / Serial'],
            'table': [[i+1,l.item_code,l.material_description,l.expected_qty,l.received_qty,l.received_qty-l.expected_qty,l.unit,l.storage_location_id or '',l.inspection_status, ' / '.join(x for x in [l.lot_no,l.heat_no,l.serial_no] if x)] for i,l in enumerate(lines)],
            'notes': obj.remarks or ''
        }
    if kind == 'OSD':
        lines = list(getattr(obj, 'lines', []) or [])
        return {
            'number': obj.osd_no, 'subtitle': 'Over / Short / Damaged Report',
            'meta': [('Report Date', _value(obj.report_date)), ('Goods Receipt', getattr(obj.goods_receipt, 'receipt_no', obj.goods_receipt_id)),
                     ('Packing List', getattr(obj.packing_list, 'packing_list_no', obj.packing_list_id)), ('Delivery', getattr(obj.delivery, 'delivery_id', obj.delivery_id or '')),
                     ('Supplier', getattr(obj.supplier, 'full_name', '') or getattr(obj.supplier, 'company_email', '')), ('Status', _value(obj.status))],
            'headers': ['#','Item Code','Discrepancy','Expected','Received','Variance','Details','Action Required'],
            'table': [[i+1,getattr(l.material,'material_code', '') or '',l.discrepancy_type,l.expected_qty,l.received_qty,l.variance_qty,l.details or '',l.action_required or ''] for i,l in enumerate(lines)],
            'notes': obj.remarks or ''
        }
    line = obj
    gr = line.goods_receipt
    pl = line.packing_list_line.packing_list if line.packing_list_line else None
    inv = WarehouseInventory.query.filter_by(company_name=current_user.company_name, material_id=line.material_id, warehouse_id=gr.warehouse_id).first()
    txs = WarehouseTransaction.query.filter_by(company_name=current_user.company_name, receipt_line_id=line.id).order_by(WarehouseTransaction.created_at.asc()).all()
    return {
        'number': f'TRACE-{line.id:06d}', 'subtitle': 'Material Traceability Record',
        'meta': [('Item Code', line.item_code), ('Description', line.material_description), ('Material ID', line.material_id),
                 ('Goods Receipt', gr.receipt_no), ('Packing List', getattr(pl, 'packing_list_no', '')), ('Warehouse', gr.warehouse_id),
                 ('Receipt Date', _value(gr.receipt_date)), ('Inspection', line.inspection_status)],
        'headers': ['Event','Transaction','Qty','Unit','Balance After','Reference','Date'],
        'table': [[tx.transaction_type,tx.transaction_no,tx.quantity,tx.unit,tx.balance_after or '',tx.reference_no or tx.packing_list_no or '',_value(tx.created_at)] for tx in txs] or [['RECEIPT','—',line.received_qty,line.unit,(getattr(inv,'available_qty',0) or 0) + (getattr(inv,'quarantine_qty',0) or 0),gr.receipt_no,_value(gr.receipt_date)]],
        'notes': f"Lot: {line.lot_no or '—'} | Heat: {line.heat_no or '—'} | Serial: {line.serial_no or '—'} | Location: {line.storage_location_id or '—'}"
    }

def _reconciliation_rows():
    company = current_user.company_name
    mrs = MaterialRequisition.query.filter_by(company_name=company).order_by(
        MaterialRequisition.project_no.asc(), MaterialRequisition.item_code.asc(), MaterialRequisition.id.asc()
    ).all()
    rows = []
    for mr in mrs:
        po_items = PurchaseOrderItem.query.join(PurchaseOrder).filter(
            PurchaseOrderItem.material_requisition_id == mr.id,
            PurchaseOrder.company_name == company,
            PurchaseOrder.status != PurchaseOrderStatus.cancelled,
        ).all()
        po_ids = [x.purchase_order_id for x in po_items]
        po_qty = sum(float(x.quantity or 0) for x in po_items)

        deliveries = Delivery.query.filter(
            Delivery.company_name == company,
            Delivery.material_id == mr.material_id,
        ).filter(Delivery.order_id.in_(po_ids) if po_ids else db.text('1=0')).all()
        delivery_qty = po_qty if deliveries else 0.0

        pls = PackingList.query.filter_by(company_name=company).filter(
            PackingList.order_id.in_(po_ids) if po_ids else db.text('1=0')
        ).all()
        pl_ids = [x.id for x in pls]
        pl_lines = PackingListLine.query.filter(
            PackingListLine.packing_list_id.in_(pl_ids),
            PackingListLine.material_id == mr.material_id,
        ).all() if pl_ids else []
        pl_qty = sum(float(x.quantity or 0) for x in pl_lines)

        grs = GoodsReceipt.query.filter_by(company_name=company, status=ReceivingStatus.posted).filter(
            GoodsReceipt.packing_list_id.in_(pl_ids) if pl_ids else db.text('1=0')
        ).all()
        gr_ids = [x.id for x in grs]
        gr_lines = GoodsReceiptLine.query.filter(
            GoodsReceiptLine.goods_receipt_id.in_(gr_ids),
            GoodsReceiptLine.material_id == mr.material_id,
        ).all() if gr_ids else []
        grn_qty = sum(float(x.received_qty or 0) for x in gr_lines)

        qc_passed_qty = sum(float(x.received_qty or 0) for x in gr_lines if str(x.inspection_status).lower() == 'passed')
        qc_pending_qty = sum(float(x.received_qty or 0) for x in gr_lines if str(x.inspection_status).lower() == 'pending')
        qc_failed_qty = sum(float(x.received_qty or 0) for x in gr_lines if str(x.inspection_status).lower() == 'failed')

        invs = WarehouseInventory.query.filter_by(
            company_name=company, material_id=mr.material_id, project_no=mr.project_no
        ).all()
        wh_received = sum(float(x.received_qty or 0) for x in invs)
        wh_available = sum(float(x.available_qty or 0) for x in invs)
        wh_quarantine = sum(float(x.quarantine_qty or 0) for x in invs)

        rows.append({
            'mr': mr, 'mr_qty': float(mr.quantity or 0), 'po_qty': po_qty,
            'delivery_qty': delivery_qty, 'pl_qty': pl_qty, 'grn_qty': grn_qty,
            'qc_passed_qty': qc_passed_qty, 'qc_pending_qty': qc_pending_qty,
            'qc_failed_qty': qc_failed_qty, 'warehouse_received_qty': wh_received,
            'warehouse_available_qty': wh_available, 'warehouse_quarantine_qty': wh_quarantine,
            'variance_mr_po': po_qty - float(mr.quantity or 0),
            'variance_po_delivery': delivery_qty - po_qty,
            'variance_delivery_pl': pl_qty - delivery_qty,
            'variance_pl_grn': grn_qty - pl_qty,
            'variance_grn_qc': qc_passed_qty - grn_qty,
            'variance_qc_warehouse': wh_available - qc_passed_qty,
            'po_count': len(po_ids), 'delivery_count': len(deliveries),
            'pl_count': len(pl_ids), 'gr_count': len(gr_ids),
        })
    return rows

@reports_bp.get('/reports/reconciliation')
@login_required
def reconciliation():
    rows = _reconciliation_rows()
    keys = ('mr_qty','po_qty','delivery_qty','pl_qty','grn_qty','qc_passed_qty','qc_pending_qty','qc_failed_qty','warehouse_received_qty','warehouse_available_qty','warehouse_quarantine_qty','variance_mr_po','variance_po_delivery','variance_delivery_pl','variance_pl_grn','variance_grn_qc','variance_qc_warehouse')
    totals = {k: sum(r[k] for r in rows) for k in keys}
    return render_template('reports/reconciliation.html', rows=rows, totals=totals)

@reports_bp.get('/reports/reconciliation/print')
@login_required
def reconciliation_print():
    rows = _reconciliation_rows()
    keys = ('mr_qty','po_qty','delivery_qty','pl_qty','grn_qty','qc_passed_qty','qc_pending_qty','qc_failed_qty','warehouse_received_qty','warehouse_available_qty','warehouse_quarantine_qty','variance_mr_po','variance_po_delivery','variance_delivery_pl','variance_pl_grn','variance_grn_qc','variance_qc_warehouse')
    totals = {k: sum(r[k] for r in rows) for k in keys}
    return render_template('reports/reconciliation_print.html', rows=rows, totals=totals)

@reports_bp.get('/reports/operational')
@login_required
def operational_center():
    counts = {k: _operational_query(m).count() for k,(_,m,_) in REPORT_TYPES.items()}
    return render_template('reports/operational_center.html', report_types=REPORT_TYPES, counts=counts)

@reports_bp.get('/reports/operational/<kind>')
@login_required
def operational_listing(kind):
    if kind not in REPORT_TYPES: abort(404)
    label, model, number_field = REPORT_TYPES[kind]
    rows = _operational_query(model).order_by(model.id.desc()).limit(500).all()
    return render_template('reports/operational_list.html', kind=kind, label=label, rows=rows, number_field=number_field)

@reports_bp.get('/reports/operational/<kind>/<int:record_id>')
@login_required
def operational_report(kind, record_id):
    obj = _operational_record(kind, record_id)
    payload = _operational_payload(kind, obj)
    return render_template('reports/print_document.html', kind=kind, title=REPORT_TYPES[kind][0], obj=obj, **payload)

@reports_bp.get('/reports/operational/<kind>/print')
@login_required
def operational_print_register(kind):
    if kind not in REPORT_TYPES: abort(404)
    label, model, number_field = REPORT_TYPES[kind]
    rows = _operational_query(model).order_by(model.id.desc()).limit(500).all()
    return render_template('reports/operational_register.html', kind=kind, title=label, rows=rows, number_field=number_field)

@reports_bp.get('/reports')
@login_required
def center():
    counts = {k: _query_model(m).count() for k, (_, m, _) in TYPES.items()}
    requests_count = MaterialRequest.query.filter_by(company_name=current_user.company_name).count()
    return render_template('reports/center.html', types=TYPES, counts=counts, requests_count=requests_count)


@reports_bp.get('/reports/<kind>')
@login_required
def listing(kind):
    if kind not in TYPES:
        abort(404)
    label, model, number_field = TYPES[kind]
    rows = _query_model(model).order_by(model.id.desc()).limit(200).all()
    return render_template('reports/list.html', kind=kind, label=label, rows=rows, number_field=number_field)


@reports_bp.get('/reports/<kind>/<int:record_id>')
@login_required
def report(kind, record_id):
    obj = _record(kind, record_id)
    target = url_for('reports.report', kind=kind, record_id=record_id, _external=True)
    return render_template('reports/document.html', kind=kind, title=TYPES[kind][0],
                           number=_number(kind, obj), rows=_record_rows(kind, obj),
                           qr=_qr_data_uri(target), share_target=target, obj=obj)


@reports_bp.get('/reports/<kind>/<int:record_id>/csv')
@login_required
def export_csv(kind, record_id):
    obj = _record(kind, record_id)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Field', 'Value'])
    writer.writerows(_record_rows(kind, obj))
    return Response('\ufeff' + output.getvalue(), mimetype='text/csv',
                    headers={'Content-Disposition': f'attachment; filename={kind}-{_number(kind,obj)}.csv'})


@reports_bp.post('/reports/<kind>/<int:record_id>/share')
@login_required
def create_share(kind, record_id):
    obj = _record(kind, record_id)
    expires = max(1, min(int(request.form.get('days', 7)), 30))
    token = secrets.token_urlsafe(48)
    share = ReportShare(token=token, company_name=current_user.company_name,
                        report_type=kind, record_id=obj.id, created_by=current_user.id,
                        expires_at=datetime.now(pytz.UTC) + timedelta(days=expires))
    db.session.add(share); db.session.commit()
    flash('Secure report link created. You can now copy it or scan the QR code.', 'success')
    return redirect(url_for('reports.shared_report', token=token))


@reports_bp.get('/reports/shared/<token>')
def shared_report(token):
    share = ReportShare.query.filter_by(token=token).first_or_404()
    now = datetime.now(pytz.UTC)
    expiry = share.expires_at if share.expires_at.tzinfo else pytz.UTC.localize(share.expires_at)
    if share.revoked_at or expiry <= now:
        abort(410)
    model = TYPES.get(share.report_type, (None, None, None))[1]
    if not model:
        abort(404)
    obj = model.query.filter_by(id=share.record_id, company_name=share.company_name).first_or_404()
    target = url_for('reports.shared_report', token=token, _external=True)
    return render_template('reports/shared_document.html', kind=share.report_type, title=TYPES[share.report_type][0],
                           number=_number(share.report_type,obj), rows=_record_rows(share.report_type,obj),
                           qr=_qr_data_uri(target), obj=obj)


@reports_bp.post('/reports/shared/<token>/revoke')
@login_required
def revoke_share(token):
    share = ReportShare.query.filter_by(token=token, company_name=current_user.company_name).first_or_404()
    share.revoked_at = datetime.now(pytz.UTC)
    db.session.commit()
    flash('Share link revoked.', 'success')
    return redirect(url_for('reports.center'))


@reports_bp.get('/requests')
@login_required
def requests():
    rows = MaterialRequest.query.filter_by(company_name=current_user.company_name).order_by(MaterialRequest.id.desc()).limit(200).all()
    return render_template('reports/requests.html', rows=rows)


@reports_bp.post('/requests/create')
@login_required
def create_request():
    kind = request.form.get('request_type', 'MR')
    record_id = int(request.form.get('record_id', 0))
    obj = _record(kind, record_id)
    request_no = f"REQ-{datetime.now(pytz.UTC).strftime('%Y%m%d')}-{secrets.token_hex(3).upper()}"
    item = MaterialRequest(request_no=request_no, company_name=current_user.company_name,
                           request_type=kind, record_id=obj.id,
                           title=(request.form.get('title') or f'Request for {_number(kind,obj)}')[:200],
                           message=(request.form.get('message') or '')[:5000],
                           status='pending', created_by=current_user.id)
    db.session.add(item); db.session.commit()
    flash('Request created.', 'success')
    return redirect(url_for('reports.request_detail', request_id=item.id))


@reports_bp.get('/requests/<int:request_id>')
@login_required
def request_detail(request_id):
    item = MaterialRequest.query.filter_by(id=request_id, company_name=current_user.company_name).first_or_404()
    obj = _record(item.request_type, item.record_id)
    return render_template('reports/request_detail.html', item=item, obj=obj,
                           document_number=_number(item.request_type,obj),
                           qr=_qr_data_uri(url_for('reports.request_detail', request_id=item.id, _external=True)))


@reports_bp.post('/requests/<int:request_id>/status')
@login_required
def request_status(request_id):
    item = MaterialRequest.query.filter_by(id=request_id, company_name=current_user.company_name).first_or_404()
    status = request.form.get('status')
    if status not in {'pending', 'approved', 'rejected', 'closed'}:
        abort(400)
    item.status = status
    db.session.commit()
    return redirect(url_for('reports.request_detail', request_id=item.id))
