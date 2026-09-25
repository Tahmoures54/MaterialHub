"""Supplier workspace: catalog management, marketplace browsing and tender entry."""
from datetime import datetime

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from flask_wtf.csrf import validate_csrf, CSRFError

from data.country_codes import COUNTRY_NAMES_BY_CODE, COUNTRY_CODES
from extensions import db
from forms.material_forms import MaterialMarketplaceForm
from models import (
    SupplierMaterial, AccessLevel, PurchaseOrder, PurchaseOrderStatus,
    Delivery, DeliveryStatus, Tender, TenderStatus, Bid, BidStatus, ValidationError,
)
from utils import tenant_query, compute_supplier_performance

supplier_bp = Blueprint("supplier", __name__, template_folder='templates')


def _require_supplier():
    """Return True when the current user may act as a supplier."""
    return (
        current_user.is_authenticated
        and (
            current_user.access_level == AccessLevel.supplier
            or current_user.is_admin
        )
    )


def _supplier_materials_query():
    """Materials owned by the logged-in supplier (by user_id)."""
    return SupplierMaterial.query.filter_by(user_id=current_user.id)


def _query_number(name, cast):
    value = (request.args.get(name) or '').strip()
    if not value:
        return None
    try:
        return cast(value)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Supplier dashboard
# ---------------------------------------------------------------------------

@supplier_bp.route('/supplier_dashboard', methods=['GET', 'POST'])
@login_required
def supplier_dashboard():
    """Supplier home: manage catalog, see assigned POs and open tenders."""
    if not _require_supplier():
        flash('Supplier access required.', 'danger')
        return redirect(url_for('role_workspace.my_workspace'))

    if request.method == 'POST':
        return _handle_dashboard_post()

    materials = _supplier_materials_query().order_by(SupplierMaterial.updated_at.desc()).all()

    purchase_orders = (
        PurchaseOrder.query
        .filter_by(supplier_id=current_user.id)
        .filter(PurchaseOrder.status.in_([
            PurchaseOrderStatus.pending,
            PurchaseOrderStatus.issued,
            PurchaseOrderStatus.delivered,
        ]))
        .order_by(PurchaseOrder.created_at.desc())
        .limit(50)
        .all()
    )

    open_tenders = (
        Tender.query
        .filter_by(status=TenderStatus.open)
        .order_by(Tender.created_at.desc())
        .limit(30)
        .all()
    )

    my_bids = (
        Bid.query
        .filter_by(supplier_id=current_user.id)
        .order_by(Bid.created_at.desc())
        .limit(30)
        .all()
    )

    deliveries = (
        Delivery.query
        .join(PurchaseOrder, Delivery.order_id == PurchaseOrder.id)
        .filter(PurchaseOrder.supplier_id == current_user.id)
        .order_by(Delivery.updated_at.desc())
        .limit(30)
        .all()
    )

    stats = {
        'materials': len(materials),
        'open_pos': sum(1 for po in purchase_orders if po.status in (
            PurchaseOrderStatus.pending, PurchaseOrderStatus.issued)),
        'open_tenders': len(open_tenders),
        'my_bids': len(my_bids),
        'deliveries': len(deliveries),
    }

    performance = compute_supplier_performance(
        current_user.id, buyer_company=None, persist=True
    )
    stats['otif'] = performance.get('otif_score', 0)
    stats['overall'] = performance.get('overall_score', 0)

    return render_template(
        'dashboard/supplier_dashboard.html',
        materials=materials,
        purchase_orders=purchase_orders,
        open_tenders=open_tenders,
        my_bids=my_bids,
        deliveries=deliveries,
        stats=stats,
        performance=performance,
        full_name=current_user.full_name,
        company_name=current_user.company_name,
        countries=sorted(COUNTRY_CODES.items(), key=lambda x: x[0]),
        current_year=datetime.now().year,
    )


def _handle_dashboard_post():
    """Create / update / delete catalog rows from the dashboard form."""
    action = (request.form.get('action') or '').strip()

    try:
        if action == 'add_material':
            material = SupplierMaterial(
                user_id=current_user.id,
                material_name=(request.form.get('material_name') or '').strip(),
                material_type=(request.form.get('material_type') or 'General').strip(),
                price=float(request.form.get('price') or 0),
                available_qty=float(request.form.get('available_qty') or 0),
                unit=(request.form.get('unit') or 'EA').strip(),
                delivery_time_days=int(request.form['delivery_time_days'])
                    if request.form.get('delivery_time_days') else None,
                country_code=(request.form.get('country_code') or current_user.country or '').strip()[:2] or None,
                company_name=current_user.company_name,
            )
            db.session.add(material)
            db.session.commit()
            flash('Material listed in your catalog.', 'success')

        elif action == 'update_material':
            material_id = int(request.form.get('material_id') or 0)
            material = _supplier_materials_query().filter_by(id=material_id).first()
            if not material:
                flash('Material not found.', 'danger')
            else:
                if request.form.get('material_name'):
                    material.material_name = request.form.get('material_name').strip()
                if request.form.get('material_type'):
                    material.material_type = request.form.get('material_type').strip()
                if request.form.get('price') not in (None, ''):
                    material.price = float(request.form.get('price'))
                if request.form.get('available_qty') not in (None, ''):
                    material.available_qty = float(request.form.get('available_qty'))
                if request.form.get('unit'):
                    material.unit = request.form.get('unit').strip()
                if request.form.get('delivery_time_days') not in (None, ''):
                    material.delivery_time_days = int(request.form.get('delivery_time_days'))
                if request.form.get('country_code'):
                    material.country_code = request.form.get('country_code').strip()[:2]
                db.session.commit()
                flash('Material updated.', 'success')

        elif action == 'delete_material':
            material_id = int(request.form.get('material_id') or 0)
            material = _supplier_materials_query().filter_by(id=material_id).first()
            if not material:
                flash('Material not found.', 'danger')
            else:
                db.session.delete(material)
                db.session.commit()
                flash('Material removed from catalog.', 'success')

        elif action == 'submit_bid':
            tender_id = int(request.form.get('tender_id') or 0)
            bid_amount = float(request.form.get('bid_amount') or 0)
            tender = Tender.query.filter_by(id=tender_id, status=TenderStatus.open).first()
            if not tender:
                flash('Tender not found or closed.', 'danger')
            elif bid_amount <= 0:
                flash('Bid amount must be positive.', 'danger')
            else:
                existing = Bid.query.filter_by(
                    tender_id=tender.id, supplier_id=current_user.id
                ).first()
                if existing:
                    existing.bid_amount = bid_amount
                    existing.status = BidStatus.pending
                    flash('Bid updated.', 'success')
                else:
                    bid = Bid(
                        tender_id=tender.id,
                        supplier_id=current_user.id,
                        bid_amount=bid_amount,
                        status=BidStatus.pending,
                        company_name=current_user.company_name,
                    )
                    db.session.add(bid)
                    flash('Bid submitted.', 'success')
                db.session.commit()
        else:
            flash('Unknown action.', 'warning')

    except (ValidationError, ValueError, TypeError) as exc:
        db.session.rollback()
        flash(str(exc), 'danger')
    except Exception:
        db.session.rollback()
        flash('Operation failed. Please try again.', 'danger')

    return redirect(url_for('supplier.supplier_dashboard'))


# ---------------------------------------------------------------------------
# JSON API for catalog (used by richer UIs later)
# ---------------------------------------------------------------------------

@supplier_bp.route('/api/supplier/materials', methods=['GET'])
@login_required
def api_list_materials():
    if not _require_supplier():
        return jsonify({'error': 'Forbidden'}), 403
    rows = _supplier_materials_query().order_by(SupplierMaterial.updated_at.desc()).all()
    return jsonify([r.to_dict() for r in rows]), 200


@supplier_bp.route('/api/supplier/materials', methods=['POST'])
@login_required
def api_create_material():
    if not _require_supplier():
        return jsonify({'error': 'Forbidden'}), 403
    try:
        data = request.get_json(force=True) or {}
        validate_csrf(data.get('csrf_token'))
        material = SupplierMaterial(
            user_id=current_user.id,
            material_name=(data.get('material_name') or '').strip(),
            material_type=(data.get('material_type') or 'General').strip(),
            price=float(data.get('price') or 0),
            available_qty=float(data.get('available_qty') or 0),
            unit=(data.get('unit') or 'EA').strip(),
            delivery_time_days=int(data['delivery_time_days']) if data.get('delivery_time_days') else None,
            country_code=(data.get('country_code') or current_user.country or '').strip()[:2] or None,
            company_name=current_user.company_name,
        )
        db.session.add(material)
        db.session.commit()
        return jsonify(material.to_dict()), 201
    except CSRFError:
        return jsonify({'error': 'Invalid CSRF token'}), 403
    except (ValidationError, ValueError, TypeError) as exc:
        db.session.rollback()
        return jsonify({'error': str(exc)}), 400
    except Exception:
        db.session.rollback()
        return jsonify({'error': 'Failed to create material'}), 500


@supplier_bp.route('/api/supplier/materials/<int:material_id>', methods=['PUT', 'DELETE'])
@login_required
def api_mutate_material(material_id):
    if not _require_supplier():
        return jsonify({'error': 'Forbidden'}), 403
    material = _supplier_materials_query().filter_by(id=material_id).first()
    if not material:
        return jsonify({'error': 'Not found'}), 404
    try:
        data = request.get_json(silent=True) or {}
        validate_csrf(data.get('csrf_token') or request.headers.get('X-CSRFToken'))
        if request.method == 'DELETE':
            db.session.delete(material)
            db.session.commit()
            return jsonify({'message': 'Deleted'}), 200
        if data.get('material_name'):
            material.material_name = data['material_name'].strip()
        if data.get('material_type'):
            material.material_type = data['material_type'].strip()
        if data.get('price') is not None:
            material.price = float(data['price'])
        if data.get('available_qty') is not None:
            material.available_qty = float(data['available_qty'])
        if data.get('unit'):
            material.unit = data['unit'].strip()
        if 'delivery_time_days' in data:
            material.delivery_time_days = int(data['delivery_time_days']) if data['delivery_time_days'] is not None else None
        if data.get('country_code'):
            material.country_code = data['country_code'].strip()[:2]
        db.session.commit()
        return jsonify(material.to_dict()), 200
    except CSRFError:
        return jsonify({'error': 'Invalid CSRF token'}), 403
    except (ValidationError, ValueError, TypeError) as exc:
        db.session.rollback()
        return jsonify({'error': str(exc)}), 400
    except Exception:
        db.session.rollback()
        return jsonify({'error': 'Failed to update material'}), 500


# ---------------------------------------------------------------------------
# OTIF / performance API
# ---------------------------------------------------------------------------

@supplier_bp.route('/api/supplier/performance', methods=['GET'])
@login_required
def api_supplier_performance():
    if not _require_supplier():
        return jsonify({'error': 'Forbidden'}), 403
    data = compute_supplier_performance(current_user.id, buyer_company=None, persist=True)
    return jsonify(data), 200


# ---------------------------------------------------------------------------
# Public marketplace (buyers browse all suppliers)
# ---------------------------------------------------------------------------

@supplier_bp.route('/material_marketplace', methods=['GET', 'POST'])
@login_required
def material_marketplace():
    """Browse the cross-tenant supplier catalog."""
    form = MaterialMarketplaceForm()
    query = SupplierMaterial.query
    search_query = (request.args.get('search') or '').strip()
    country_filter = request.args.get('country') or ''
    type_filter = (request.args.get('material_type') or '').strip()
    unit_filter = (request.args.get('unit') or '').strip()
    supplier_filter = (request.args.get('supplier') or '').strip()
    min_price = _query_number('min_price', float)
    max_price = _query_number('max_price', float)
    min_qty = _query_number('min_qty', float)
    max_delivery = _query_number('max_delivery', int)
    sort_filter = request.args.get('sort') or 'updated'

    if search_query:
        query = query.filter(SupplierMaterial.material_name.ilike(f'%{search_query}%'))
    if country_filter:
        query = query.filter(SupplierMaterial.country_code == country_filter)
    if type_filter:
        query = query.filter(SupplierMaterial.material_type.ilike(f'%{type_filter}%'))
    if unit_filter:
        query = query.filter(SupplierMaterial.unit.ilike(f'%{unit_filter}%'))
    if supplier_filter:
        query = query.filter(SupplierMaterial.company_name.ilike(f'%{supplier_filter}%'))
    if min_price is not None:
        query = query.filter(SupplierMaterial.price >= min_price)
    if max_price is not None:
        query = query.filter(SupplierMaterial.price <= max_price)
    if min_qty is not None:
        query = query.filter(SupplierMaterial.available_qty >= min_qty)
    if max_delivery is not None:
        query = query.filter(
            db.or_(
                SupplierMaterial.delivery_time_days.is_(None),
                SupplierMaterial.delivery_time_days <= max_delivery,
            )
        )

    sort_map = {
        'price_asc': SupplierMaterial.price.asc(),
        'price_desc': SupplierMaterial.price.desc(),
        'qty_desc': SupplierMaterial.available_qty.desc(),
        'delivery_asc': SupplierMaterial.delivery_time_days.asc(),
        'updated': SupplierMaterial.updated_at.desc(),
    }
    materials = query.order_by(sort_map.get(sort_filter, SupplierMaterial.updated_at.desc())).limit(500).all()
    filter_options = {
        'types': [x[0] for x in db.session.query(SupplierMaterial.material_type).distinct().order_by(SupplierMaterial.material_type).all() if x[0]],
        'units': [x[0] for x in db.session.query(SupplierMaterial.unit).distinct().order_by(SupplierMaterial.unit).all() if x[0]],
        'suppliers': [x[0] for x in db.session.query(SupplierMaterial.company_name).distinct().order_by(SupplierMaterial.company_name).all() if x[0]],
    }
    return render_template(
        'procurement/material_marketplace.html',
        form=form,
        materials=materials,
        COUNTRY_NAMES_BY_CODE=COUNTRY_NAMES_BY_CODE,
        current_year=datetime.now().year,
        filter_options=filter_options,
    )


@supplier_bp.route('/tender')
@login_required
def tender():
    """List open tenders and allow suppliers to place bids."""
    if not _require_supplier() and current_user.access_level not in (
        AccessLevel.purchase, AccessLevel.project_manager
    ):
        return redirect(url_for('role_workspace.my_workspace'))

    tenders = (
        Tender.query
        .filter_by(status=TenderStatus.open)
        .order_by(Tender.created_at.desc())
        .limit(100)
        .all()
    )
    tender_rows = []
    for t in tenders:
        mr = t.material_requisition
        tender_rows.append({
            'id': t.id,
            'tender_no': t.tender_no,
            'material': mr.material_description if mr else t.tender_no,
            'quantity': mr.quantity if mr else None,
            'company': t.company_name,
            'status': t.status.value.title() if t.status else 'Open',
            'object': t,
        })

    return render_template(
        'procurement/tender.html',
        tenders=tender_rows,
        current_year=datetime.now().year,
    )
