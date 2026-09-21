from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, Response, current_app
from flask_login import login_required, current_user
from extensions import db
from models import (
    ReportShare, MaterialRequest, MaterialRequisition, PurchaseOrder,
    Delivery, WarehouseInventory, AccessLevel
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
    return render_template('reports/document.html', kind=share.report_type, title=TYPES[share.report_type][0],
                           number=_number(share.report_type,obj), rows=_record_rows(share.report_type,obj),
                           qr=_qr_data_uri(target), share_target=target, obj=obj, public_share=True)


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
    target = url_for('reports.request_detail', request_id=item.id, _external=True)
    return render_template('reports/request_detail.html', item=item, obj=obj,
                           document_number=_number(item.request_type,obj), qr=_qr_data_uri(target), share_target=target)


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


@reports_bp.get('/requests/<int:request_id>/share')
@login_required
def request_share(request_id):
    item = MaterialRequest.query.filter_by(id=request_id, company_name=current_user.company_name).first_or_404()
    token = secrets.token_urlsafe(48)
    share = ReportShare(token=token, company_name=current_user.company_name,
                        report_type='REQ', record_id=item.id, created_by=current_user.id,
                        expires_at=datetime.now(pytz.UTC) + timedelta(days=7))
    db.session.add(share); db.session.commit()
    target = url_for('reports.shared_request', token=token, _external=True)
    return render_template('reports/share_request.html', item=item, share_target=target, qr=_qr_data_uri(target))


@reports_bp.get('/requests/shared/<token>')
def shared_request(token):
    share = ReportShare.query.filter_by(token=token, report_type='REQ').first_or_404()
    now = datetime.now(pytz.UTC)
    expiry = share.expires_at if share.expires_at.tzinfo else pytz.UTC.localize(share.expires_at)
    if share.revoked_at or expiry <= now:
        abort(410)
    item = MaterialRequest.query.filter_by(id=share.record_id, company_name=share.company_name).first_or_404()
    obj = _record(item.request_type, item.record_id)
    target = url_for('reports.shared_request', token=token, _external=True)
    return render_template('reports/request_detail.html', item=item, obj=obj,
                           document_number=_number(item.request_type, obj),
                           qr=_qr_data_uri(target), share_target=target, public_share=True)
