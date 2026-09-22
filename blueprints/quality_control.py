from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from datetime import datetime
from flask_login import login_required, current_user
from models import db, QualityControl, InspectionStatus, AccessLevel, GoodsReceiptLine, WarehouseInventory
from forms.material_forms import QualityControlForm
from utils import parse_enum
import logging

logger = logging.getLogger(__name__)

quality_control_bp = Blueprint("quality_control", __name__, template_folder='templates')


def _company_qc():
    query = QualityControl.query
    if not current_user.is_admin:
        query = query.filter_by(company_name=current_user.company_name)
    return query


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
        if not line or line.goods_receipt.company_name != current_user.company_name:
            return jsonify({'error': 'Receipt Line not found'}), 404
        result = str(data.get('status') or '').lower()
        if result not in ('passed', 'failed', 'pending'):
            return jsonify({'error': 'Status must be passed, failed, or pending'}), 400
        qc = QualityControl.query.filter_by(
            receipt_line_id=line.id, company_name=current_user.company_name
        ).order_by(QualityControl.created_at.desc()).first()
        if not qc:
            qc = QualityControl(
                order_id=line.goods_receipt.order_id,
                material_id=line.material_id,
                user_id=current_user.id,
                goods_receipt_id=line.goods_receipt_id,
                receipt_line_id=line.id,
                warehouse_id=line.goods_receipt.warehouse_id,
                company_name=current_user.company_name,
            )
            db.session.add(qc)
        qc.status = InspectionStatus(result)
        qc.inspected_date = datetime.utcnow().date()
        qc.user_id = current_user.id
        qc.remarks = data.get('remarks')
        inventory = WarehouseInventory.query.filter_by(
            warehouse_id=line.goods_receipt.warehouse_id,
            material_id=line.material_id,
            company_name=current_user.company_name
        ).first()
        if inventory:
            qty = float(line.received_qty or 0)
            if result == 'passed':
                inventory.quarantine_qty = max(0.0, float(inventory.quarantine_qty or 0) - qty)
                inventory.available_qty = float(inventory.available_qty or 0) + qty
            elif result == 'failed':
                inventory.quarantine_qty = max(0.0, float(inventory.quarantine_qty or 0) - qty)
        line.inspection_status = result
        db.session.commit()
        return jsonify({'quality_control': qc.to_dict(), 'receipt_line': line.to_dict(),
                        'inventory': inventory.to_dict() if inventory else None}), 200
    except CSRFError:
        db.session.rollback()
        return jsonify({'error': 'Invalid CSRF token'}), 403
    except Exception as exc:
        db.session.rollback()
        logger.exception('Receipt inspection update failed')
        return jsonify({'error': 'Failed to update receipt inspection'}), 500
