from flask import Blueprint, render_template, redirect, url_for, flash
from flask_login import login_required, current_user
from models import User

admin_bp = Blueprint("admin", __name__)

@admin_bp.route('/admin', methods=['GET'])
@login_required
def admin():
    if not current_user.is_admin:
        flash('Administrator access is required.', 'danger')
        return redirect(url_for('role_workspace.my_workspace'))
    users = User.query.order_by(User.company_name.asc(), User.full_name.asc()).all()
    return render_template('admin/admin.html', users=users)
