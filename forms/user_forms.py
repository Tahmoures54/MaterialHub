from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, SubmitField
from wtforms.validators import DataRequired, Email, Regexp, ValidationError
from models import User, AccessLevel

class AddUserForm(FlaskForm):
    new_full_name = StringField('Full Name', validators=[
        DataRequired(message="Full name is required.")
    ])
    new_email = StringField('Email', validators=[
        DataRequired(message="Email is required."),
        Email(message="Invalid email address.")
    ])
    new_phone = StringField('Phone', validators=[
        DataRequired(message="Phone number is required."),
        Regexp(r'^\+?\d{9,15}$', message="Invalid phone number (e.g., +989123456789).")
    ])
    # Use AccessLevel Enum's .value for SelectField values to match model expectation
    new_access_level = SelectField(
        'Access Level',
        choices=[(level.value, level.name.replace('_', ' ').title()) for level in AccessLevel],
        validators=[DataRequired(message="Access level is required.")]
    )
    add_user = SubmitField('Add User')

    def validate_new_email(self, field):
        """
        Validate that the email is not already registered in the database.
        """
        if User.query.filter_by(company_email=field.data).first():
            raise ValidationError('This email is already registered. Please use a different email.')