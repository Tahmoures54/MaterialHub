from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from models import (
    db, PurchaseOrder, PurchaseOrderStatus, AccessLevel,
    MaterialRequisition, ApprovalStatus, Tender, TenderStatus, Bid, BidStatus,
    ValidationError, PurchaseOrderItem,
)
from forms.material_forms import PurchaseOrderForm
from utils import generate_next_po_no, generate_next_tender_no, tenant_query
import logging
from datetime import date

logger = logging.getLogger(__name__)

purchase_order_bp = Blueprint("purchase_order", __name__, template_folder='templates')


def _company_pos():
    """Tenant-scoped PO query. Admins remain scoped to their own company."""
    return tenant_query(PurchaseOrder, allow_admin=False)


def _can_manage_procurement():
    return (
        current_user.is_admin
        or current_user.access_level in (AccessLevel.purchase, AccessLevel.project_manager)
    )


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
    if not _can_manage_procurement():
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


# ---------------------------------------------------------------------------
# Tender management (buyer / procurement side)
# ---------------------------------------------------------------------------

@purchase_order_bp.route('/tenders', methods=['GET', 'POST'])
@login_required
def manage_tenders():
    """List company tenders; POST creates a new tender from an approved MR."""
    if not _can_manage_procurement():
        flash('Only procurement users can manage tenders.', 'danger')
        return redirect(url_for('role_workspace.my_workspace'))

    if request.method == 'POST':
        return _create_tender_from_form()

    tenders = (
        tenant_query(Tender)
        .order_by(Tender.created_at.desc())
        .limit(100)
        .all()
    )
    open_tender_mr_ids = {
        t.material_requisition_id
        for t in tenant_query(Tender).filter_by(status=TenderStatus.open).all()
    }
    eligible_mrs = (
        tenant_query(MaterialRequisition)
        .filter(MaterialRequisition.status == ApprovalStatus.approved)
        .order_by(MaterialRequisition.created_at.desc())
        .limit(200)
        .all()
    )
    eligible_mrs = [mr for mr in eligible_mrs if mr.id not in open_tender_mr_ids]

    return render_template(
        'procurement/tender_manage.html',
        tenders=tenders,
        eligible_mrs=eligible_mrs,
    )


def _create_tender_from_form():
    try:
        mr_id = int(request.form.get('material_requisition_id') or 0)
        mr = tenant_query(MaterialRequisition).filter_by(id=mr_id).first()
        if not mr:
            flash('Material requisition not found.', 'danger')
            return redirect(url_for('purchase_order.manage_tenders'))
        if mr.status != ApprovalStatus.approved:
            flash('Only approved requisitions can be put out to tender.', 'danger')
            return redirect(url_for('purchase_order.manage_tenders'))
        if not mr.project_id:
            flash('Requisition must be linked to a project.', 'danger')
            return redirect(url_for('purchase_order.manage_tenders'))

        existing_open = tenant_query(Tender).filter_by(
            material_requisition_id=mr.id, status=TenderStatus.open
        ).first()
        if existing_open:
            flash(f'An open tender already exists: {existing_open.tender_no}', 'warning')
            return redirect(url_for('purchase_order.manage_tenders'))

        tender = Tender(
            tender_no=generate_next_tender_no(current_user.company_name),
            project_id=mr.project_id,
            material_requisition_id=mr.id,
            status=TenderStatus.open,
            created_by=current_user.id,
            company_name=current_user.company_name,
        )
        db.session.add(tender)
        db.session.commit()
        flash(f'Tender {tender.tender_no} opened.', 'success')
    except (ValidationError, ValueError, TypeError) as exc:
        db.session.rollback()
        flash(str(exc), 'danger')
    except Exception:
        db.session.rollback()
        logger.exception('Failed to create tender')
        flash('Failed to create tender.', 'danger')
    return redirect(url_for('purchase_order.manage_tenders'))


@purchase_order_bp.route('/tenders/<int:tender_id>', methods=['GET', 'POST'])
@login_required
def tender_detail(tender_id):
    """View bids on a tender; accept or reject individual bids."""
    if not _can_manage_procurement():
        flash('Only procurement users can evaluate tenders.', 'danger')
        return redirect(url_for('role_workspace.my_workspace'))

    tender = tenant_query(Tender).filter_by(id=tender_id).first_or_404()

    if request.method == 'POST':
        return _handle_bid_decision(tender)

    bids = (
        Bid.query.filter_by(tender_id=tender.id)
        .order_by(Bid.bid_amount.asc(), Bid.created_at.asc())
        .all()
    )
    return render_template(
        'procurement/tender_detail.html',
        tender=tender,
        bids=bids,
        mr=tender.material_requisition,
    )


def _handle_bid_decision(tender):
    action = (request.form.get('action') or '').strip()
    bid_id = int(request.form.get('bid_id') or 0)
    bid = Bid.query.filter_by(id=bid_id, tender_id=tender.id).first()

    try:
        if action == 'close_tender':
            tender.status = TenderStatus.closed
            db.session.commit()
            flash(f'Tender {tender.tender_no} closed.', 'success')
            return redirect(url_for('purchase_order.manage_tenders'))

        if action == 'cancel_tender':
            tender.status = TenderStatus.cancelled
            for b in Bid.query.filter_by(tender_id=tender.id, status=BidStatus.pending).all():
                b.status = BidStatus.rejected
            db.session.commit()
            flash(f'Tender {tender.tender_no} cancelled.', 'success')
            return redirect(url_for('purchase_order.manage_tenders'))

        if not bid:
            flash('Bid not found.', 'danger')
            return redirect(url_for('purchase_order.tender_detail', tender_id=tender.id))

        if action == 'reject_bid':
            bid.status = BidStatus.rejected
            db.session.commit()
            flash('Bid rejected.', 'success')

        elif action == 'accept_bid':
            if tender.status != TenderStatus.open:
                flash('Tender is not open.', 'danger')
                return redirect(url_for('purchase_order.tender_detail', tender_id=tender.id))

            bid.status = BidStatus.accepted
            for other in Bid.query.filter(
                Bid.tender_id == tender.id,
                Bid.id != bid.id,
                Bid.status == BidStatus.pending,
            ).all():
                other.status = BidStatus.rejected

            tender.status = TenderStatus.closed
            mr = tender.material_requisition

            po = PurchaseOrder(
                order_no=generate_next_po_no(current_user.company_name),
                project_id=tender.project_id,
                user_id=current_user.id,
                supplier_id=bid.supplier_id,
                total_price=bid.bid_amount,
                status=PurchaseOrderStatus.issued,
                issued_date=date.today(),
                company_name=current_user.company_name,
            )
            db.session.add(po)
            db.session.flush()

            if mr and getattr(mr, 'material_id', None):
                qty = float(mr.quantity or 1)
                unit_price = float(bid.bid_amount) / max(qty, 1e-9)
                item = PurchaseOrderItem(
                    purchase_order_id=po.id,
                    material_requisition_id=mr.id,
                    material_id=mr.material_id,
                    quantity=qty,
                    unit_price=unit_price,
                )
                db.session.add(item)

            db.session.commit()
            flash(
                f'Bid accepted. Purchase order {po.order_no} issued to supplier.',
                'success',
            )
            return redirect(url_for('purchase_order.get_purchase_orders'))

        else:
            flash('Unknown action.', 'warning')

    except Exception:
        db.session.rollback()
        logger.exception('Bid decision failed')
        flash('Operation failed.', 'danger')

    return redirect(url_for('purchase_order.tender_detail', tender_id=tender.id))


@purchase_order_bp.route('/api/tenders', methods=['GET'])
@login_required
def api_list_tenders():
    if not _can_manage_procurement():
        return jsonify({'error': 'Forbidden'}), 403
    rows = tenant_query(Tender).order_by(Tender.created_at.desc()).limit(100).all()
    return jsonify([t.to_dict() for t in rows]), 200
