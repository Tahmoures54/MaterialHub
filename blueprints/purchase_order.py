from flask import Blueprint, render_template, request, redirect, url_for, current_app
from flask_login import login_required, current_user
from models import db, PurchaseOrder
from forms.material_forms import PurchaseOrderForm
import logging

logger = logging.getLogger(__name__)

purchase_order_bp = Blueprint("purchase_order", __name__, url_prefix="/purchase_order", template_folder='templates')

@purchase_order_bp.route('/')
@login_required
def purchase_order():
    logger.info("Accessing purchase order dashboard")
    return render_template('purchase_order.html', mode='dashboard')

@purchase_order_bp.route('/get_purchase_orders')
@login_required
def get_purchase_orders():
    try:
        purchase_orders = PurchaseOrder.query.all()
        logger.info("Fetched purchase orders from database")
        return render_template('purchase_order.html', mode='list', purchase_orders=purchase_orders)
    except Exception as e:
        logger.error(f"Error fetching purchase orders: {e}")
        return render_template('500.html'), 500

@purchase_order_bp.route('/create_purchase_order', methods=['GET', 'POST'])
@login_required
def create_purchase_order():
    form = PurchaseOrderForm()
    if form.validate_on_submit():
        try:
            purchase_order = PurchaseOrder(
                order_no=form.order_no.data,
                project_id=form.project_id.data,
                user_id=current_user.id,
                supplier_id=form.supplier_id.data,
                total_price=form.total_price.data,
                status=PurchaseOrderStatus.pending
            )
            db.session.add(purchase_order)
            db.session.commit()
            logger.info("Created new purchase order")
            return redirect(url_for('purchase_order.purchase_order'))
        except Exception as e:
            logger.error(f"Error creating purchase order: {e}")
            return render_template('500.html'), 500
    return render_template('purchase_order.html', mode='create', form=form)