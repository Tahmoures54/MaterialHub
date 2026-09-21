from flask import Blueprint, render_template, request, redirect, url_for
from flask_login import login_required, current_user
from forms.material_forms import MaterialMarketplaceForm
from data.country_codes import COUNTRY_NAMES_BY_CODE
from models import SupplierMaterial, AccessLevel
from extensions import db
from datetime import datetime


def _query_number(name, cast):
    value = (request.args.get(name) or '').strip()
    if not value:
        return None
    try:
        return cast(value)
    except (TypeError, ValueError):
        return None

supplier_bp = Blueprint("supplier", __name__, template_folder='templates')


@supplier_bp.route('/supplier_dashboard')
@login_required
def supplier_dashboard():
    """Render the supplier dashboard for users with supplier access level."""
    if current_user.access_level != AccessLevel.supplier:
        return redirect(url_for('role_workspace.my_workspace'))
    return redirect(url_for('role_workspace.my_workspace'))


@supplier_bp.route('/material_marketplace', methods=['GET', 'POST'])
@login_required
def material_marketplace():
    """Render the material marketplace page using live supplier catalog data."""
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
    materials = query.order_by(sort_map.get(sort_filter, SupplierMaterial.updated_at.desc())).all()
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
    """Render the tender page for suppliers."""
    if current_user.access_level != AccessLevel.supplier and not current_user.is_admin:
        return redirect(url_for('role_workspace.my_workspace'))
    return render_template('procurement/tender.html', current_year=datetime.now().year)
