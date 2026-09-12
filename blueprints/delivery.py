from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from models import db, Delivery, DeliveryStatus, AccessLevel
from forms.material_forms import DeliveryForm
from utils import generate_next_delivery_id, parse_enum
import logging

logger = logging.getLogger(__name__)

delivery_bp = Blueprint("delivery", __name__, template_folder='templates')


def _company_deliveries():
    query = Delivery.query
    if not current_user.is_admin:
        query = query.filter_by(company_name=current_user.company_name)
    return query


@delivery_bp.route('/delivery_order')
@login_required
def delivery_order():
    logger.info("Accessing delivery order dashboard")
    return render_template('warehouse/delivery_order.html', mode='dashboard')


@delivery_bp.route('/get_deliveries')
@login_required
def get_deliveries():
    try:
        deliveries = _company_deliveries().order_by(Delivery.updated_at.desc()).all()
        logger.info("Fetched delivery records from database")
        return render_template('warehouse/delivery_order.html', mode='list', deliveries=deliveries)
    except Exception as e:
        logger.error(f"Error fetching deliveries: {e}")
        return render_template('errors/500.html'), 500


@delivery_bp.route('/create_delivery', methods=['GET', 'POST'])
@login_required
def create_delivery():
    if current_user.access_level not in (AccessLevel.delivery, AccessLevel.warehouse, AccessLevel.project_manager) and not current_user.is_admin:
        flash('You do not have permission to create deliveries.', 'danger')
        return redirect(url_for('delivery.delivery_order'))
    form = DeliveryForm()
    if form.validate_on_submit():
        try:
            delivery = Delivery(
                order_id=form.order_id.data,
                user_id=current_user.id,
                delivery_id=generate_next_delivery_id(current_user.company_name),
                status=parse_enum(DeliveryStatus, form.status.data, DeliveryStatus.pending),
                remarks=form.remarks.data,
                company_name=current_user.company_name,
            )
            db.session.add(delivery)
            db.session.commit()
            logger.info("Created new delivery")
            flash('Delivery created.', 'success')
            return redirect(url_for('delivery.delivery_order'))
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error creating delivery: {e}")
            return render_template('errors/500.html'), 500
    return render_template('warehouse/delivery_order.html', mode='create', form=form)
