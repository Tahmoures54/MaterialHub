import os
import logging
import random
from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request, session
from flask_login import login_user, logout_user, current_user, login_required
from sqlalchemy.exc import IntegrityError
from models import db, User, AccessLevel
from forms.auth_forms import RegisterForm, LoginForm, ResetPasswordRequestForm, ChangePasswordForm, ConfirmTOTPForm
from data.country_codes import COUNTRY_CODES
import pyotp
import qrcode
from io import BytesIO
import base64

auth_bp = Blueprint('auth', __name__)
logger = logging.getLogger(__name__)

def generate_qr_code(totp_uri):
    """Generate QR code for TOTP URI as base64 string."""
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(totp_uri)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buffered = BytesIO()
    img.save(buffered, format='PNG')
    return base64.b64encode(buffered.getvalue()).decode('utf-8')

@auth_bp.route('/')
def home():
    """Render the home page and redirect authenticated users based on their role."""
    if current_user.is_authenticated:
        if current_user.is_admin:
            return redirect(url_for('role_workspace.my_workspace'))
        elif current_user.access_level == AccessLevel.supplier:
            return redirect(url_for('role_workspace.my_workspace'))
        elif current_user.access_level == AccessLevel.project_manager:
            return redirect(url_for('role_workspace.my_workspace'))
        else:
            return redirect(url_for('role_workspace.my_workspace'))
    return render_template('dashboard/home.html', current_year=datetime.now().year)

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """Handle user registration with dynamic CAPTCHA and TOTP setup."""
    if current_user.is_authenticated:
        flash('You are already logged in.', 'info')
        return redirect(url_for('auth.home'))

    form = RegisterForm()
    totp_form = ConfirmTOTPForm()

    # Generate dynamic CAPTCHA if not already set
    if 'captcha_answer' not in session:
        num1 = random.randint(1, 10)
        num2 = random.randint(1, 10)
        session['captcha_answer'] = str(num1 + num2)
        session['captcha_question'] = f"What is {num1} + {num2}?"

    if form.validate_on_submit():
        # Verify terms acceptance
        if not request.form.get('accept_terms'):
            flash('You must agree to the Terms of Service and Privacy Policy.', 'danger')
            return render_template('auth/register.html', form=form, totp_form=totp_form, qr_code=None, registered=False,
                                 countries=sorted(COUNTRY_CODES.keys()), current_year=datetime.now().year,
                                 captcha_question=session.get('captcha_question', 'Please reload the page.'))

        # Verify CAPTCHA
        if str(form.captcha_answer.data) != session.get('captcha_answer'):
            flash('Incorrect CAPTCHA answer. Please try again.', 'danger')
            # Regenerate CAPTCHA
            num1 = random.randint(1, 10)
            num2 = random.randint(1, 10)
            session['captcha_answer'] = str(num1 + num2)
            session['captcha_question'] = f"What is {num1} + {num2}?"
            return render_template('auth/register.html', form=form, totp_form=totp_form, qr_code=None, registered=False,
                                 countries=sorted(COUNTRY_CODES.keys()), current_year=datetime.now().year,
                                 captcha_question=session.get('captcha_question'))

        try:
            # Generate TOTP secret
            totp_secret = pyotp.random_base32()
            # Prepare user object
            user = User(
                company_name=form.company_name.data,
                company_email=form.company_email.data,
                company_phone=form.company_phone.data,
                full_name=form.full_name.data,
                company_address=form.company_address.data,
                country=form.country.data,
                access_level=AccessLevel[form.access_level.data],
                store_name=form.store_name.data if form.access_level.data == 'supplier' else None,
                is_admin=(form.company_email.data == os.environ.get('ADMIN_EMAIL', '')),
                totp_secret=totp_secret,
                qr_code_base64=None,
                totp_confirmed=False,
                project_id=None
            )
            # Generate URI and QR code
            totp_uri = pyotp.totp.TOTP(totp_secret).provisioning_uri(
                name=form.company_email.data,
                issuer_name="MaterialHub"
            )
            user.qr_code_base64 = generate_qr_code(totp_uri)
            db.session.add(user)
            db.session.commit()
            session['pending_user_id'] = user.id
            logger.info(f"New user registered: {form.company_email.data} (ID: {user.id}, IP: {request.remote_addr})")
            flash('Registration successful! Please scan the QR code with Microsoft Authenticator and confirm TOTP.', 'success')
            # Reset CAPTCHA after successful registration
            session.pop('captcha_answer', None)
            session.pop('captcha_question', None)
            return render_template(
                'auth/register.html',
                form=form,
                totp_form=totp_form,
                qr_code=user.qr_code_base64,
                totp_secret=totp_secret,
                registered=True,
                countries=sorted(COUNTRY_CODES.keys()),
                current_year=datetime.now().year,
                captcha_question=None
            )
        except IntegrityError as e:
            db.session.rollback()
            logger.warning(f"Failed registration attempt: {str(e)} (IP: {request.remote_addr})")
            if 'company_email' in str(e).lower():
                flash('This email is already registered. Please use a different email or log in.', 'danger')
            elif 'company_phone' in str(e).lower():
                flash('This phone number is already in use. Please use a different phone number.', 'danger')
            else:
                flash('A database error occurred. Please try again later.', 'danger')
        except ValueError as e:
            db.session.rollback()
            logger.warning(f"Validation error during registration: {str(e)} (IP: {request.remote_addr})")
            flash(f"Invalid input: {str(e)}", 'danger')
        except Exception as e:
            db.session.rollback()
            logger.error(f"Registration error for {form.company_email.data}: {str(e)} (IP: {request.remote_addr})")
            flash('An unexpected error occurred during registration. Please try again later.', 'danger')
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f"Error in {form[field].label.text}: {error}", 'danger')

    return render_template('auth/register.html', form=form, totp_form=totp_form, qr_code=None, registered=False,
                         countries=sorted(COUNTRY_CODES.keys()), current_year=datetime.now().year,
                         captcha_question=session.get('captcha_question', 'Please reload the page.'))

@auth_bp.route('/confirm_totp', methods=['POST'])
def confirm_totp():
    """Confirm TOTP code and mark user as confirmed."""
    form = ConfirmTOTPForm()
    user_id = session.get('pending_user_id')

    if not user_id:
        flash('Session expired. Please register again.', 'danger')
        return redirect(url_for('auth.register'))

    user = User.query.get(user_id)
    if not user:
        flash('User not found. Please register again.', 'danger')
        return redirect(url_for('auth.register'))

    if form.validate_on_submit():
        totp = pyotp.TOTP(user.totp_secret)
        if totp.verify(form.totp_code.data) and form.totp_confirmed.data:
            user.totp_confirmed = True
            db.session.commit()
            session.pop('pending_user_id', None)
            logger.info(f"TOTP confirmed for user: {user.company_email} (ID: {user.id}, IP: {request.remote_addr})")
            flash('Two-factor authentication setup confirmed. You can now log in.', 'success')
            return redirect(url_for('auth.login'))
        else:
            flash('Invalid TOTP code or confirmation not checked.', 'danger')
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f"Error in {form[field].label.text}: {error}", 'danger')

    return render_template(
        'auth/register.html',
        form=RegisterForm(),
        totp_form=form,
        qr_code=user.qr_code_base64,
        totp_secret=user.totp_secret,
        registered=True,
        countries=sorted(COUNTRY_CODES.keys()),
        current_year=datetime.now().year,
        captcha_question=None
    )

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Handle user login with email and TOTP verification."""
    if current_user.is_authenticated:
        flash('You are already logged in.', 'info')
        return redirect(url_for('auth.home'))

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(company_email=form.email.data).first()
        if user:
            if not user.totp_confirmed:
                logger.warning(f"Login attempt without TOTP setup: {form.email.data} (IP: {request.remote_addr})")
                flash('Please complete two-factor authentication setup before logging in.', 'danger')
                return redirect(url_for('auth.register'))
            totp = pyotp.TOTP(user.totp_secret)
            if totp.verify(form.totp_code.data):
                login_user(user)
                logger.info(f"User logged in: {user.company_email} (ID: {user.id}, IP: {request.remote_addr})")
                flash('Login successful!', 'success')
                if user.is_admin:
                    return redirect(url_for('role_workspace.my_workspace'))
                elif user.access_level == AccessLevel.supplier:
                    return redirect(url_for('role_workspace.my_workspace'))
                elif user.access_level == AccessLevel.project_manager:
                    return redirect(url_for('role_workspace.my_workspace'))
                return redirect(url_for('role_workspace.my_workspace'))
            else:
                logger.warning(f"Invalid TOTP code for {form.email.data} (IP: {request.remote_addr})")
                flash('Invalid authenticator code. Please try again.', 'danger')
        else:
            logger.warning(f"Login attempt with non-existent email: {form.email.data} (IP: {request.remote_addr})")
            flash('No account found with that email.', 'danger')
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f"Error in {form[field].label.text}: {error}", 'danger')

    return render_template('auth/login.html', form=form, current_year=datetime.now().year)

@auth_bp.route('/logout')
@login_required
def logout():
    """Handle user logout."""
    logger.info(f"User logged out: {current_user.company_email} (ID: {current_user.id}, IP: {request.remote_addr})")
    logout_user()
    flash('You have been logged out successfully.', 'success')
    return redirect(url_for('auth.home'))

@auth_bp.route('/reset_password_request', methods=['GET', 'POST'])
def reset_password_request():
    """Handle TOTP reset request (email-based, placeholder)."""
    if current_user.is_authenticated:
        flash('You are already logged in.', 'info')
        return redirect(url_for('auth.home'))

    form = ResetPasswordRequestForm()
    if form.validate_on_submit():
        user = User.query.filter_by(company_email=form.email.data).first()
        if user:
            logger.info(f"TOTP reset requested for: {form.email.data} (IP: {request.remote_addr})")
            flash('A TOTP reset link has been sent to your email (feature not fully implemented).', 'success')
        else:
            logger.warning(f"TOTP reset attempt for non-existent email: {form.email.data} (IP: {request.remote_addr})")
            flash('No account found with that email.', 'danger')
        return redirect(url_for('auth.login'))
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f"Error in {form[field].label.text}: {error}", 'danger')

    return render_template('auth/reset_password_request.html', form=form, current_year=datetime.now().year)

@auth_bp.route('/change_password', methods=['GET', 'POST'])
@login_required
def change_password():
    """Handle TOTP reset (no password, as TOTP is primary authentication)."""
    form = ChangePasswordForm()
    if form.validate_on_submit():
        try:
            user = current_user
            user.totp_secret = pyotp.random_base32()
            totp_uri = pyotp.totp.TOTP(user.totp_secret).provisioning_uri(
                name=user.company_email,
                issuer_name="MaterialHub"
            )
            user.qr_code_base64 = generate_qr_code(totp_uri)
            user.totp_confirmed = False
            db.session.commit()
            logger.info(f"TOTP reset for user: {user.company_email} (ID: {user.id}, IP: {request.remote_addr})")
            flash('TOTP reset successfully! Please scan the new QR code with Microsoft Authenticator.', 'success')
            return render_template('auth/change_password.html', form=form, qr_code=user.qr_code_base64,
                                 totp_secret=user.totp_secret, current_year=datetime.now().year)
        except Exception as e:
            db.session.rollback()
            logger.error(f"TOTP reset error for {current_user.company_email}: {str(e)} (IP: {request.remote_addr})")
            flash('An error occurred while resetting TOTP. Please try again.', 'danger')
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f"Error in {form[field].label.text}: {error}", 'danger')

    return render_template('auth/change_password.html', form=form, qr_code=None, totp_secret=None, current_year=datetime.now().year)

@auth_bp.route('/privacy_policy')
def privacy_policy():
    """Render the privacy policy page."""
    return render_template('legal/privacy_policy.html', current_year=datetime.now().year)

@auth_bp.route('/terms_of_service')
def terms_of_service():
    """Render the terms of service page."""
    return render_template('legal/terms_of_service.html', current_year=datetime.now().year)

@auth_bp.route('/contact_support')
def contact_support():
    """Render the contact support page."""
    return render_template('support/contact_support.html', current_year=datetime.now().year)