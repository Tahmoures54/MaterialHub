import enum
import re
from datetime import date, datetime
import pytz
from flask_login import UserMixin
from sqlalchemy import Enum
from extensions import db

# --- Custom Exceptions ---

class ValidationError(Exception):
    """Custom exception for model validation errors."""
    pass

# --- Enums ---

class AccessLevel(enum.Enum):
    project_manager = 'project_manager'
    engineering = 'engineering'
    purchase = 'purchase'
    quality = 'quality'
    delivery = 'delivery'
    warehouse = 'warehouse'
    supplier = 'supplier'

class InspectionStatus(enum.Enum):
    passed = 'passed'
    failed = 'failed'
    pending = 'pending'

class TenderStatus(enum.Enum):
    open = 'open'
    closed = 'closed'
    cancelled = 'cancelled'

class BidStatus(enum.Enum):
    pending = 'pending'
    accepted = 'accepted'
    rejected = 'rejected'

class RequisitionStatus(enum.Enum):
    pending = 'pending'
    approved = 'approved'
    rejected = 'rejected'

class PurchaseOrderStatus(enum.Enum):
    pending = 'pending'
    issued = 'issued'
    delivered = 'delivered'
    cancelled = 'cancelled'

class DeliveryStatus(enum.Enum):
    pending = 'pending'
    in_transit = 'in_transit'
    delivered = 'delivered'
    delayed = 'delayed'

class ApprovalStatus(enum.Enum):
    pending = 'pending'
    approved = 'approved'
    rejected = 'rejected'

class WorkflowStatus(enum.Enum):
    warehouse = 'Warehouse'
    approved = 'Approved'
    rejected = 'Rejected'


def _parse_date(value):
    if value in (None, ''):
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    text = str(value).strip()
    for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y', '%Y/%m/%d'):
        try:
            return datetime.strptime(text[:10], fmt).date()
        except ValueError:
            continue
    raise ValidationError(f'Invalid date: {value}')


def _parse_float(value, default=None):
    if value in (None, ''):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        raise ValidationError(f'Invalid number: {value}')


def _parse_enum(enum_cls, value, default=None):
    if value in (None, ''):
        return default
    if isinstance(value, enum_cls):
        return value
    try:
        return enum_cls(value)
    except ValueError:
        try:
            return enum_cls[str(value).lower()]
        except KeyError:
            return default


def ensure_project(project_no, company_name, project_name=None):
    """Find or create a project so requisitions can be imported without a prior setup step."""
    if not project_no:
        raise ValidationError('Project number is required')
    project = Project.query.filter_by(project_no=project_no, company_name=company_name).first()
    if project:
        return project
    project = Project(
        project_no=project_no,
        project_name=project_name or project_no,
        company_name=company_name,
    )
    db.session.add(project)
    db.session.flush()
    return project


# --- Models ---

class Project(db.Model):
    __tablename__ = 'project'
    id = db.Column(db.Integer, primary_key=True)
    project_no = db.Column(db.String(50), nullable=False, unique=True, index=True)
    project_name = db.Column(db.String(100), nullable=False)
    company_name = db.Column(db.String(100), nullable=False, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(pytz.UTC))
    updated_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(pytz.UTC), onupdate=lambda: datetime.now(pytz.UTC))

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.validate(kwargs)

    def validate(self, kwargs):
        if 'project_no' in kwargs and not re.match(r'^[A-Za-z0-9_-]{1,50}$', kwargs['project_no']):
            raise ValidationError('Project number must be 1-50 characters, alphanumeric, underscore, or hyphen')
        if 'project_name' in kwargs and not kwargs['project_name'].strip():
            raise ValidationError('Project name cannot be empty')
        if 'company_name' in kwargs and not kwargs['company_name'].strip():
            raise ValidationError('Company name cannot be empty')

    def to_dict(self):
        return {
            'id': self.id,
            'project_no': self.project_no,
            'project_name': self.project_name,
            'company_name': self.company_name,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }

    def __repr__(self):
        return f"<Project {self.project_no}: {self.project_name}>"

class MaterialRequisition(db.Model):
    __tablename__ = 'material_requisition'
    id = db.Column(db.Integer, primary_key=True)
    mr_no = db.Column(db.String(50), unique=True, nullable=False, index=True)
    subject = db.Column(db.String(200), nullable=False)
    drawing_no = db.Column(db.String(50))
    drawing_revision = db.Column(db.String(10))
    drawing_page = db.Column(db.String(10))
    material_type = db.Column(db.String(50))
    item_code = db.Column(db.String(50), nullable=False, index=True)
    material_description = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(50))
    size_inches = db.Column(db.Float, nullable=True)
    thickness_mm = db.Column(db.Float, nullable=True)
    length_mm = db.Column(db.Float, nullable=True)
    discipline = db.Column(db.String(50), nullable=False)
    added_by = db.Column(db.String(100), nullable=False)
    edited_by = db.Column(db.String(100), nullable=False)
    required_date = db.Column(db.Date, nullable=False)
    unit_of_measure = db.Column(db.String(20), nullable=False)
    quantity = db.Column(db.Float, nullable=False)
    spare_part_quantity = db.Column(db.Float, default=0.0)
    priority = db.Column(db.String(20), nullable=False)
    standard_specification = db.Column(db.String(100), nullable=True)
    estimated_cost = db.Column(db.Float, nullable=True)
    project_no = db.Column(db.String(50), nullable=False, index=True)
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'), nullable=False, index=True)
    company_name = db.Column(db.String(100), nullable=False, index=True)
    status = db.Column(Enum(ApprovalStatus), nullable=False, default=ApprovalStatus.pending)
    remarks = db.Column(db.Text, nullable=True)
    documents = db.Column(db.Text, nullable=True)
    suggested_vendor = db.Column(db.String(100), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(pytz.UTC))
    updated_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(pytz.UTC), onupdate=lambda: datetime.now(pytz.UTC))
    project = db.relationship('Project', backref=db.backref('requisitions', lazy='dynamic'))
    user = db.relationship('User', backref=db.backref('requisitions', lazy='dynamic'))

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.validate(kwargs)

    def validate(self, kwargs):
        if 'mr_no' in kwargs and not re.match(r'^MR-\d{4,}$', kwargs['mr_no']):
            raise ValidationError('Material requisition number must be in format MR-XXXX (numbers)')
        if 'quantity' in kwargs and kwargs['quantity'] <= 0:
            raise ValidationError('Quantity must be positive')
        if 'spare_part_quantity' in kwargs and kwargs['spare_part_quantity'] is not None and kwargs['spare_part_quantity'] < 0:
            raise ValidationError('Spare part quantity cannot be negative')
        if 'item_code' in kwargs and not kwargs['item_code'].strip():
            raise ValidationError('Item code cannot be empty')
        if 'material_description' in kwargs and not kwargs['material_description'].strip():
            raise ValidationError('Material description cannot be empty')

    def to_dict(self):
        return {
            'id': self.id,
            'mr_no': self.mr_no,
            'subject': self.subject,
            'drawing_no': self.drawing_no,
            'drawing_revision': self.drawing_revision,
            'drawing_page': self.drawing_page,
            'material_type': self.material_type,
            'item_code': self.item_code,
            'material_description': self.material_description,
            'category': self.category,
            'size_inches': self.size_inches,
            'thickness_mm': self.thickness_mm,
            'length_mm': self.length_mm,
            'discipline': self.discipline,
            'added_by': self.added_by,
            'edited_by': self.edited_by,
            'required_date': self.required_date.isoformat() if self.required_date else None,
            'unit_of_measure': self.unit_of_measure,
            'quantity': self.quantity,
            'spare_part_quantity': self.spare_part_quantity,
            'priority': self.priority,
            'standard_specification': self.standard_specification,
            'estimated_cost': self.estimated_cost,
            'project_no': self.project_no,
            'project_id': self.project_id,
            'company_name': self.company_name,
            'status': self.status.value,
            'remarks': self.remarks,
            'documents': self.documents,
            'suggested_vendor': self.suggested_vendor,
            'user_id': self.user_id,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }

    CSV_FIELDS = (
        'mr_no', 'subject', 'drawing_no', 'drawing_revision', 'drawing_page',
        'material_type', 'item_code', 'material_description', 'category',
        'size_inches', 'thickness_mm', 'length_mm', 'discipline', 'required_date',
        'unit_of_measure', 'quantity', 'spare_part_quantity', 'priority',
        'standard_specification', 'estimated_cost', 'project_no', 'status',
        'remarks', 'suggested_vendor',
    )

    @classmethod
    def csv_fields(cls):
        return list(cls.CSV_FIELDS)

    @classmethod
    def csv_headers(cls):
        return [field.replace('_', ' ').title() for field in cls.CSV_FIELDS]

    @classmethod
    def from_dict(cls, data, company_name, user_id=None):
        payload = dict(data or {})
        project_no = (payload.get('project_no') or '').strip()
        project_id = payload.get('project_id')
        if not project_id:
            project = ensure_project(project_no, company_name, payload.get('project_name'))
            project_id = project.id
            project_no = project.project_no
        required_date = _parse_date(payload.get('required_date')) or date.today()
        quantity = _parse_float(payload.get('quantity'), 0)
        user_id = user_id or payload.get('user_id')
        if not user_id:
            raise ValidationError('User is required to create a material requisition')
        return cls(
            mr_no=payload.get('mr_no'),
            subject=payload.get('subject') or payload.get('material_description') or payload.get('item_code'),
            drawing_no=payload.get('drawing_no'),
            drawing_revision=payload.get('drawing_revision'),
            drawing_page=payload.get('drawing_page'),
            material_type=payload.get('material_type') or payload.get('category'),
            item_code=(payload.get('item_code') or '').strip(),
            material_description=(payload.get('material_description') or payload.get('subject') or '').strip(),
            category=payload.get('category'),
            size_inches=_parse_float(payload.get('size_inches')),
            thickness_mm=_parse_float(payload.get('thickness_mm')),
            length_mm=_parse_float(payload.get('length_mm')),
            discipline=payload.get('discipline') or 'General',
            added_by=payload.get('added_by') or '',
            edited_by=payload.get('edited_by') or payload.get('added_by') or '',
            required_date=required_date,
            unit_of_measure=payload.get('unit_of_measure') or payload.get('unit') or 'EA',
            quantity=quantity,
            spare_part_quantity=_parse_float(payload.get('spare_part_quantity'), 0.0),
            priority=payload.get('priority') or 'Normal',
            standard_specification=payload.get('standard_specification'),
            estimated_cost=_parse_float(payload.get('estimated_cost')),
            project_no=project_no,
            project_id=project_id,
            company_name=company_name,
            status=_parse_enum(ApprovalStatus, payload.get('status'), ApprovalStatus.pending),
            remarks=payload.get('remarks'),
            documents=payload.get('documents'),
            suggested_vendor=payload.get('suggested_vendor'),
            user_id=int(user_id),
        )

    def update_from_dict(self, data):
        payload = dict(data or {})
        assignable = {
            'subject', 'drawing_no', 'drawing_revision', 'drawing_page',
            'material_type', 'item_code', 'material_description', 'category',
            'size_inches', 'thickness_mm', 'length_mm', 'discipline',
            'unit_of_measure', 'quantity', 'spare_part_quantity', 'priority',
            'standard_specification', 'estimated_cost', 'remarks', 'documents',
            'suggested_vendor', 'project_no',
        }
        for key in assignable:
            if key not in payload:
                continue
            value = payload[key]
            if key in ('size_inches', 'thickness_mm', 'length_mm', 'quantity', 'spare_part_quantity', 'estimated_cost'):
                value = _parse_float(value, getattr(self, key))
            setattr(self, key, value)
        if 'required_date' in payload:
            parsed = _parse_date(payload.get('required_date'))
            if parsed:
                self.required_date = parsed
        if 'status' in payload:
            parsed_status = _parse_enum(ApprovalStatus, payload.get('status'), self.status)
            if parsed_status:
                self.status = parsed_status
        if payload.get('project_no') and payload.get('project_no') != self.project_no:
            project = ensure_project(payload['project_no'], self.company_name)
            self.project_id = project.id
            self.project_no = project.project_no
        return self

    def __repr__(self):
        return f"<MaterialRequisition {self.mr_no}: {self.project_no}>"

class SupplierMaterial(db.Model):
    __tablename__ = 'supplier_material'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    material_name = db.Column(db.String(100), nullable=False)
    material_type = db.Column(db.String(50), nullable=False)
    price = db.Column(db.Float, nullable=False)
    available_qty = db.Column(db.Float, nullable=False)
    unit = db.Column(db.String(20), nullable=False)
    delivery_time_days = db.Column(db.Integer, nullable=True)
    country_code = db.Column(db.String(2), nullable=True)
    company_name = db.Column(db.String(100), nullable=False, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(pytz.UTC))
    updated_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(pytz.UTC), onupdate=lambda: datetime.now(pytz.UTC))
    user = db.relationship('User', backref=db.backref('materials', lazy='dynamic'))

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.validate(kwargs)

    def validate(self, kwargs):
        if 'price' in kwargs and kwargs['price'] <= 0:
            raise ValidationError('Price must be positive')
        if 'available_qty' in kwargs and kwargs['available_qty'] <= 0:
            raise ValidationError('Available quantity must be positive')
        if 'material_name' in kwargs and not kwargs['material_name'].strip():
            raise ValidationError('Material name cannot be empty')
        if 'material_type' in kwargs and not kwargs['material_type'].strip():
            raise ValidationError('Material type cannot be empty')
        if 'unit' in kwargs and not kwargs['unit'].strip():
            raise ValidationError('Unit cannot be empty')
        if 'delivery_time_days' in kwargs and kwargs['delivery_time_days'] is not None and kwargs['delivery_time_days'] <= 0:
            raise ValidationError('Delivery time must be positive')

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'material_name': self.material_name,
            'material_type': self.material_type,
            'price': self.price,
            'available_qty': self.available_qty,
            'unit': self.unit,
            'delivery_time_days': self.delivery_time_days,
            'country_code': self.country_code,
            'company_name': self.company_name,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }

    def __repr__(self):
        return f"<SupplierMaterial {self.material_name}: {self.user_id}>"

class PurchaseOrder(db.Model):
    __tablename__ = 'purchase_order'
    id = db.Column(db.Integer, primary_key=True)
    order_no = db.Column(db.String(50), unique=True, nullable=False, index=True)
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    supplier_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    status = db.Column(Enum(PurchaseOrderStatus), nullable=False, default=PurchaseOrderStatus.pending)
    total_price = db.Column(db.Float, nullable=False)
    issued_date = db.Column(db.Date, nullable=True)
    delivered_date = db.Column(db.Date, nullable=True)
    remarks = db.Column(db.Text, nullable=True)
    company_name = db.Column(db.String(100), nullable=False, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(pytz.UTC))
    updated_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(pytz.UTC), onupdate=lambda: datetime.now(pytz.UTC))
    project = db.relationship('Project', backref=db.backref('purchase_orders', lazy=True))
    user = db.relationship('User', foreign_keys=[user_id], backref=db.backref('my_purchase_orders', lazy=True))
    supplier = db.relationship('User', foreign_keys=[supplier_id], backref=db.backref('received_orders', lazy=True))
    items = db.relationship('PurchaseOrderItem', backref='purchase_order', lazy=True)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.validate(kwargs)

    def validate(self, kwargs):
        if 'order_no' in kwargs and not re.match(r'^PO-\d{4,}$', kwargs['order_no']):
            raise ValidationError('Purchase order number must be in format PO-XXXX (numbers)')
        if 'total_price' in kwargs and kwargs['total_price'] < 0:
            raise ValidationError('Total price cannot be negative')

    def to_dict(self):
        return {
            'id': self.id,
            'order_no': self.order_no,
            'project_id': self.project_id,
            'user_id': self.user_id,
            'supplier_id': self.supplier_id,
            'status': self.status.value,
            'total_price': self.total_price,
            'issued_date': self.issued_date.isoformat() if self.issued_date else None,
            'delivered_date': self.delivered_date.isoformat() if self.delivered_date else None,
            'remarks': self.remarks,
            'company_name': self.company_name,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'items': [item.to_dict() for item in self.items]
        }

    def __repr__(self):
        return f"<PurchaseOrder {self.order_no}: {self.status.value}>"

class PurchaseOrderItem(db.Model):
    __tablename__ = 'purchase_order_item'
    id = db.Column(db.Integer, primary_key=True)
    purchase_order_id = db.Column(db.Integer, db.ForeignKey('purchase_order.id'), nullable=False, index=True)
    material_requisition_id = db.Column(db.Integer, db.ForeignKey('material_requisition.id'), nullable=False, index=True)
    quantity = db.Column(db.Float, nullable=False)
    unit_price = db.Column(db.Float, nullable=False)
    material_requisition = db.relationship('MaterialRequisition', backref=db.backref('purchase_order_items', lazy=True))

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.validate(kwargs)

    def validate(self, kwargs):
        if 'quantity' in kwargs and kwargs['quantity'] <= 0:
            raise ValidationError('Quantity must be positive')
        if 'unit_price' in kwargs and kwargs['unit_price'] < 0:
            raise ValidationError('Unit price cannot be negative')

    def to_dict(self):
        return {
            'id': self.id,
            'purchase_order_id': self.purchase_order_id,
            'material_requisition_id': self.material_requisition_id,
            'quantity': self.quantity,
            'unit_price': self.unit_price
        }

    def __repr__(self):
        return f"<PurchaseOrderItem PO:{self.purchase_order_id} MR:{self.material_requisition_id}>"

class QualityControl(db.Model):
    __tablename__ = 'quality_control'
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('purchase_order.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    status = db.Column(Enum(InspectionStatus), nullable=False, default=InspectionStatus.pending)
    inspected_date = db.Column(db.Date, nullable=True)
    remarks = db.Column(db.Text, nullable=True)
    company_name = db.Column(db.String(100), nullable=False, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(pytz.UTC))
    updated_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(pytz.UTC), onupdate=lambda: datetime.now(pytz.UTC))
    order = db.relationship('PurchaseOrder', backref=db.backref('quality_controls', lazy=True))
    user = db.relationship('User', backref=db.backref('quality_controls', lazy=True))

    def to_dict(self):
        return {
            'id': self.id,
            'order_id': self.order_id,
            'user_id': self.user_id,
            'status': self.status.value,
            'inspected_date': self.inspected_date.isoformat() if self.inspected_date else None,
            'remarks': self.remarks,
            'company_name': self.company_name,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }

    def __repr__(self):
        return f"<QualityControl Order:{self.order_id} Status:{self.status.value}>"

class Delivery(db.Model):
    __tablename__ = 'delivery'
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('purchase_order.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    delivery_id = db.Column(db.String(50), unique=True, nullable=False, index=True)
    status = db.Column(Enum(DeliveryStatus), nullable=False, default=DeliveryStatus.pending)
    delivered_date = db.Column(db.Date, nullable=True)
    remarks = db.Column(db.Text, nullable=True)
    company_name = db.Column(db.String(100), nullable=False, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(pytz.UTC))
    updated_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(pytz.UTC), onupdate=lambda: datetime.now(pytz.UTC))
    order = db.relationship('PurchaseOrder', backref=db.backref('deliveries', lazy=True))
    user = db.relationship('User', backref=db.backref('deliveries', lazy=True))

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.validate(kwargs)

    def validate(self, kwargs):
        if 'delivery_id' in kwargs and not re.match(r'^DLV-\d{4,}$', kwargs['delivery_id']):
            raise ValidationError('Delivery ID must be in format DLV-XXXX (numbers)')

    def to_dict(self):
        return {
            'id': self.id,
            'order_id': self.order_id,
            'user_id': self.user_id,
            'delivery_id': self.delivery_id,
            'status': self.status.value,
            'delivered_date': self.delivered_date.isoformat() if self.delivered_date else None,
            'remarks': self.remarks,
            'company_name': self.company_name,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }

    def __repr__(self):
        return f"<Delivery {self.order_id}: {self.status}>"

class WarehouseInventory(db.Model):
    __tablename__ = 'warehouse_inventory'
    id = db.Column(db.Integer, primary_key=True)
    warehouse_id = db.Column(db.String(50), unique=True, nullable=False, index=True)
    delivery_id = db.Column(db.String(50), db.ForeignKey('delivery.delivery_id'), nullable=False, index=True)
    item_code = db.Column(db.String(50), nullable=False, index=True)
    material_description = db.Column(db.Text, nullable=False)
    material_category = db.Column(db.String(50))
    received_qty = db.Column(db.Float, nullable=False)
    unit = db.Column(db.String(50), nullable=False)
    storage_location_id = db.Column(db.String(100), nullable=True)
    receipt_date = db.Column(db.Date, nullable=False)
    project_no = db.Column(db.String(50), nullable=False, index=True)
    reason = db.Column(db.Text, nullable=True)
    remarks = db.Column(db.Text, nullable=True)
    workflow_status = db.Column(Enum(WorkflowStatus), nullable=False, default=WorkflowStatus.warehouse)
    company_name = db.Column(db.String(100), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(pytz.UTC))
    updated_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(pytz.UTC), onupdate=lambda: datetime.now(pytz.UTC))
    delivery = db.relationship('Delivery', backref=db.backref('warehouse_entries', lazy=True))
    user = db.relationship('User', backref=db.backref('warehouse_entries', lazy=True))

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.validate(kwargs)

    def validate(self, kwargs):
        if 'warehouse_id' in kwargs and not re.match(r'^WH-\d{4,}$', kwargs['warehouse_id']):
            raise ValidationError('Warehouse ID must be in format WH-XXXX (numbers)')
        if 'received_qty' in kwargs and kwargs['received_qty'] <= 0:
            raise ValidationError('Received quantity must be positive')
        if  'item_code' in kwargs and 'item_code' in kwargs and not kwargs['item_code'].strip():
            raise ValidationError('Item code cannot be empty')
        if 'material_description' in kwargs and not kwargs['material_description'].strip():
            raise ValidationError('Material description cannot be empty')

    def to_dict(self):
        return {
            'id': self.id,
            'warehouse_id': self.warehouse_id,
            'delivery_id': self.delivery_id,
            'item_code': self.item_code,
            'material_description': self.material_description,
            'material_category': self.material_category,
            'received_qty': self.received_qty,
            'unit': self.unit,
            'storage_location_id': self.storage_location_id,
            'receipt_date': self.receipt_date.isoformat() if self.receipt_date else None,
            'project_no': self.project_no,
            'reason': self.reason,
            'remarks': self.remarks,
            'workflow_status': self.workflow_status.value,
            'company_name': self.company_name,
            'user_id': self.user_id,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }

    CSV_FIELDS = (
        'warehouse_id', 'delivery_id', 'item_code', 'material_description',
        'material_category', 'received_qty', 'unit', 'storage_location_id',
        'receipt_date', 'project_no', 'reason', 'remarks', 'workflow_status',
    )

    @classmethod
    def csv_fields(cls):
        return list(cls.CSV_FIELDS)

    @classmethod
    def csv_headers(cls):
        return [field.replace('_', ' ').title() for field in cls.CSV_FIELDS]

    @property
    def received_quantity(self):
        return self.received_qty

    @received_quantity.setter
    def received_quantity(self, value):
        self.received_qty = value

    @classmethod
    def from_dict(cls, data, company_name, user_id):
        payload = dict(data or {})
        qty = _parse_float(payload.get('received_qty', payload.get('received_quantity')), 0)
        receipt_date = _parse_date(payload.get('receipt_date')) or date.today()
        return cls(
            warehouse_id=payload.get('warehouse_id'),
            delivery_id=str(payload.get('delivery_id') or ''),
            item_code=(payload.get('item_code') or '').strip(),
            material_description=(payload.get('material_description') or '').strip(),
            material_category=payload.get('material_category') or payload.get('category'),
            received_qty=qty,
            unit=payload.get('unit') or payload.get('unit_of_measure') or 'EA',
            storage_location_id=payload.get('storage_location_id'),
            receipt_date=receipt_date,
            project_no=payload.get('project_no') or 'UNASSIGNED',
            reason=payload.get('reason'),
            remarks=payload.get('remarks'),
            workflow_status=_parse_enum(WorkflowStatus, payload.get('workflow_status'), WorkflowStatus.warehouse),
            company_name=company_name,
            user_id=int(user_id),
        )

    def update_from_dict(self, data):
        payload = dict(data or {})
        if 'received_quantity' in payload and 'received_qty' not in payload:
            payload['received_qty'] = payload['received_quantity']
        assignable = {
            'item_code', 'material_description', 'material_category',
            'received_qty', 'unit', 'storage_location_id', 'project_no',
            'reason', 'remarks', 'delivery_id',
        }
        for key in assignable:
            if key not in payload:
                continue
            value = payload[key]
            if key == 'received_qty':
                value = _parse_float(value, self.received_qty)
            setattr(self, key, value)
        if 'receipt_date' in payload:
            parsed = _parse_date(payload.get('receipt_date'))
            if parsed:
                self.receipt_date = parsed
        if 'workflow_status' in payload:
            parsed_status = _parse_enum(WorkflowStatus, payload.get('workflow_status'), self.workflow_status)
            if parsed_status:
                self.workflow_status = parsed_status
        return self

    def __repr__(self):
        return f"<WarehouseInventory {self.warehouse_id}: {self.material_description}>"

class Approval(db.Model):
    __tablename__ = 'approval'
    id = db.Column(db.Integer, primary_key=True)
    requisition_id = db.Column(db.Integer, db.ForeignKey('material_requisition.id'), nullable=False, index=True)
    approver_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    status = db.Column(Enum(ApprovalStatus), nullable=False, default=ApprovalStatus.pending)
    approved_date = db.Column(db.Date, nullable=True)
    remarks = db.Column(db.Text, nullable=True)
    company_name = db.Column(db.String(100), nullable=False, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(pytz.UTC))
    updated_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(pytz.UTC), onupdate=lambda: datetime.now(pytz.UTC))
    requisition = db.relationship('MaterialRequisition', backref=db.backref('approvals', lazy=True))
    approver = db.relationship('User', backref=db.backref('approvals', lazy=True))

    def to_dict(self):
        return {
            'id': self.id,
            'requisition_id': self.requisition_id,
            'approver_id': self.approver_id,
            'status': self.status.value,
            'approved_date': self.approved_date.isoformat() if self.approved_date else None,
            'remarks': self.remarks,
            'company_name': self.company_name,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }

    def __repr__(self):
        return f"<Approval Req:{self.requisition_id} Approver:{self.approver_id} Status:{self.status.value}>"

class Tender(db.Model):
    __tablename__ = 'tender'
    id = db.Column(db.Integer, primary_key=True)
    tender_no = db.Column(db.String(50), unique=True, nullable=False, index=True)
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'), nullable=False, index=True)
    material_requisition_id = db.Column(db.Integer, db.ForeignKey('material_requisition.id'), nullable=False, index=True)
    status = db.Column(Enum(TenderStatus), nullable=False, default=TenderStatus.open)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    company_name = db.Column(db.String(100), nullable=False, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(pytz.UTC))
    updated_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(pytz.UTC), onupdate=lambda: datetime.now(pytz.UTC))
    project = db.relationship('Project', backref=db.backref('tenders', lazy=True))
    material_requisition = db.relationship('MaterialRequisition', backref=db.backref('tenders', lazy=True))
    creator = db.relationship('User', backref=db.backref('tenders_created', lazy=True))

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.validate(kwargs)

    def validate(self, kwargs):
        if 'tender_no' in kwargs and not re.match(r'^TND-\d{4,}$', kwargs['tender_no']):
            raise ValidationError('Tender number must be in format TND-XXXX (numbers)')

    def to_dict(self):
        return {
            'id': self.id,
            'tender_no': self.tender_no,
            'project_id': self.project_id,
            'material_requisition_id': self.material_requisition_id,
            'status': self.status.value,
            'created_by': self.created_by,
            'company_name': self.company_name,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }

    def __repr__(self):
        return f"<Tender {self.tender_no}: {self.status.value}>"

class Bid(db.Model):
    __tablename__ = 'bid'
    id = db.Column(db.Integer, primary_key=True)
    tender_id = db.Column(db.Integer, db.ForeignKey('tender.id'), nullable=False, index=True)
    supplier_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    bid_amount = db.Column(db.Float, nullable=False)
    status = db.Column(Enum(BidStatus), nullable=False, default=BidStatus.pending)
    company_name = db.Column(db.String(100), nullable=False, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(pytz.UTC))
    updated_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(pytz.UTC), onupdate=lambda: datetime.now(pytz.UTC))
    tender = db.relationship('Tender', backref=db.backref('bids', lazy=True))
    supplier = db.relationship('User', backref=db.backref('bids', lazy=True))

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.validate(kwargs)

    def validate(self, kwargs):
        if 'bid_amount' in kwargs and kwargs['bid_amount'] <= 0:
            raise ValidationError('Bid amount must be positive')

    def to_dict(self):
        return {
            'id': self.id,
            'tender_id': self.tender_id,
            'supplier_id': self.supplier_id,
            'bid_amount': self.bid_amount,
            'status': self.status.value,
            'company_name': self.company_name,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }

    def __repr__(self):
        return f"<Bid Tender:{self.tender_id} Supplier:{self.supplier_id} Status:{self.status.value}>"

class User(db.Model, UserMixin):
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True)
    company_name = db.Column(db.String(100), nullable=False, index=True)
    company_email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    company_phone = db.Column(db.String(20), nullable=True)
    full_name = db.Column(db.String(100), nullable=False)
    company_address = db.Column(db.String(200), nullable=False)
    country = db.Column(db.String(2), nullable=False)
    access_level = db.Column(Enum(AccessLevel), nullable=False)
    store_name = db.Column(db.String(100), nullable=True)
    is_admin = db.Column(db.Boolean, default=False)
    password_hash = db.Column(db.String(128), nullable=True)
    totp_secret = db.Column(db.String(32), nullable=True)
    qr_code_base64 = db.Column(db.Text, nullable=True)
    totp_confirmed = db.Column(db.Boolean, default=False)
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'), nullable=True, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(pytz.UTC))
    updated_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(pytz.UTC), onupdate=lambda: datetime.now(pytz.UTC))
    project = db.relationship('Project', backref=db.backref('users', lazy=True))

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.validate(kwargs)

    def validate(self, kwargs):
        if 'company_email' in kwargs:
            self.validate_email(kwargs['company_email'])
        if 'company_phone' in kwargs and kwargs['company_phone']:
            self.validate_phone(kwargs['company_phone'])
        if 'password' in kwargs:
            self.set_password(kwargs['password'])
        if 'full_name' in kwargs and not kwargs['full_name'].strip():
            raise ValidationError('Full name cannot be empty')
        if 'company_address' in kwargs and not kwargs['company_address'].strip():
            raise ValidationError('Company address cannot be empty')
        if 'country' in kwargs and not kwargs['country'].strip():
            raise ValidationError('Country cannot be empty')

    def set_password(self, password):
        from werkzeug.security import generate_password_hash
        if password:
            if len(password) < 8:
                raise ValidationError('Password must be at least 8 characters long')
            self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        from werkzeug.security import check_password_hash
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)

    def validate_email(self, email):
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(pattern, email):
            raise ValidationError('Invalid email format')
        return email

    def validate_phone(self, phone):
        pattern = r'^\+?[1-9]\d{1,14}$'
        if not re.match(pattern, phone):
            raise ValidationError('Invalid phone number format')
        return phone

    def get_totp_uri(self):
        if not self.totp_secret:
            raise ValidationError('TOTP secret not set')
        return f"otpauth://totp/MaterialHub:{self.company_email}?secret={self.totp_secret}&issuer=MaterialHub"

    def to_dict(self):
        return {
            'id': self.id,
            'company_name': self.company_name,
            'company_email': self.company_email,
            'company_phone': self.company_phone,
            'full_name': self.full_name,
            'company_address': self.company_address,
            'country': self.country,
            'access_level': self.access_level.value,
            'store_name': self.store_name,
            'is_admin': self.is_admin,
            'totp_confirmed': self.totp_confirmed,
            'project_id': self.project_id,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }

    @property
    def is_active(self):
        return True

    @property
    def is_authenticated(self):
        return True

    @property
    def is_anonymous(self):
        return False

    def get_id(self):
        return str(self.id)

    def __repr__(self):
        return f"<User {self.company_email}: {self.access_level.value}>"


class ContactInquiry(db.Model):
    """Inbound demo / sales requests from the public growth funnel."""
    __tablename__ = 'contact_inquiry'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), nullable=False, index=True)
    company = db.Column(db.String(120), nullable=True)
    message = db.Column(db.Text, nullable=True)
    source = db.Column(db.String(50), nullable=False, default='website')
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(pytz.UTC))

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'email': self.email,
            'company': self.company,
            'message': self.message,
            'source': self.source,
            'created_at': self.created_at.isoformat(),
        }

    def __repr__(self):
        return f"<ContactInquiry {self.email}>"
