from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from datetime import datetime
from flask_login import login_required, current_user
from models import db, QualityControl, InspectionStatus, AccessLevel, GoodsReceiptLine, WarehouseInventory, GoodsReceipt
from forms.material_forms import QualityControlForm
from utils import parse_enum, tenant_query
import logging

logger = logging.getLogger(__name__)

quality_control_bp = Blueprint("quality_control", __name__, template_folder='templates')


def _company_qc():
    """Tenant-scoped QC query. Admins remain scoped to their own company."""
    return tenant_query(QualityControl, allow_admin=False)


@quality_control_bp.route('/')
@login_required
def quality_control():
    logger.info("Accessing quality control dashboard")
    return render_template('quality/quality_control.html', mode='dashboard')


@quality_control_bp.route('/get_quality_controls')
@login_required
def get_quality_controls():
    try:
        quality_controls = _company_qc().order_by(QualityControl.updated_at.desc()).all()
        logger.info("Fetched quality control records from database")
        return render_template('quality/quality_control.html', mode='list', quality_controls=quality_controls)
    except Exception as e:
        logger.error(f"Error fetching quality controls: {e}")
        return render_template('errors/500.html'), 500


@quality_control_bp.route('/create_quality_control', methods=['GET', 'POST'])
@login_required
def create_quality_control():
    if current_user.access_level not in (AccessLevel.quality, AccessLevel.project_manager) and not current_user.is_admin:
        flash('Only quality users can create inspections.', 'danger')
        return redirect(url_for('quality_control.quality_control'))
    form = QualityControlForm()
    if form.validate_on_submit():
        try:
            quality_control = QualityControl(
                order_id=form.order_id.data,
                user_id=current_user.id,
                status=parse_enum(InspectionStatus, form.status.data, InspectionStatus.pending),
                remarks=form.remarks.data,
                company_name=current_user.company_name,
            )
            db.session.add(quality_control)
            db.session.commit()
            logger.info("Created new quality control record")
            flash('Quality inspection recorded.', 'success')
            return redirect(url_for('quality_control.quality_control'))
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error creating quality control: {e}")
            return render_template('errors/500.html'), 500
    return render_template('quality/quality_control.html', mode='create', form=form)


@quality_control_bp.route('/api/receipt-inspections/<int:receipt_line_id>', methods=['PATCH'])
@login_required
def update_receipt_inspection(receipt_line_id):
    """Post QC result for a receipt line and release/retain its quarantined stock."""
    if current_user.access_level not in (AccessLevel.quality, AccessLevel.project_manager) and not current_user.is_admin:
        return jsonify({'error': 'Only quality users can post inspection results'}), 403
    try:
        data = request.get_json() or {}
        from flask_wtf.csrf import validate_csrf, CSRFError
        validate_csrf(data.get('csrf_token'))
        line = GoodsReceiptLine.query.filter_by(id=receipt_line_id).first()
        if not line:
            return jsonify({'error': 'Receipt Line not found'}), 404
        # Enforce tenant via parent GoodsReceipt
        receipt = tenant_query(GoodsReceipt).filter_by(id=line.goods_receipt_id).first()
        if not receipt:
            return jsonify({'error': 'Receipt Line not found'}), 404
        result = str(data.get('status') or '').lower()
        if result not in ('passed', 'failed', 'pending'):
            return jsonify({'error': 'Status must be passed, failed, or pending'}), 400
        qc = tenant_query(QualityControl).filter_by(
            receipt_line_id=line.id
        ).order_by(QualityControl.created_at.desc()).first()
        if not qc:
            qc = QualityControl(
                order_id=receipt.order_id,
                material_id=line.material_id,
                user_id=current_user.id,
                goods_receipt_id=line.goods_receipt_id,
                receipt_line_id=line.id,
                warehouse_id=receipt.warehouse_id,
                company_name=current_user.company_name,
            )
            db.session.add(qc)
        previous_status = qc.status.value if qc.status else 'pending'
        qc.status = InspectionStatus(result)
        qc.inspected_date = datetime.utcnow().date()
        qc.user_id = current_user.id
        qc.remarks = data.get('remarks')
        inventory = tenant_query(WarehouseInventory).filter_by(
            warehouse_id=receipt.warehouse_id,
            material_id=line.material_id,
        ).first()
        if inventory:
            qty = float(line.received_qty or 0)
            if result == 'passed' and previous_status != 'passed':
                inventory.quarantine_qty = max(0.0, float(inventory.quarantine_qty or 0) - qty)
                inventory.available_qty = float(inventory.available_qty or 0) + qty
            elif result == 'failed':
                # Failed material remains quarantined until a controlled disposition.
                inventory.quarantine_qty = float(inventory.quarantine_qty or 0)
        line.inspection_status = result
        db.session.commit()
        return jsonify({'quality_control': qc.to_dict(), 'receipt_line': line.to_dict(),
                        'inventory': inventory.to_dict() if inventory else None}), 200
    except CSRFError:
        db.session.rollback()
        return jsonify({'error': 'Invalid CSRF token'}), 403
    except Exception:
        db.session.rollback()
        logger.exception('Receipt inspection update failed')
        return jsonify({'error': 'Failed to update receipt inspection'}), 500
