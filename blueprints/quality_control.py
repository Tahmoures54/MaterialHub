from flask import Blueprint, render_template, request, redirect, url_for, current_app
from flask_login import login_required, current_user
from models import db, QualityControl
from forms.material_forms import QualityControlForm
import logging

logger = logging.getLogger(__name__)

quality_control_bp = Blueprint("quality_control", __name__, url_prefix="/quality_control", template_folder='templates')

@quality_control_bp.route('/')
@login_required
def quality_control():
    logger.info("Accessing quality control dashboard")
    return render_template('quality/quality_control.html', mode='dashboard')

@quality_control_bp.route('/get_quality_controls')
@login_required
def get_quality_controls():
    try:
        quality_controls = QualityControl.query.all()
        logger.info("Fetched quality control records from database")
        return render_template('quality/quality_control.html', mode='list', quality_controls=quality_controls)
    except Exception as e:
        logger.error(f"Error fetching quality controls: {e}")
        return render_template('errors/500.html'), 500

@quality_control_bp.route('/create_quality_control', methods=['GET', 'POST'])
@login_required
def create_quality_control():
    form = QualityControlForm()
    if form.validate_on_submit():
        try:
            quality_control = QualityControl(
                order_id=form.order_id.data,
                user_id=current_user.id,
                status=form.status.data,
                remarks=form.remarks.data
            )
            db.session.add(quality_control)
            db.session.commit()
            logger.info("Created new quality control record")
            return redirect(url_for('quality_control.quality_control'))
        except Exception as e:
            logger.error(f"Error creating quality control: {e}")
            return render_template('errors/500.html'), 500
    return render_template('quality/quality_control.html', mode='create', form=form)