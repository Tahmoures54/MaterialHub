import qrcode
from io import BytesIO
import base64
import phonenumbers
from phonenumbers import PhoneNumberFormat

def generate_qr_code(uri):
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(uri)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buffered = BytesIO()
    img.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode('utf-8')

def get_clean_phone(phone, country):
    try:
        parsed_number = phonenumbers.parse(phone, country)
        if not phonenumbers.is_valid_number(parsed_number):
            raise ValueError("Invalid phone number")
        return phonenumbers.format_number(parsed_number, PhoneNumberFormat.E164)
    except Exception:
        raise ValueError("Invalid phone number format")

def generate_next_mr_no(company_name):
    """
    Generate a new unique MR No for a given company.
    This is a simple version and should be adapted for production.
    """
    from models import MaterialRequisition, db

    last_mr = (
        db.session.query(MaterialRequisition)
        .filter_by(company_name=company_name)
        .order_by(MaterialRequisition.id.desc())
        .first()
    )
    if last_mr and last_mr.mr_no and last_mr.mr_no.isdigit():
        next_no = int(last_mr.mr_no) + 1
    else:
        next_no = 1
    return f"{next_no:05d}"