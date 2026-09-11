from flask import Blueprint, render_template, request, redirect, url_for, current_app, flash
from flask_login import login_required, current_user
from models import db, PurchaseOrder, PurchaseOrderStatus, AccessLevel
from forms.material_forms import PurchaseOrderForm
from utils import generate_next_po_no
import logging

logger = logging.getLogger(__name__)

purchase_order_bp = Blueprint("purchase_order", __name__, template_folder='templates')


def _company_pos():
    query = PurchaseOrder.query
    if not current_user.is_admin:
        query = query.filter_by(company_name=current_user.company_name)
    return query


@purchase_order_bp.route('/')
@login_required
def purchase_order():
    logger.info("Accessing purchase order dashboard")
    return render_template('procurement/purchase_order.html', mode='dashboard')


@purchase_order_bp.route('/get_purchase_orders')
@login_required
def get_purchase_orders():
    try:
        purchase_orders = _company_pos().order_by(PurchaseOrder.created_at.desc()).all()
        logger.info("Fetched purchase orders from database")
        return render_template('procurement/purchase_order.html', mode='list', purchase_orders=purchase_orders)
    except Exception as e:
        logger.error(f"Error fetching purchase orders: {e}")
        return render_template('errors/500.html'), 500


@purchase_order_bp.route('/create_purchase_order', methods=['GET', 'POST'])
@login_required
def create_purchase_order():
    if current_user.access_level not in (AccessLevel.purchase, AccessLevel.project_manager) and not current_user.is_admin:
        flash('Only procurement users can create purchase orders.', 'danger')
        return redirect(url_for('purchase_order.purchase_order'))
    form = PurchaseOrderForm()
    if form.validate_on_submit():
        try:
            purchase_order = PurchaseOrder(
                order_no=form.order_no.data or generate_next_po_no(current_user.company_name),
                project_id=form.project_id.data,
                user_id=current_user.id,
                supplier_id=form.supplier_id.data,
                total_price=form.total_price.data,
                status=PurchaseOrderStatus.pending,
                company_name=current_user.company_name,
            )
            db.session.add(purchase_order)
            db.session.commit()
            logger.info("Created new purchase order")
            flash('Purchase order created.', 'success')
            return redirect(url_for('purchase_order.purchase_order'))
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error creating purchase order: {e}")
            return render_template('errors/500.html'), 500
    return render_template('procurement/purchase_order.html', mode='create', form=form)
