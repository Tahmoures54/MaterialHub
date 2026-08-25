from flask import Blueprint, render_template, request, redirect, url_for, current_app
from flask_login import login_required, current_user
from models import db, Delivery
from forms.material_forms import DeliveryForm
import logging

logger = logging.getLogger(__name__)

delivery_bp = Blueprint("delivery", __name__, url_prefix="/delivery", template_folder='templates')

@delivery_bp.route('/delivery_order')
@login_required
def delivery_order():
    logger.info("Accessing delivery order dashboard")
    return render_template('warehouse/delivery_order.html', mode='dashboard')

@delivery_bp.route('/get_deliveries')
@login_required
def get_deliveries():
    try:
        deliveries = Delivery.query.all()
        logger.info("Fetched delivery records from database")
        return render_template('warehouse/delivery_order.html', mode='list', deliveries=deliveries)
    except Exception as e:
        logger.error(f"Error fetching deliveries: {e}")
        return render_template('errors/500.html'), 500

@delivery_bp.route('/create_delivery', methods=['GET', 'POST'])
@login_required
def create_delivery():
    form = DeliveryForm()
    if form.validate_on_submit():
        try:
            delivery = Delivery(
                order_id=form.order_id.data,
                user_id=current_user.id,
                status=form.status.data,
                remarks=form.remarks.data
            )
            db.session.add(delivery)
            db.session.commit()
            logger.info("Created new delivery")
            return redirect(url_for('delivery.delivery_order'))
        except Exception as e:
            logger.error(f"Error creating delivery: {e}")
            return render_template('errors/500.html'), 500
    return render_template('warehouse/delivery_order.html', mode='create', form=form)