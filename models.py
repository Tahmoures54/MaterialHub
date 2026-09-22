import enum
import re
from datetime import date, datetime, timedelta
import pytz
import base64
import hashlib
from cryptography.fernet import Fernet, InvalidToken
from config.config import Config
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
    __table_args__ = (
        db.UniqueConstraint('project_no', 'company_name', name='uq_project_no_company'),
        {"extend_existing": True},
    )
    id = db.Column(db.Integer, primary_key=True)
    project_no = db.Column(db.String(50), nullable=False, index=True)
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


class DocumentSequence(db.Model):
    """Per-tenant monotonic counters for sequential document numbers.

    Rows are keyed by (document type, company) so that each tenant owns an
    independent MR/PO/DLV/WH sequence. The counter is incremented with a
    single UPDATE statement, which makes allocation safe under concurrent
    requests (unlike reading the last document number first).
    """
    __tablename__ = 'document_sequence'
    key = db.Column(db.String(10), primary_key=True)
    company_name = db.Column(db.String(100), primary_key=True)
    last_value = db.Column(db.Integer, nullable=False, default=0)

    def next_value(self):
        """Atomically claim and return the next sequence value for this tenant."""
        from sqlalchemy import select, update
        db.session.execute(
            update(DocumentSequence)
            .where(DocumentSequence.key == self.key,
                   DocumentSequence.company_name == self.company_name)
            .values(last_value=DocumentSequence.last_value + 1)
        )
        # Read back through Core so we always see the committed increment
        # even if an ORM instance with a stale attribute is in the identity map.
        return db.session.execute(
            select(DocumentSequence.last_value)
            .where(DocumentSequence.key == self.key,
                   DocumentSequence.company_name == self.company_name)
        ).scalar_one()


class MaterialRequisition(db.Model):
    __tablename__ = 'material_requisition'
    __table_args__ = (
        db.UniqueConstraint('mr_no', 'company_name', name='uq_mr_no_company'),
        {"extend_existing": True},
    )
    id = db.Column(db.Integer, primary_key=True)
    mr_no = db.Column(db.String(50), nullable=False, index=True)
    subject = db.Column(db.String(200), nullable=False)
    drawing_no = db.Column(db.String(50))
    drawing_revision = db.Column(db.String(10))
    drawing_page = db.Column(db.String(10))
    material_type = db.Column(db.String(50))
    material_id = db.Column(db.Integer, db.ForeignKey('material_master.id'), nullable=False, index=True)
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
    material = db.relationship('MaterialMaster', foreign_keys=[material_id], backref=db.backref('requisitions', lazy=True))
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
            'material_id': self.material_id,
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


class MaterialMaster(db.Model):
    """Tenant-scoped material master with stable internal identity and standards mapping."""
    __tablename__ = 'material_master'
    __table_args__ = (
        db.UniqueConstraint('material_code', 'company_name', name='uq_material_master_code_company'),
        db.UniqueConstraint('fingerprint', 'company_name', name='uq_material_master_fingerprint_company'),
        {"extend_existing": True},
    )
    id = db.Column(db.Integer, primary_key=True)
    material_code = db.Column(db.String(50), nullable=False, index=True)
    family_code = db.Column(db.String(20), nullable=False, index=True)
    material_name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    unit = db.Column(db.String(20), nullable=False, default='EA')
    material_group = db.Column(db.String(100), nullable=True, index=True)
    discipline = db.Column(db.String(50), nullable=True, index=True)
    unspsc_code = db.Column(db.String(20), nullable=True, index=True)
    eclass_code = db.Column(db.String(50), nullable=True, index=True)
    etim_class = db.Column(db.String(50), nullable=True, index=True)
    standard = db.Column(db.String(100), nullable=True)
    grade = db.Column(db.String(100), nullable=True)
    size = db.Column(db.String(50), nullable=True)
    schedule = db.Column(db.String(50), nullable=True)
    manufacturer = db.Column(db.String(150), nullable=True)
    manufacturer_part_no = db.Column(db.String(100), nullable=True)
    supplier_material_no = db.Column(db.String(100), nullable=True, index=True)
    revision = db.Column(db.String(30), nullable=True)
    certificate_required = db.Column(db.Boolean, nullable=False, default=False)
    inspection_required = db.Column(db.Boolean, nullable=False, default=False)
    lot_control = db.Column(db.Boolean, nullable=False, default=False)
    heat_control = db.Column(db.Boolean, nullable=False, default=False)
    serial_control = db.Column(db.Boolean, nullable=False, default=False)
    quarantine_allowed = db.Column(db.Boolean, nullable=False, default=True)
    project_peg_required = db.Column(db.Boolean, nullable=False, default=False)
    lifecycle_status = db.Column(db.String(20), nullable=False, default='active', index=True)
    attributes = db.Column(db.Text, nullable=True)
    fingerprint = db.Column(db.String(64), nullable=False, index=True)
    status = db.Column(db.String(20), nullable=False, default='active', index=True)
    company_name = db.Column(db.String(100), nullable=False, index=True)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(pytz.UTC))
    updated_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(pytz.UTC), onupdate=lambda: datetime.now(pytz.UTC))
    creator = db.relationship('User', foreign_keys=[created_by])

    def to_dict(self):
        return {
            'id': self.id, 'material_code': self.material_code, 'family_code': self.family_code,
            'material_name': self.material_name, 'description': self.description, 'unit': self.unit,
            'material_group': self.material_group, 'discipline': self.discipline,
            'unspsc_code': self.unspsc_code, 'eclass_code': self.eclass_code, 'etim_class': self.etim_class,
            'standard': self.standard, 'grade': self.grade, 'size': self.size, 'schedule': self.schedule,
            'manufacturer': self.manufacturer, 'manufacturer_part_no': self.manufacturer_part_no,
            'supplier_material_no': self.supplier_material_no, 'revision': self.revision,
            'certificate_required': self.certificate_required, 'inspection_required': self.inspection_required,
            'lot_control': self.lot_control, 'heat_control': self.heat_control,
            'serial_control': self.serial_control, 'quarantine_allowed': self.quarantine_allowed,
            'project_peg_required': self.project_peg_required, 'lifecycle_status': self.lifecycle_status,
            'attributes': self.attributes, 'status': self.status, 'company_name': self.company_name,
            'created_by': self.created_by, 'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }

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
    __table_args__ = (
        db.UniqueConstraint('order_no', 'company_name', name='uq_po_order_no_company'),
        {"extend_existing": True},
    )
    id = db.Column(db.Integer, primary_key=True)
    order_no = db.Column(db.String(50), nullable=False, index=True)
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
    material_id = db.Column(db.Integer, db.ForeignKey('material_master.id'), nullable=False, index=True)
    quantity = db.Column(db.Float, nullable=False)
    unit_price = db.Column(db.Float, nullable=False)
    material_requisition = db.relationship('MaterialRequisition', backref=db.backref('purchase_order_items', lazy=True))
    material = db.relationship('MaterialMaster', foreign_keys=[material_id], backref=db.backref('purchase_order_items', lazy=True))

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
            'material_id': self.material_id,
            'quantity': self.quantity,
            'unit_price': self.unit_price
        }

    def __repr__(self):
        return f"<PurchaseOrderItem PO:{self.purchase_order_id} MR:{self.material_requisition_id}>"

class QualityControl(db.Model):
    __tablename__ = 'quality_control'
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('purchase_order.id'), nullable=False, index=True)
    material_id = db.Column(db.Integer, db.ForeignKey('material_master.id'), nullable=True, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    status = db.Column(Enum(InspectionStatus), nullable=False, default=InspectionStatus.pending)
    inspected_date = db.Column(db.Date, nullable=True)
    remarks = db.Column(db.Text, nullable=True)
    company_name = db.Column(db.String(100), nullable=False, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(pytz.UTC))
    updated_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(pytz.UTC), onupdate=lambda: datetime.now(pytz.UTC))
    order = db.relationship('PurchaseOrder', backref=db.backref('quality_controls', lazy=True))
    material = db.relationship('MaterialMaster', foreign_keys=[material_id], backref=db.backref('quality_controls', lazy=True))
    user = db.relationship('User', backref=db.backref('quality_controls', lazy=True))

    def to_dict(self):
        return {
            'id': self.id,
            'order_id': self.order_id,
            'material_id': self.material_id,
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
    __table_args__ = (
        db.UniqueConstraint('delivery_id', 'company_name', name='uq_delivery_id_company'),
        {"extend_existing": True},
    )
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('purchase_order.id'), nullable=False, index=True)
    material_id = db.Column(db.Integer, db.ForeignKey('material_master.id'), nullable=True, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    delivery_id = db.Column(db.String(50), nullable=False, index=True)
    status = db.Column(Enum(DeliveryStatus), nullable=False, default=DeliveryStatus.pending)
    delivered_date = db.Column(db.Date, nullable=True)
    remarks = db.Column(db.Text, nullable=True)
    company_name = db.Column(db.String(100), nullable=False, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(pytz.UTC))
    updated_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(pytz.UTC), onupdate=lambda: datetime.now(pytz.UTC))
    order = db.relationship('PurchaseOrder', backref=db.backref('deliveries', lazy=True))
    material = db.relationship('MaterialMaster', foreign_keys=[material_id], backref=db.backref('deliveries', lazy=True))
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
            'material_id': self.material_id,
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
    __table_args__ = (
        db.UniqueConstraint('warehouse_id', 'material_id', 'company_name', name='uq_wh_warehouse_material_company'),
        {"extend_existing": True},
    )
    id = db.Column(db.Integer, primary_key=True)
    warehouse_id = db.Column(db.String(50), nullable=False, index=True)
    # Application-level reference to Delivery.delivery_id (tenant-scoped code).
    # Kept as a plain indexed string so delivery numbers stay unique per tenant.
    delivery_id = db.Column(db.String(50), nullable=False, index=True)
    material_id = db.Column(db.Integer, db.ForeignKey('material_master.id'), nullable=True, index=True)
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
    user = db.relationship('User', backref=db.backref('warehouse_entries', lazy=True))
    material = db.relationship('MaterialMaster', foreign_keys=[material_id], backref=db.backref('warehouse_inventory', lazy=True))

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.validate(kwargs)

    def validate(self, kwargs):
        if 'warehouse_id' in kwargs and not re.match(r'^WH-[A-Za-z0-9-]{4,}$', kwargs['warehouse_id']):
            raise ValidationError('Warehouse ID must be in format WH-XXXX (letters, numbers, or hyphens)')
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
            'material_id': self.material_id,
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
            material_id=payload.get('material_id'),
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


class WarehouseTransaction(db.Model):
    """Immutable audit ledger for warehouse stock movements."""
    __tablename__ = 'warehouse_transaction'
    __table_args__ = (
        db.UniqueConstraint('transaction_no', 'company_name', name='uq_warehouse_transaction_no_company'),
        {"extend_existing": True},
    )
    id = db.Column(db.Integer, primary_key=True)
    transaction_no = db.Column(db.String(50), nullable=False, index=True)
    transaction_type = db.Column(db.String(30), nullable=False, index=True)
    warehouse_id = db.Column(db.String(50), nullable=False, index=True)
    material_id = db.Column(db.Integer, db.ForeignKey('material_master.id'), nullable=True, index=True)
    item_code = db.Column(db.String(50), nullable=False, index=True)
    material_description = db.Column(db.Text, nullable=False)
    quantity = db.Column(db.Float, nullable=False)
    unit = db.Column(db.String(50), nullable=False)
    project_no = db.Column(db.String(50), nullable=True, index=True)
    delivery_id = db.Column(db.String(50), nullable=True, index=True)
    contractor = db.Column(db.String(150), nullable=True)
    storage_location_id = db.Column(db.String(100), nullable=True)
    reference_no = db.Column(db.String(100), nullable=True, index=True)
    remarks = db.Column(db.Text, nullable=True)
    company_name = db.Column(db.String(100), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(pytz.UTC))
    balance_before = db.Column(db.Float, nullable=True)
    balance_after = db.Column(db.Float, nullable=True)
    destination_warehouse_id = db.Column(db.String(50), nullable=True, index=True)
    user = db.relationship('User', backref=db.backref('warehouse_transactions', lazy=True))
    material = db.relationship('MaterialMaster', foreign_keys=[material_id], backref=db.backref('warehouse_transactions', lazy=True))

    def to_dict(self):
        return {
            'id': self.id,
            'transaction_no': self.transaction_no,
            'transaction_type': self.transaction_type,
            'warehouse_id': self.warehouse_id,
            'material_id': self.material_id,
            'item_code': self.item_code,
            'material_description': self.material_description,
            'quantity': self.quantity,
            'unit': self.unit,
            'project_no': self.project_no,
            'delivery_id': self.delivery_id,
            'contractor': self.contractor,
            'storage_location_id': self.storage_location_id,
            'reference_no': self.reference_no,
            'remarks': self.remarks,
            'balance_before': self.balance_before,
            'balance_after': self.balance_after,
            'destination_warehouse_id': self.destination_warehouse_id,
            'company_name': self.company_name,
            'user_id': self.user_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }

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
    __table_args__ = (
        db.UniqueConstraint('tender_no', 'company_name', name='uq_tender_no_company'),
        {"extend_existing": True},
    )
    id = db.Column(db.Integer, primary_key=True)
    tender_no = db.Column(db.String(50), nullable=False, index=True)
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
    totp_secret = db.Column(db.String(512), nullable=True)
    qr_code_base64 = db.Column(db.Text, nullable=True)
    totp_confirmed = db.Column(db.Boolean, default=False)
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'), nullable=True, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(pytz.UTC))
    updated_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(pytz.UTC), onupdate=lambda: datetime.now(pytz.UTC))
    trial_started_at = db.Column(db.DateTime, nullable=True, index=True)
    trial_ends_at = db.Column(db.DateTime, nullable=True, index=True)
    subscription_plan = db.Column(db.String(30), nullable=False, default='trial')
    subscription_status = db.Column(db.String(20), nullable=False, default='trial')
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

    @staticmethod
    def _password_hasher():
        from argon2 import PasswordHasher
        return PasswordHasher()

    @staticmethod
    def _totp_cipher():
        key_material = Config.SECRET_KEY.encode('utf-8')
        key = base64.urlsafe_b64encode(hashlib.sha256(key_material).digest())
        return Fernet(key)

    @classmethod
    def encrypt_totp_secret(cls, secret):
        if not secret:
            return None
        return 'enc:' + cls._totp_cipher().encrypt(secret.encode('utf-8')).decode('ascii')

    def decrypt_totp_secret(self):
        if not self.totp_secret:
            raise ValidationError('TOTP secret not set')
        if not self.totp_secret.startswith('enc:'):
            return self.totp_secret
        try:
            return self._totp_cipher().decrypt(
                self.totp_secret[4:].encode('ascii')
            ).decode('utf-8')
        except (InvalidToken, ValueError, UnicodeDecodeError) as exc:
            raise ValidationError('Stored TOTP secret cannot be decrypted') from exc

    def set_totp_secret(self, secret):
        self.totp_secret = self.encrypt_totp_secret(secret)

    def set_password(self, password):
        if password:
            if len(password) < 8:
                raise ValidationError('Password must be at least 8 characters long')
            self.password_hash = self._password_hasher().hash(password)

    def check_password(self, password):
        if not self.password_hash:
            return False
        hasher = self._password_hasher()
        try:
            valid = hasher.verify(self.password_hash, password)
        except Exception:
            from werkzeug.security import check_password_hash
            try:
                valid = check_password_hash(self.password_hash, password)
            except Exception:
                return False
            if valid:
                self.password_hash = hasher.hash(password)
        else:
            if valid and hasher.check_needs_rehash(self.password_hash):
                self.password_hash = hasher.hash(password)
        return bool(valid)

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
        secret = self.decrypt_totp_secret()
        return f"otpauth://totp/MaterialHub:{self.company_email}?secret={secret}&issuer=MaterialHub"

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
    def trial_active(self):
        if self.subscription_status == 'active':
            return True
        if self.subscription_status != 'trial' or not self.trial_ends_at:
            return False
        end = self.trial_ends_at
        if end.tzinfo is None:
            end = pytz.UTC.localize(end)
        return datetime.now(pytz.UTC) < end

    @property
    def trial_days_remaining(self):
        if self.subscription_status == 'active':
            return None
        if not self.trial_ends_at:
            return 0
        end = self.trial_ends_at
        if end.tzinfo is None:
            end = pytz.UTC.localize(end)
        return max(0, (end - datetime.now(pytz.UTC)).days)

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
    # Keep these limits aligned with the public contact form and practical email limits.
    email = db.Column(db.String(254), nullable=False, index=True)
    company = db.Column(db.String(160), nullable=True)
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



class ReportShare(db.Model):
    """Tenant-scoped, revocable share link for a generated report."""
    __tablename__ = 'report_share'
    id = db.Column(db.Integer, primary_key=True)
    token = db.Column(db.String(96), unique=True, nullable=False, index=True)
    company_name = db.Column(db.String(100), nullable=False, index=True)
    report_type = db.Column(db.String(30), nullable=False)
    record_id = db.Column(db.Integer, nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False, index=True)
    revoked_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(pytz.UTC))
    creator = db.relationship('User', foreign_keys=[created_by])


class MaterialRequest(db.Model):
    """A lightweight, shareable request tied to an MR/PO/RFQ/Delivery/WH record."""
    __tablename__ = 'material_request'
    id = db.Column(db.Integer, primary_key=True)
    request_no = db.Column(db.String(50), nullable=False, index=True)
    company_name = db.Column(db.String(100), nullable=False, index=True)
    request_type = db.Column(db.String(30), nullable=False)
    record_id = db.Column(db.Integer, nullable=False)
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), nullable=False, default='pending', index=True)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(pytz.UTC))
    updated_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(pytz.UTC), onupdate=lambda: datetime.now(pytz.UTC))
    creator = db.relationship('User', foreign_keys=[created_by])
    __table_args__ = (db.UniqueConstraint('request_no', 'company_name', name='uq_material_request_no_company'),)
