from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, SelectField, TelField, TextAreaField, IntegerField, BooleanField
from wtforms.validators import DataRequired, Email, Length, Regexp, ValidationError, Optional
from models import User, AccessLevel
from data.country_codes import COUNTRY_CODES
from flask import session

def validate_captcha(form, field):
    """Validate CAPTCHA answer against session-stored value."""
    if 'captcha_answer' not in session:
        raise ValidationError('CAPTCHA session expired. Please reload the page and try again.')
    if str(field.data).strip() != str(session.get('captcha_answer')).strip():
        raise ValidationError('Incorrect CAPTCHA answer.')

def validate_company_email(form, field):
    """Ensure company email is unique."""
    if User.query.filter_by(company_email=field.data).first():
        raise ValidationError('This email is already registered.')

def validate_company_phone(form, field):
    """Ensure company phone is unique."""
    if User.query.filter_by(company_phone=field.data).first():
        raise ValidationError('This phone number is already in use.')

def validate_store_name(form, field):
    """Ensure store_name is provided for suppliers."""
    if form.access_level.data == 'supplier' and not field.data:
        raise ValidationError('Store name is required for suppliers.')

class RegisterForm(FlaskForm):
    company_name = StringField('Company Name', validators=[
        DataRequired(), Length(min=2, max=100)
    ])
    company_email = StringField('Company Email', validators=[
        DataRequired(), Email(), validate_company_email
    ])
    company_phone = TelField('Company Phone', validators=[
        DataRequired(),
        Regexp(r'^\+?[0-9]{10,15}$', message='Please enter a valid phone number (e.g., +989123456789)'),
        validate_company_phone
    ])
    full_name = StringField('Full Name', validators=[
        DataRequired(), Length(min=2, max=100)
    ])
    company_address = TextAreaField('Company Address', validators=[
        DataRequired(), Length(min=5, max=200)
    ])
    country = SelectField('Country', choices=[('', 'Select a country')] + [(code, name) for name, code in sorted(COUNTRY_CODES.items())],
                         validators=[DataRequired(message='Please select a country.')])
    access_level = SelectField('Role', choices=[
        ('', 'Select a role'),
        ('project_manager', 'Project Manager'),
        ('supplier', 'Supplier')
    ], validators=[DataRequired(message='Please select a role.')])
    store_name = StringField('Store Name', validators=[
        Optional(), validate_store_name, Length(max=100)
    ])
    captcha_answer = IntegerField('CAPTCHA Answer', validators=[
        DataRequired(message='Please enter the CAPTCHA answer.'), validate_captcha
    ])
    submit = SubmitField('Register')

class LoginForm(FlaskForm):
    email = StringField('Email', validators=[
        DataRequired(message='Please enter your email.'),
        Email(message='Please enter a valid email address.')
    ])
    totp_code = StringField('Authenticator Code', validators=[
        DataRequired(message='Please enter the authenticator code.'),
        Regexp(r'^\d{6}$', message='Enter a valid 6-digit code.')
    ])
    submit = SubmitField('Login')

class ResetPasswordRequestForm(FlaskForm):
    email = StringField('Email', validators=[
        DataRequired(message='Please enter your email.'),
        Email(message='Please enter a valid email address.')
    ])
    submit = SubmitField('Request TOTP Reset')

class ChangePasswordForm(FlaskForm):
    submit = SubmitField('Reset TOTP')

class ConfirmTOTPForm(FlaskForm):
    totp_code = StringField('Authenticator Code', validators=[
        DataRequired(message='Please enter the authenticator code.'),
        Regexp(r'^\d{6}$', message='Enter a valid 6-digit code.')
    ])
    totp_confirmed = BooleanField(
        'I have saved the TOTP secret and understand I am responsible for any loss of access.',
        validators=[DataRequired(message='You must confirm that you have saved the TOTP secret.')]
    )
    submit = SubmitField('Confirm')

class AddUserForm(FlaskForm):
    new_full_name = StringField('Full Name', validators=[
        DataRequired(message='Please enter the full name.'),
        Length(min=2, max=100)
    ])
    new_email = StringField('Email', validators=[
        DataRequired(message='Please enter the email.'),
        Email(message='Please enter a valid email address.'),
        validate_company_email
    ])
    new_phone = TelField('Phone', validators=[
        DataRequired(message='Please enter the phone number.'),
        Regexp(r'^\+?[0-9]{10,15}$', message='Please enter a valid phone number (e.g., +989123456789)'),
        validate_company_phone
    ])
    new_access_level = SelectField('Role', choices=[
        ('engineering', 'Engineering'),
        ('purchase', 'Purchase'),
        ('quality', 'Quality'),
        ('delivery', 'Delivery'),
        ('warehouse', 'Warehouse')
    ], validators=[DataRequired(message='Please select a role.')])
    add_user = SubmitField('Add Team Member')