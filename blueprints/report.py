from flask import Blueprint, render_template
from flask_login import login_required

report_bp = Blueprint('report', __name__, template_folder='templates')

@report_bp.route('/report')
@login_required
def report():
    return render_template('reports/report.html')