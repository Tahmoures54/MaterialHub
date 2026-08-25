"""MaterialHub intelligence, traceability and procurement models.
Designed as an additive vNext layer so the original application remains compatible.
"""
import enum
from datetime import datetime
import pytz
from extensions import db

class RecordStatus(enum.Enum):
    draft='draft'; active='active'; approved='approved'; rejected='rejected'; closed='closed'

class DocumentType(enum.Enum):
    MTC='MTC'; COC='CoC'; DATASHEET='Datasheet'; DRAWING='Drawing'; OTHER='Other'

class MatchStatus(enum.Enum):
    pending='pending'; matched='matched'; exception='exception'

class RFQStatus(enum.Enum):
    draft='draft'; sent='sent'; quoted='quoted'; awarded='awarded'; closed='closed'

class MaterialTrace(db.Model):
    __tablename__='material_trace'
    id=db.Column(db.Integer,primary_key=True)
    trace_code=db.Column(db.String(80),unique=True,nullable=False,index=True)
    item_code=db.Column(db.String(80),nullable=False,index=True)
    material_description=db.Column(db.Text,nullable=False)
    heat_no=db.Column(db.String(80),index=True)
    lot_no=db.Column(db.String(80),index=True)
    serial_no=db.Column(db.String(80),index=True)
    batch_no=db.Column(db.String(80),index=True)
    quantity=db.Column(db.Float,default=0)
    unit=db.Column(db.String(20))
    po_no=db.Column(db.String(50),index=True)
    delivery_id=db.Column(db.String(50),index=True)
    warehouse_id=db.Column(db.String(50),index=True)
    supplier_name=db.Column(db.String(150))
    project_no=db.Column(db.String(50),index=True)
    status=db.Column(db.String(30),default='active')
    company_name=db.Column(db.String(100),index=True)
    created_at=db.Column(db.DateTime,default=lambda:datetime.now(pytz.UTC),nullable=False)
    updated_at=db.Column(db.DateTime,default=lambda:datetime.now(pytz.UTC),onupdate=lambda:datetime.now(pytz.UTC),nullable=False)

class MaterialDocument(db.Model):
    __tablename__='material_document'
    id=db.Column(db.Integer,primary_key=True)
    trace_id=db.Column(db.Integer,db.ForeignKey('material_trace.id'),index=True)
    document_type=db.Column(db.Enum(DocumentType),nullable=False)
    document_no=db.Column(db.String(100))
    file_name=db.Column(db.String(255),nullable=False)
    file_path=db.Column(db.String(500))
    revision=db.Column(db.String(30))
    issue_date=db.Column(db.Date)
    expiry_date=db.Column(db.Date)
    approved=db.Column(db.Boolean,default=False)
    remarks=db.Column(db.Text)
    company_name=db.Column(db.String(100),index=True)
    created_at=db.Column(db.DateTime,default=lambda:datetime.now(pytz.UTC),nullable=False)
    trace=db.relationship('MaterialTrace',backref=db.backref('documents',lazy=True))

class SupplierScore(db.Model):
    __tablename__='supplier_score'
    id=db.Column(db.Integer,primary_key=True)
    supplier_id=db.Column(db.Integer,db.ForeignKey('user.id'),nullable=False,index=True)
    period=db.Column(db.String(20),nullable=False,index=True)
    quality_score=db.Column(db.Float,default=0)
    otif_score=db.Column(db.Float,default=0)
    price_score=db.Column(db.Float,default=0)
    responsiveness_score=db.Column(db.Float,default=0)
    lead_time_score=db.Column(db.Float,default=0)
    overall_score=db.Column(db.Float,default=0,index=True)
    orders_count=db.Column(db.Integer,default=0)
    company_name=db.Column(db.String(100),index=True)
    created_at=db.Column(db.DateTime,default=lambda:datetime.now(pytz.UTC),nullable=False)
    supplier=db.relationship('User',backref=db.backref('supplier_scores',lazy=True))

class RFQ(db.Model):
    __tablename__='rfq'
    id=db.Column(db.Integer,primary_key=True)
    rfq_no=db.Column(db.String(50),unique=True,nullable=False,index=True)
    mr_id=db.Column(db.Integer,db.ForeignKey('material_requisition.id'),nullable=False,index=True)
    status=db.Column(db.Enum(RFQStatus),default=RFQStatus.draft,nullable=False)
    due_date=db.Column(db.Date)
    target_quantity=db.Column(db.Float,default=0)
    unit=db.Column(db.String(20))
    specification=db.Column(db.Text)
    company_name=db.Column(db.String(100),index=True)
    created_by=db.Column(db.Integer,db.ForeignKey('user.id'),nullable=False)
    created_at=db.Column(db.DateTime,default=lambda:datetime.now(pytz.UTC),nullable=False)
    mr=db.relationship('MaterialRequisition',backref=db.backref('rfqs',lazy=True))
    creator=db.relationship('User',foreign_keys=[created_by])

class RFQSupplier(db.Model):
    __tablename__='rfq_supplier'
    id=db.Column(db.Integer,primary_key=True)
    rfq_id=db.Column(db.Integer,db.ForeignKey('rfq.id'),nullable=False,index=True)
    supplier_id=db.Column(db.Integer,db.ForeignKey('user.id'),nullable=False,index=True)
    invited_at=db.Column(db.DateTime,default=lambda:datetime.now(pytz.UTC))
    quoted_at=db.Column(db.DateTime)
    quoted_price=db.Column(db.Float)
    quoted_qty=db.Column(db.Float)
    lead_time_days=db.Column(db.Integer)
    quality_score=db.Column(db.Float,default=0)
    commercial_score=db.Column(db.Float,default=0)
    total_score=db.Column(db.Float,default=0,index=True)
    status=db.Column(db.String(20),default='invited')
    rfq=db.relationship('RFQ',backref=db.backref('supplier_quotes',lazy=True))
    supplier=db.relationship('User',backref=db.backref('rfq_quotes',lazy=True))

class Receipt(db.Model):
    __tablename__='material_receipt'
    id=db.Column(db.Integer,primary_key=True)
    receipt_no=db.Column(db.String(50),unique=True,nullable=False,index=True)
    po_id=db.Column(db.Integer,db.ForeignKey('purchase_order.id'),nullable=False,index=True)
    received_qty=db.Column(db.Float,default=0)
    receipt_date=db.Column(db.Date)
    accepted_qty=db.Column(db.Float,default=0)
    rejected_qty=db.Column(db.Float,default=0)
    company_name=db.Column(db.String(100),index=True)
    po=db.relationship('PurchaseOrder',backref=db.backref('material_receipts',lazy=True))

class SupplierInvoice(db.Model):
    __tablename__='supplier_invoice'
    id=db.Column(db.Integer,primary_key=True)
    invoice_no=db.Column(db.String(80),unique=True,nullable=False,index=True)
    po_id=db.Column(db.Integer,db.ForeignKey('purchase_order.id'),nullable=False,index=True)
    invoice_amount=db.Column(db.Float,default=0)
    invoice_date=db.Column(db.Date)
    status=db.Column(db.Enum(MatchStatus),default=MatchStatus.pending)
    variance_amount=db.Column(db.Float,default=0)
    company_name=db.Column(db.String(100),index=True)
    po=db.relationship('PurchaseOrder',backref=db.backref('supplier_invoices',lazy=True))

class ThreeWayMatch(db.Model):
    __tablename__='three_way_match'
    id=db.Column(db.Integer,primary_key=True)
    po_id=db.Column(db.Integer,db.ForeignKey('purchase_order.id'),nullable=False,index=True)
    receipt_id=db.Column(db.Integer,db.ForeignKey('material_receipt.id'))
    invoice_id=db.Column(db.Integer,db.ForeignKey('supplier_invoice.id'))
    po_amount=db.Column(db.Float,default=0)
    receipt_amount=db.Column(db.Float,default=0)
    invoice_amount=db.Column(db.Float,default=0)
    variance_amount=db.Column(db.Float,default=0)
    status=db.Column(db.Enum(MatchStatus),default=MatchStatus.pending,index=True)
    notes=db.Column(db.Text)
    created_at=db.Column(db.DateTime,default=lambda:datetime.now(pytz.UTC),nullable=False)
    po=db.relationship('PurchaseOrder')
    receipt=db.relationship('Receipt')
    invoice=db.relationship('SupplierInvoice')

class MaterialPriceHistory(db.Model):
    __tablename__='material_price_history'
    id=db.Column(db.Integer,primary_key=True)
    item_code=db.Column(db.String(80),nullable=False,index=True)
    material_description=db.Column(db.Text)
    supplier_id=db.Column(db.Integer,db.ForeignKey('user.id'),index=True)
    price=db.Column(db.Float,nullable=False)
    currency=db.Column(db.String(10),default='USD')
    unit=db.Column(db.String(20))
    lead_time_days=db.Column(db.Integer)
    source_type=db.Column(db.String(30),default='quote')
    recorded_at=db.Column(db.DateTime,default=lambda:datetime.now(pytz.UTC),nullable=False,index=True)
    company_name=db.Column(db.String(100),index=True)
    supplier=db.relationship('User')

class ScheduleRisk(db.Model):
    __tablename__='schedule_risk'
    id=db.Column(db.Integer,primary_key=True)
    item_code=db.Column(db.String(80),nullable=False,index=True)
    material_description=db.Column(db.Text)
    required_date=db.Column(db.Date)
    expected_available_date=db.Column(db.Date)
    current_stock=db.Column(db.Float,default=0)
    required_qty=db.Column(db.Float,default=0)
    coverage_qty=db.Column(db.Float,default=0)
    risk_score=db.Column(db.Float,default=0,index=True)
    days_to_risk=db.Column(db.Integer)
    reason=db.Column(db.Text)
    recommended_action=db.Column(db.Text)
    project_no=db.Column(db.String(50),index=True)
    company_name=db.Column(db.String(100),index=True)
    created_at=db.Column(db.DateTime,default=lambda:datetime.now(pytz.UTC),nullable=False)
