from flask import Blueprint, render_template, request, redirect, url_for
from flask_login import login_required, current_user
from forms.material_forms import MaterialMarketplaceForm
from data.country_codes import COUNTRY_NAMES_BY_CODE
from models import SupplierMaterial, AccessLevel
from datetime import datetime

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
    search_query = request.args.get('search') or (form.search.data if form.validate_on_submit() else None)
    country_filter = request.args.get('country') or (form.country.data if form.validate_on_submit() else None)
    if search_query:
        query = query.filter(SupplierMaterial.material_name.ilike(f'%{search_query}%'))
    if country_filter:
        query = query.filter(SupplierMaterial.country_code == country_filter)
    materials = query.order_by(SupplierMaterial.updated_at.desc()).all()
    return render_template(
        'procurement/material_marketplace.html',
        form=form,
        materials=materials,
        COUNTRY_NAMES_BY_CODE=COUNTRY_NAMES_BY_CODE,
        current_year=datetime.now().year,
    )


@supplier_bp.route('/tender')
@login_required
def tender():
    """Render the tender page for suppliers."""
    if current_user.access_level != AccessLevel.supplier and not current_user.is_admin:
        return redirect(url_for('role_workspace.my_workspace'))
    return render_template('procurement/tender.html', current_year=datetime.now().year)
