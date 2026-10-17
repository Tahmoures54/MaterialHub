import os
import logging
import secrets
import hashlib
import re
from datetime import datetime, timedelta
from flask import Blueprint, render_template, redirect, url_for, flash, request, session
from flask_login import login_user, logout_user, current_user, login_required
from sqlalchemy.exc import IntegrityError
from models import User, AccessLevel, AccountRecoveryToken
from extensions import db, limiter
from forms.auth_forms import RegisterForm, LoginForm, ResetPasswordRequestForm, ChangePasswordForm, ConfirmTOTPForm
from data.country_codes import COUNTRY_CODES
import pyotp
import pytz
import qrcode
from io import BytesIO
import base64
from services.email_service import EmailConfigurationError, send_totp_recovery_email

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
@limiter.limit('5 per hour')
def register():
    """Handle user registration with dynamic CAPTCHA and TOTP setup."""
    if current_user.is_authenticated:
        flash('You are already logged in.', 'info')
        return redirect(url_for('auth.home'))

    form = RegisterForm()
    totp_form = ConfirmTOTPForm()

    # Generate dynamic CAPTCHA if not already set
    if 'captcha_answer' not in session:
        num1 = secrets.randbelow(10) + 1
        num2 = secrets.randbelow(10) + 1
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
            num1 = secrets.randbelow(10) + 1
            num2 = secrets.randbelow(10) + 1
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
                totp_secret=User.encrypt_totp_secret(totp_secret),
                qr_code_base64=None,
                totp_confirmed=False,
                project_id=None,
                trial_started_at=None,
                trial_ends_at=None,
                subscription_plan='trial',
                subscription_status='trial'
            )
            # Generate URI and QR code
            totp_uri = pyotp.totp.TOTP(totp_secret).provisioning_uri(
                name=form.company_email.data,
                issuer_name="MaterialHub"
            )
            qr_code = generate_qr_code(totp_uri)
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
                qr_code=qr_code,
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
@limiter.limit('5 per minute')
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
        totp = pyotp.TOTP(user.decrypt_totp_secret())
        if totp.verify(form.totp_code.data) and form.totp_confirmed.data:
            user.totp_confirmed = True
            trial_started = datetime.now(pytz.UTC)
            user.trial_started_at = trial_started
            user.trial_ends_at = trial_started + timedelta(days=45)
            user.subscription_plan = 'trial'
            user.subscription_status = 'trial'
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
        qr_code=generate_qr_code(user.get_totp_uri()),
        totp_secret=user.decrypt_totp_secret(),
        registered=True,
        countries=sorted(COUNTRY_CODES.keys()),
        current_year=datetime.now().year,
        captcha_question=None
    )

@auth_bp.route('/login', methods=['GET', 'POST'])
@limiter.limit('5 per minute')
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
                logger.warning("Login rejected because authenticator setup is incomplete (user_id=%s)", user.id)
                flash('Unable to sign in with those details. Check your email and authenticator code or contact support.', 'danger')
            totp = pyotp.TOTP(user.decrypt_totp_secret())
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
                logger.warning("Login rejected because authenticator verification failed")
                flash('Unable to sign in with those details. Check your email and authenticator code or contact support.', 'danger')
        else:
            logger.warning("Login rejected because credentials were not accepted")
            flash('Unable to sign in with those details. Check your email and authenticator code or contact support.', 'danger')
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
@limiter.limit('3 per 15 minutes')
def reset_password_request():
    """Request a one-time, expiring TOTP recovery link without account enumeration."""
    if current_user.is_authenticated:
        flash('You are already logged in.', 'info')
        return redirect(url_for('auth.home'))

    form = ResetPasswordRequestForm()
    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        user = User.query.filter(User.company_email.ilike(email)).first()
        if user:
            raw_token = secrets.token_urlsafe(32)
            now = datetime.now(pytz.UTC).replace(tzinfo=None)
            recovery = AccountRecoveryToken(
                user_id=user.id,
                token_hash=hashlib.sha256(raw_token.encode('utf-8')).hexdigest(),
                expires_at=now + timedelta(minutes=30),
            )
            db.session.add(recovery)
            try:
                db.session.commit()
                send_totp_recovery_email(user.company_email, raw_token)
                logger.info("TOTP recovery email submitted for delivery (user_id=%s)", user.id)
            except Exception as exc:
                db.session.rollback()
                # If the token row was committed before SMTP failed, invalidate it.
                persisted = AccountRecoveryToken.query.filter_by(
                    token_hash=hashlib.sha256(raw_token.encode('utf-8')).hexdigest(),
                    used_at=None,
                ).first()
                if persisted:
                    persisted.used_at = datetime.now(pytz.UTC).replace(tzinfo=None)
                    db.session.commit()
                # Deliberately log neither the raw token nor the recovery URL.
                logger.warning("TOTP recovery delivery unavailable (%s)", type(exc).__name__)
        # Identical public response for existing/missing users and delivery failure.
        flash(
            'If the address matches an account and recovery email is configured, instructions will be sent. '
            'If you do not receive an email, contact support.',
            'info',
        )
        return redirect(url_for('auth.login'))

    for field, errors in form.errors.items():
        for error in errors:
            flash(f"Error in {form[field].label.text}: {error}", 'danger')
    return render_template('auth/reset_password_request.html', form=form, current_year=datetime.now().year)


@auth_bp.route('/reset_totp', methods=['GET', 'POST'])
@limiter.limit('10 per hour')
def reset_totp_with_token():
    """Rotate TOTP only after the emailed token and new authenticator code are verified."""
    token = request.args.get('token') if request.method == 'GET' else request.form.get('token')
    if not token or len(token) > 128:
        flash('This recovery link is invalid or expired. Request a new one.', 'danger')
        return redirect(url_for('auth.reset_password_request'))

    token_hash = hashlib.sha256(token.encode('utf-8')).hexdigest()
    now = datetime.now(pytz.UTC).replace(tzinfo=None)
    recovery = AccountRecoveryToken.query.filter_by(token_hash=token_hash, used_at=None).first()
    if not recovery or recovery.expires_at <= now:
        flash('This recovery link is invalid or expired. Request a new one.', 'danger')
        return redirect(url_for('auth.reset_password_request'))

    user = User.query.get(recovery.user_id)
    if not user:
        flash('This recovery link is invalid or expired. Request a new one.', 'danger')
        return redirect(url_for('auth.reset_password_request'))

    if request.method == 'GET':
        if not recovery.pending_totp_secret:
            new_secret = pyotp.random_base32()
            recovery.pending_totp_secret = User.encrypt_totp_secret(new_secret)
            db.session.commit()
        new_secret = User._totp_cipher().decrypt(
            recovery.pending_totp_secret[4:].encode('ascii')
        ).decode('utf-8') if recovery.pending_totp_secret.startswith('enc:') else recovery.pending_totp_secret
        uri = pyotp.TOTP(new_secret).provisioning_uri(
            name=user.company_email,
            issuer_name='MaterialHub',
        )
        return render_template(
            'auth/reset_totp.html',
            qr_code=generate_qr_code(uri),
            totp_secret=new_secret,
            recovery_token=token,
        )

    code = (request.form.get('totp_code') or '').strip()
    if not re.fullmatch(r'\d{6}', code):
        flash('Enter a valid six-digit authenticator code.', 'danger')
        return redirect(url_for('auth.reset_totp_with_token', token=token))

    encrypted_secret = recovery.pending_totp_secret
    if not encrypted_secret:
        flash('This recovery link is invalid or expired. Request a new one.', 'danger')
        return redirect(url_for('auth.reset_password_request'))
    try:
        new_secret = (
            User._totp_cipher().decrypt(encrypted_secret[4:].encode('ascii')).decode('utf-8')
            if encrypted_secret.startswith('enc:') else encrypted_secret
        )
    except Exception:
        logger.error("Unable to decrypt pending TOTP recovery secret (recovery_id=%s)", recovery.id)
        flash('Recovery could not be completed. Request a new link.', 'danger')
        return redirect(url_for('auth.reset_password_request'))

    if not pyotp.TOTP(new_secret).verify(code, valid_window=1):
        flash('Invalid authenticator code. Please try again.', 'danger')
        return redirect(url_for('auth.reset_totp_with_token', token=token))

    user.totp_secret = encrypted_secret
    user.qr_code_base64 = None
    user.totp_confirmed = True
    recovery.used_at = now
    recovery.pending_totp_secret = None
    AccountRecoveryToken.query.filter(
        AccountRecoveryToken.user_id == user.id,
        AccountRecoveryToken.id != recovery.id,
        AccountRecoveryToken.used_at.is_(None),
    ).update({AccountRecoveryToken.used_at: now}, synchronize_session=False)
    db.session.commit()
    logger.info("TOTP recovery completed (user_id=%s)", user.id)
    flash('Your authenticator has been reset. You can now sign in with the new code.', 'success')
    return redirect(url_for('auth.login'))


@auth_bp.route('/change_password', methods=['GET', 'POST'])
@limiter.limit('5 per 15 minutes')
@login_required
def change_password():
    """Handle TOTP reset (no password, as TOTP is primary authentication)."""
    form = ChangePasswordForm()
    if form.validate_on_submit():
        try:
            user = current_user
            new_totp_secret = pyotp.random_base32()
            user.totp_secret = User.encrypt_totp_secret(new_totp_secret)
            totp_uri = pyotp.totp.TOTP(new_totp_secret).provisioning_uri(
                name=user.company_email,
                issuer_name="MaterialHub"
            )
            qr_code = generate_qr_code(totp_uri)
            user.qr_code_base64 = None
            user.totp_confirmed = False
            db.session.commit()
            logger.info(f"TOTP reset for user: {user.company_email} (ID: {user.id}, IP: {request.remote_addr})")
            flash('TOTP reset successfully! Please scan the new QR code with Microsoft Authenticator.', 'success')
            return render_template('auth/change_password.html', form=form, qr_code=qr_code,
                                 totp_secret=new_totp_secret, current_year=datetime.now().year)
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