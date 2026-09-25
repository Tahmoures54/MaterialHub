from flask import Blueprint, render_template, request, jsonify, send_file
from flask_login import login_required, current_user
from flask_wtf.csrf import validate_csrf, CSRFError
from io import StringIO
import csv
import logging
from datetime import datetime
from models import (db, WarehouseInventory, WarehouseTransaction, Delivery, MaterialMaster,
                    WorkflowStatus, AccessLevel, ValidationError, PurchaseOrder, InspectionStatus,
                    PackingList, PackingListLine, GoodsReceipt, GoodsReceiptLine,
                    OSDReport, OSDReportLine, ReceivingStatus, OSDStatus)

# Configure logging
logger = logging.getLogger(__name__)
warehouse_bp = Blueprint('warehouse', __name__, template_folder='templates')

@warehouse_bp.route('/', methods=['GET'])
@warehouse_bp.route('/warehouse', methods=['GET'])
@login_required
def warehouse():
    """Redirect to warehouse operations dashboard."""
    return warehouse_operations()

@warehouse_bp.route('/warehouse_operations', methods=['GET'])
@login_required
def warehouse_operations():
    """Render the warehouse operations dashboard."""
    try:
        logger.info(f"User {current_user.id} ({current_user.company_email}) accessing warehouse operations dashboard")
        read_only = current_user.access_level != AccessLevel.warehouse
        return render_template('dashboard/warehouse_operations.html', read_only=read_only,
            company_name=current_user.company_name,
        )
    except Exception as e:
        logger.exception('Warehouse operations page failed')
        return render_template('errors/500.html'), 500
