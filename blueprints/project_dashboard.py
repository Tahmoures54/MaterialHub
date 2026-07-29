from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from sqlalchemy.exc import IntegrityError
from models import db, User, AccessLevel
from forms.user_forms import AddUserForm
import pyotp
import qrcode
from io import BytesIO
import base64
import logging
from datetime import datetime

project_dashboard_bp = Blueprint('project_dashboard', __name__, template_folder='templates')
logger = logging.getLogger(__name__)

def generate_qr_code(totp_uri):
    """Generate QR code for TOTP URI as base64 string."""
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(totp_uri)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buffered = BytesIO()
    img.save(buffered, format="PNG")
    qr_code = base64.b64encode(buffered.getvalue()).decode('utf-8')
    buffered.close()
    return qr_code

@project_dashboard_bp.route('/dashboard', methods=['GET', 'POST'])
@login_required
def dashboard():
    """Render the project dashboard and handle team management."""
    if current_user.access_level != AccessLevel.project_manager:
        flash('Only project managers can access this dashboard.', 'danger')
        return redirect(url_for('auth.home'))

    add_user_form = AddUserForm()
    qr_code = None
    totp_secret = None

    # Fetch company team
    company_team = User.query.filter_by(company_name=current_user.company_name).all()
    required_roles = [
        'engineering_manager', 'purchase_manager', 'quality_manager',
        'delivery_manager', 'warehouse_manager'
    ]
    role_names = [u.access_level.name for u in company_team]
    has_project_manager = 'project_manager' in role_names
    has_all_managers = all(r in role_names for r in required_roles)

    if request.method == 'POST' and 'add_user' in request.form and add_user_form.validate_on_submit():
        try:
            totp_secret = pyotp.random_base32()
            totp_uri = pyotp.totp.TOTP(totp_secret).provisioning_uri(
                name=add_user_form.new_email.data,
                issuer_name="MaterialHub"
            )
            qr_code = generate_qr_code(totp_uri)
            new_user = User(
                full_name=add_user_form.new_full_name.data,
                company_email=add_user_form.new_email.data,
                company_phone=add_user_form.new_phone.data,
                company_name=current_user.company_name,
                company_address=current_user.company_address,
                country=current_user.country,
                access_level=AccessLevel[add_user_form.new_access_level.data],
                totp_secret=totp_secret,
                qr_code_base64=qr_code,
                totp_confirmed=False,
                is_admin=False,
                store_name=None,
                project_id=None
            )
            db.session.add(new_user)
            db.session.commit()
            logger.info(f"New team member added: {new_user.company_email} by {current_user.company_email} (ID: {current_user.id}, IP: {request.remote_addr})")
            flash("New team member added. Share the TOTP credentials with them.", "success")
        except IntegrityError as e:
            db.session.rollback()
            logger.warning(f"Failed to add team member: {str(e)} (IP: {request.remote_addr})")
            if 'company_email' in str(e).lower():
                flash('This email is already registered.', 'danger')
            elif 'company_phone' in str(e).lower():
                flash('This phone number is already in use.', 'danger')
            else:
                flash('A database error occurred. Please try again.', 'danger')
        except ValueError as e:
            db.session.rollback()
            logger.warning(f"Validation error adding team member: {str(e)} (IP: {request.remote_addr})")
            flash(f"Invalid input: {str(e)}", 'danger')
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error adding team member: {str(e)} (IP: {request.remote_addr})")
            flash('An unexpected error occurred. Please try again.', 'danger')

    return render_template(
        'project_dashboard.html',
        add_user_form=add_user_form,
        company_team=company_team,
        has_project_manager=has_project_manager,
        has_all_managers=has_all_managers,
        qr_code=qr_code,
        totp_secret=totp_secret,
        current_year=datetime.now().year
    )

@project_dashboard_bp.route('/edit_user', methods=['POST'])
@login_required
def edit_user():
    """Handle editing a team member."""
    if current_user.access_level != AccessLevel.project_manager:
        flash('Only project managers can edit team members.', 'danger')
        return redirect(url_for('project_dashboard.dashboard'))

    user_id = request.form.get('user_id')
    user = User.query.get_or_404(user_id)
    
    if user.company_name != current_user.company_name:
        flash('You can only edit users from your company.', 'danger')
        return redirect(url_for('project_dashboard.dashboard'))

    form = AddUserForm()
    if form.validate_on_submit():
        try:
            user.full_name = form.new_full_name.data
            user.company_email = form.new_email.data
            user.company_phone = form.new_phone.data
            user.access_level = AccessLevel[form.new_access_level.data]
            db.session.commit()
            logger.info(f"Team member updated: {user.company_email} by {current_user.company_email} (ID: {current_user.id}, IP: {request.remote_addr})")
            flash('Team member updated successfully.', 'success')
        except IntegrityError as e:
            db.session.rollback()
            logger.warning(f"Failed to update team member: {str(e)} (IP: {request.remote_addr})")
            if 'company_email' in str(e).lower():
                flash('This email is already registered.', 'danger')
            elif 'company_phone' in str(e).lower():
                flash('This phone number is already in use.', 'danger')
            else:
                flash('A database error occurred. Please try again.', 'danger')
        except ValueError as e:
            db.session.rollback()
            logger.warning(f"Validation error updating team member: {str(e)} (IP: {request.remote_addr})")
            flash(f"Invalid input: {str(e)}", 'danger')
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error updating team member: {str(e)} (IP: {request.remote_addr})")
            flash('An unexpected error occurred. Please try again.', 'danger')
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f"Error in {field}: {error}", 'danger')

    return redirect(url_for('project_dashboard.dashboard'))

@project_dashboard_bp.route('/delete_user', methods=['POST'])
@login_required
def delete_user():
    """Handle deleting a team member."""
    if current_user.access_level != AccessLevel.project_manager:
        flash('Only project managers can delete team members.', 'danger')
        return redirect(url_for('project_dashboard.dashboard'))

    user_id = request.form.get('user_id')
    user = User.query.get_or_404(user_id)
    
    if user.company_name != current_user.company_name:
        flash('You can only delete users from your company.', 'danger')
        return redirect(url_for('project_dashboard.dashboard'))
    
    if user.access_level == AccessLevel.project_manager:
        flash('Cannot delete a project manager.', 'danger')
        return redirect(url_for('project_dashboard.dashboard'))

    try:
        db.session.delete(user)
        db.session.commit()
        logger.info(f"Team member deleted: {user.company_email} by {current_user.company_email} (ID: {current_user.id}, IP: {request.remote_addr})")
        flash('Team member deleted successfully.', 'success')
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error deleting team member: {str(e)} (IP: {request.remote_addr})")
        flash('An error occurred while deleting the team member.', 'danger')

    return redirect(url_for('project_dashboard.dashboard'))