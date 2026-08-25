from flask_wtf import FlaskForm
from wtforms import StringField, FloatField, SelectField, SubmitField, IntegerField
from wtforms.validators import DataRequired, Optional
from data.country_codes import COUNTRY_CODES
from models import Project, User, PurchaseOrder, MaterialRequisition, InspectionStatus, DeliveryStatus, PurchaseOrderStatus

class MaterialMarketplaceForm(FlaskForm):
    search = StringField("Search", validators=[Optional()])
    country = SelectField("Country", choices=[('', 'All Countries')] + [(code, name) for name, code in sorted(COUNTRY_CODES.items())], validators=[Optional()])
    submit = SubmitField("Search")

class AddMaterialForm(FlaskForm):
    material_name = StringField("Material Name", validators=[DataRequired()])
    description = StringField("Description", validators=[DataRequired()])
    category = StringField("Category", validators=[DataRequired()])
    unit_price = FloatField("Unit Price", validators=[DataRequired()])
    available_quantity = FloatField("Available Quantity", validators=[DataRequired()])
    unit_of_measure = StringField("Unit of Measure", validators=[DataRequired()])
    submit = SubmitField("Add Material")

class PurchaseOrderForm(FlaskForm):
    order_no = StringField("Order Number", validators=[DataRequired()])
    project_id = SelectField("Project", coerce=int, validators=[DataRequired()])
    supplier_id = SelectField("Supplier", coerce=int, validators=[DataRequired()])
    total_price = FloatField("Total Price", validators=[DataRequired()])
    submit = SubmitField("Create Purchase Order")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.project_id.choices = [(p.id, p.project_name) for p in Project.query.all()]
        self.supplier_id.choices = [(u.id, u.company_name) for u in User.query.filter_by(access_level='supplier').all()]

class QualityControlForm(FlaskForm):
    order_id = SelectField("Purchase Order", coerce=int, validators=[DataRequired()])
    status = SelectField("Status", choices=[(e.value, e.name) for e in InspectionStatus], validators=[DataRequired()])
    remarks = StringField("Remarks", validators=[Optional()])
    submit = SubmitField("Create Quality Control")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.order_id.choices = [(p.id, p.order_no) for p in PurchaseOrder.query.all()]

class DeliveryForm(FlaskForm):
    order_id = SelectField("Purchase Order", coerce=int, validators=[DataRequired()])
    status = SelectField("Status", choices=[(e.value, e.name) for e in DeliveryStatus], validators=[DataRequired()])
    remarks = StringField("Remarks", validators=[Optional()])
    submit = SubmitField("Create Delivery")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.order_id.choices = [(p.id, p.order_no) for p in PurchaseOrder.query.all()]

class WarehouseEntryForm(FlaskForm):
    material_id = SelectField("Material Requisition", coerce=int, validators=[DataRequired()])
    quantity = FloatField("Quantity", validators=[DataRequired()])
    remarks = StringField("Remarks", validators=[Optional()])
    submit = SubmitField("Receive Material")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.material_id.choices = [(m.id, m.mr_no) for m in MaterialRequisition.query.all()]