from flask import Blueprint, render_template, request, redirect, url_for
from flask_login import login_required, current_user
from forms.material_forms import MaterialMarketplaceForm
from data.country_codes import COUNTRY_CODES
from models import db, AccessLevel
from datetime import datetime

supplier_bp = Blueprint("supplier", __name__, template_folder='templates')

@supplier_bp.route('/supplier_dashboard')
@login_required
def supplier_dashboard():
    """Render the supplier dashboard for users with supplier access level."""
    if current_user.access_level != AccessLevel.supplier:
        return redirect(url_for('auth.home'))
    return render_template('supplier_dashboard.html', current_year=datetime.now().year)

@supplier_bp.route('/material_marketplace', methods=['GET', 'POST'])
@login_required
def material_marketplace():
    """Render the material marketplace page for suppliers."""
    if current_user.access_level != AccessLevel.supplier:
        return redirect(url_for('auth.home'))

    form = MaterialMarketplaceForm()
    
    # Sample materials (replace with database query in production)
    materials = [
        {"id": 1, "name": "Steel Beam", "price": 500, "unit": "ton", "country_code": "IR"},
        {"id": 2, "name": "Concrete Mix", "price": 100, "unit": "cubic meter", "country_code": "US"},
        {"id": 3, "name": "Copper Wire", "price": 5, "unit": "meter", "country_code": "DE"},
        {"id": 4, "name": "Aluminum Sheet", "price": 800, "unit": "kg", "country_code": "AE"},
        {"id": 5, "name": "Plastic Pipe", "price": 20, "unit": "meter", "country_code": "TR"},
        {"id": 6, "name": "Cement", "price": 70, "unit": "ton", "country_code": "PK"},
    ]

    search_query = request.args.get('search', '').lower()
    country_filter = request.args.get('country', '')
    
    if search_query or country_filter:
        filtered_materials = []
        for material in materials:
            if (search_query in material['name'].lower() or not search_query) and \
               (material['country_code'] == country_filter or not country_filter):
                filtered_materials.append(material)
        materials = filtered_materials

    COUNTRY_NAMES_BY_CODE = {code: name for name, code in COUNTRY_CODES.items()}

    return render_template('material_marketplace.html', 
                         form=form, 
                         materials=materials, 
                         COUNTRY_NAMES_BY_CODE=COUNTRY_NAMES_BY_CODE,
                         current_year=datetime.now().year)

@supplier_bp.route('/tender')
@login_required
def tender():
    """Render the tender page for suppliers."""
    if current_user.access_level != AccessLevel.supplier:
        return redirect(url_for('auth.home'))
    return render_template('tender.html', current_year=datetime.now().year)