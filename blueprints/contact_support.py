from flask import Blueprint, render_template
from flask_login import login_required

contact_support_bp = Blueprint('contact_support', __name__, template_folder='templates')

@contact_support_bp.route('/contact_support')
@login_required
def contact_support():
    return render_template('support/contact_support.html')