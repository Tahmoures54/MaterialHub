from flask import Blueprint, render_template, request, jsonify, send_file
from flask_login import login_required, current_user
from flask_wtf.csrf import validate_csrf, CSRFError
from io import StringIO
import csv
import logging
from datetime import datetime
from models import db, WarehouseInventory, Delivery, WorkflowStatus, AccessLevel, ValidationError

# Configure logging
logger = logging.getLogger(__name__)
warehouse_bp = Blueprint('warehouse', __name__, url_prefix='/warehouse', template_folder='templates')

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
        return render_template(
            'warehouse_operations.html',
            company_name=current_user.company_name,
            read_only=read_only,
            current_user=current_user
        )
    except Exception as e:
        logger.error(f"Error rendering warehouse operations for user {current_user.id}: {str(e)}")
        return render_template('500.html', error=str(e)), 500

@warehouse_bp.route('/api/inventory', methods=['GET'])
@login_required
def api_get_inventory():
    """Fetch all warehouse inventory entries for the current user's company."""
    try:
        logger.info(f"User {current_user.id} fetching inventory")
        inventory = WarehouseInventory.query.filter_by(company_name=current_user.company_name).all()
        return jsonify([item.to_dict() for item in inventory]), 200
    except Exception as e:
        logger.error(f"Error fetching inventory for user {current_user.id}: {str(e)}")
        return jsonify({'error': 'Failed to fetch inventory'}), 500

@warehouse_bp.route('/api/inventory', methods=['POST'])
@login_required
def api_receive_inventory():
    """Receive new materials into the warehouse."""
    if current_user.access_level != AccessLevel.warehouse:
        logger.warning(f"Unauthorized access attempt by user {current_user.id} to receive inventory")
        return jsonify({'error': 'Unauthorized'}), 403
    try:
        validate_csrf(request.json.get('csrf_token'))
        data = request.get_json()
        if not data:
            logger.warning(f"No data provided in inventory receive request by user {current_user.id}")
            return jsonify({'error': 'No data provided'}), 400
        if not isinstance(data, list):
            data = [data]
        for item in data:
            if not all(key in item for key in ['warehouse_id', 'delivery_id', 'item_code', 'material_description', 'received_quantity']):
                logger.warning(f"Missing required fields in inventory data for user {current_user.id}")
                return jsonify({'error': 'Missing required fields'}), 400
            inventory = WarehouseInventory.from_dict(item, current_user.company_name, current_user.id)
            db.session.add(inventory)
        db.session.commit()
        logger.info(f"User {current_user.id} received {len(data)} inventory items")
        return jsonify({'message': 'Materials received successfully'}), 201
    except CSRFError:
        logger.error(f"CSRF validation failed for user {current_user.id}")
        return jsonify({'error': 'Invalid CSRF token'}), 403
    except ValidationError as e:
        logger.error(f"Validation error receiving inventory for user {current_user.id}: {str(e)}")
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error receiving inventory for user {current_user.id}: {str(e)}")
        return jsonify({'error': 'Failed to receive materials'}), 500

@warehouse_bp.route('/api/inventory/<warehouse_id>', methods=['PUT'])
@login_required
def api_update_inventory(warehouse_id):
    """Update an existing inventory entry."""
    if current_user.access_level != AccessLevel.warehouse:
        logger.warning(f"Unauthorized update attempt by user {current_user.id} for inventory {warehouse_id}")
        return jsonify({'error': 'Unauthorized'}), 403
    try:
        validate_csrf(request.json.get('csrf_token'))
        inventory = WarehouseInventory.query.filter_by(warehouse_id=warehouse_id, company_name=current_user.company_name).first()
        if not inventory:
            logger.warning(f"Inventory {warehouse_id} not found for user {current_user.id}")
            return jsonify({'error': 'Inventory not found'}), 404
        data = request.get_json()
        if not data:
            logger.warning(f"No data provided in inventory update request by user {current_user.id}")
            return jsonify({'error': 'No data provided'}), 400
        inventory.update_from_dict(data)
        db.session.commit()
        logger.info(f"User {current_user.id} updated inventory {warehouse_id}")
        return jsonify({'message': 'Inventory updated successfully'}), 200
    except CSRFError:
        logger.error(f"CSRF validation failed for user {current_user.id}")
        return jsonify({'error': 'Invalid CSRF token'}), 403
    except ValidationError as e:
        logger.error(f"Validation error updating inventory {warehouse_id} for user {current_user.id}: {str(e)}")
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error updating inventory {warehouse_id} for user {current_user.id}: {str(e)}")
        return jsonify({'error': 'Failed to update inventory'}), 500

@warehouse_bp.route('/api/inventory/<warehouse_id>', methods=['DELETE'])
@login_required
def api_delete_inventory(warehouse_id):
    """Delete an inventory entry."""
    if current_user.access_level != AccessLevel.warehouse:
        logger.warning(f"Unauthorized delete attempt by user {current_user.id} for inventory {warehouse_id}")
        return jsonify({'error': 'Unauthorized'}), 403
    try:
        validate_csrf(request.json.get('csrf_token'))
        inventory = WarehouseInventory.query.filter_by(warehouse_id=warehouse_id, company_name=current_user.company_name).first()
        if not inventory:
            logger.warning(f"Inventory {warehouse_id} not found for user {current_user.id}")
            return jsonify({'error': 'Inventory not found'}), 404
        db.session.delete(inventory)
        db.session.commit()
        logger.info(f"User {current_user.id} deleted inventory {warehouse_id}")
        return jsonify({'message': 'Inventory deleted successfully'}), 200
    except CSRFError:
        logger.error(f"CSRF validation failed for user {current_user.id}")
        return jsonify({'error': 'Invalid CSRF token'}), 403
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error deleting inventory {warehouse_id} for user {current_user.id}: {str(e)}")
        return jsonify({'error': 'Failed to delete inventory'}), 500

@warehouse_bp.route('/api/issue', methods=['POST'])
@login_required
def api_issue_inventory():
    """Issue materials to contractors."""
    if current_user.access_level != AccessLevel.warehouse:
        logger.warning(f"Unauthorized issue attempt by user {current_user.id}")
        return jsonify({'error': 'Unauthorized'}), 403
    try:
        validate_csrf(request.json.get('csrf_token'))
        data = request.get_json()
        if not data:
            logger.warning(f"No data provided in issue request by user {current_user.id}")
            return jsonify({'error': 'No data provided'}), 400
        if not isinstance(data, list):
            data = [data]
        for item in data:
            if 'warehouse_id' not in item or 'issue_quantity' not in item:
                logger.warning(f"Missing required fields in issue data for user {current_user.id}")
                return jsonify({'error': 'Missing required fields'}), 400
            inventory = WarehouseInventory.query.filter_by(warehouse_id=item['warehouse_id'], company_name=current_user.company_name).first()
            if not inventory:
                logger.warning(f"Inventory {item['warehouse_id']} not found for user {current_user.id}")
                return jsonify({'error': f'Inventory {item["warehouse_id"]} not found'}), 404
            issue_quantity = float(item.get('issue_quantity', 0))
            if issue_quantity <= 0:
                logger.warning(f"Invalid issue quantity for {item['warehouse_id']} by user {current_user.id}")
                return jsonify({'error': 'Issue quantity must be positive'}), 400
            if inventory.received_quantity < issue_quantity:
                logger.warning(f"Insufficient stock for {item['warehouse_id']} by user {current_user.id}")
                return jsonify({'error': f'Insufficient stock for {item["warehouse_id"]}'}), 400
            inventory.received_quantity -= issue_quantity
        db.session.commit()
        logger.info(f"User {current_user.id} issued {len(data)} inventory items")
        return jsonify({'message': 'Materials issued successfully'}), 200
    except CSRFError:
        logger.error(f"CSRF validation failed for user {current_user.id}")
        return jsonify({'error': 'Invalid CSRF token'}), 403
    except ValidationError as e:
        logger.error(f"Validation error issuing inventory for user {current_user.id}: {str(e)}")
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error issuing inventory for user {current_user.id}: {str(e)}")
        return jsonify({'error': 'Failed to issue materials'}), 500

@warehouse_bp.route('/api/approve', methods=['POST'])
@login_required
def api_approve_inventory():
    """Approve or reject warehouse operations."""
    if current_user.access_level != AccessLevel.project_manager:
        logger.warning(f"Unauthorized approval attempt by user {current_user.id}")
        return jsonify({'error': 'Unauthorized'}), 403
    try:
        validate_csrf(request.json.get('csrf_token'))
        data = request.get_json()
        if not data or 'warehouse_id' not in data or 'approval_status' not in data:
            logger.warning(f"Missing required fields in approval request by user {current_user.id}")
            return jsonify({'error': 'Missing required fields'}), 400
        inventory = WarehouseInventory.query.filter_by(warehouse_id=data['warehouse_id'], company_name=current_user.company_name).first()
        if not inventory:
            logger.warning(f"Inventory {data['warehouse_id']} not found for user {current_user.id}")
            return jsonify({'error': 'Inventory not found'}), 404
        approval_status = data.get('approval_status')
        if approval_status not in ['Approved', 'Rejected', 'Pending']:
            logger.warning(f"Invalid approval status {approval_status} by user {current_user.id}")
            return jsonify({'error': 'Invalid approval status'}), 400
        inventory.workflow_status = WorkflowStatus[approval_status.lower()]
        db.session.commit()
        logger.info(f"User {current_user.id} set approval status to {approval_status} for inventory {data['warehouse_id']}")
        return jsonify({'message': 'Approval submitted successfully'}), 200
    except CSRFError:
        logger.error(f"CSRF validation failed for user {current_user.id}")
        return jsonify({'error': 'Invalid CSRF token'}), 403
    except KeyError as e:
        logger.error(f"Missing field in approval request by user {current_user.id}: {str(e)}")
        return jsonify({'error': f'Missing field: {str(e)}'}), 400
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error approving inventory for user {current_user.id}: {str(e)}")
        return jsonify({'error': 'Failed to submit approval'}), 500

@warehouse_bp.route('/api/generate_warehouse_id', methods=['GET'])
@login_required
def api_generate_warehouse_id():
    """Generate a unique warehouse ID."""
    try:
        if current_user.access_level != AccessLevel.warehouse:
            logger.warning(f"Unauthorized warehouse ID generation attempt by user {current_user.id}")
            return jsonify({'error': 'Unauthorized'}), 403
        last_item = WarehouseInventory.query.order_by(WarehouseInventory.id.desc()).first()
        if last_item and last_item.warehouse_id.startswith('WH-'):
            last_number = int(last_item.warehouse_id.split('-')[1])
            warehouse_id = f"WH-{last_number + 1:04d}"
        else:
            warehouse_id = "WH-0001"
        logger.info(f"User {current_user.id} generated warehouse ID {warehouse_id}")
        return jsonify({'warehouse_id': warehouse_id}), 200
    except Exception as e:
        logger.error(f"Error generating warehouse ID for user {current_user.id}: {str(e)}")
        return jsonify({'error': 'Failed to generate warehouse ID'}), 500

@warehouse_bp.route('/api/upload_csv', methods=['POST'])
@login_required
def api_upload_csv():
    """Import inventory from CSV."""
    if current_user.access_level != AccessLevel.warehouse:
        logger.warning(f"Unauthorized CSV upload attempt by user {current_user.id}")
        return jsonify({'error': 'Unauthorized'}), 403
    try:
        validate_csrf(request.form.get('csrf_token'))
        if 'file' not in request.files:
            logger.warning(f"No file provided in CSV upload by user {current_user.id}")
            return jsonify({'error': 'No file provided'}), 400
        file = request.files['file']
        if not file.filename.endswith('.csv'):
            logger.warning(f"Invalid file format in CSV upload by user {current_user.id}")
            return jsonify({'error': 'Invalid file format'}), 400
        stream = StringIO(file.stream.read().decode('utf-8'))
        csv_reader = csv.DictReader(stream, fieldnames=WarehouseInventory.csv_fields())
        next(csv_reader)  # Skip header
        row_count = 0
        for row in csv_reader:
            if not all(key in row for key in ['warehouse_id', 'delivery_id', 'item_code', 'material_description', 'received_quantity']):
                logger.warning(f"Missing required fields in CSV row {csv_reader.line_num} for user {current_user.id}")
                return jsonify({'error': f'Missing required fields in CSV row {csv_reader.line_num}'}), 400
            inventory = WarehouseInventory.from_dict(row, current_user.company_name, current_user.id)
            db.session.add(inventory)
            row_count += 1
        db.session.commit()
        logger.info(f"User {current_user.id} imported CSV with {row_count} rows")
        return jsonify({'message': 'CSV imported successfully'}), 200
    except CSRFError:
        logger.error(f"CSRF validation failed for user {current_user.id}")
        return jsonify({'error': 'Invalid CSRF token'}), 403
    except ValidationError as e:
        logger.error(f"Validation error importing CSV for user {current_user.id}: {str(e)}")
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error importing CSV for user {current_user.id}: {str(e)}")
        return jsonify({'error': 'Failed to import CSV'}), 500

@warehouse_bp.route('/api/export_csv', methods=['GET'])
@login_required
def api_export_csv():
    """Export inventory as CSV."""
    try:
        logger.info(f"User {current_user.id} exporting inventory as CSV")
        inventory = WarehouseInventory.query.filter_by(company_name=current_user.company_name).all()
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(WarehouseInventory.csv_headers())
        for item in inventory:
            writer.writerow([
                getattr(item, field) if field != 'workflow_status' else item.workflow_status.value
                for field in WarehouseInventory.csv_fields()
            ])
        output.seek(0)
        logger.info(f"User {current_user.id} exported {len(inventory)} inventory items as CSV")
        return send_file(
            output,
            mimetype='text/csv',
            as_attachment=True,
            download_name=f'warehouse_inventory_{datetime.now().strftime("%Y%m%d")}.csv'
        )
    except Exception as e:
        logger.error(f"Error exporting CSV for user {current_user.id}: {str(e)}")
        return jsonify({'error': 'Failed to export CSV'}), 500

@warehouse_bp.route('/api/check_stock', methods=['POST'])
@login_required
def api_check_stock():
    """Check stock availability for issuing materials."""
    if current_user.access_level != AccessLevel.warehouse:
        logger.warning(f"Unauthorized stock check attempt by user {current_user.id}")
        return jsonify({'error': 'Unauthorized'}), 403
    try:
        validate_csrf(request.json.get('csrf_token'))
        data = request.get_json()
        if not data:
            logger.warning(f"No data provided in stock check request by user {current_user.id}")
            return jsonify({'error': 'No data provided'}), 400
        if not isinstance(data, list):
            data = [data]
        for item in data:
            if 'warehouse_id' not in item or 'issue_quantity' not in item:
                logger.warning(f"Missing required fields in stock check data for user {current_user.id}")
                return jsonify({'error': 'Missing required fields'}), 400
            inventory = WarehouseInventory.query.filter_by(warehouse_id=item['warehouse_id'], company_name=current_user.company_name).first()
            if not inventory:
                logger.warning(f"Inventory {item['warehouse_id']} not found for user {current_user.id}")
                return jsonify({'error': f'Inventory {item["warehouse_id"]} not found'}), 404
            issue_quantity = float(item.get('issue_quantity', 0))
            if issue_quantity <= 0:
                logger.warning(f"Invalid issue quantity for {item['warehouse_id']} by user {current_user.id}")
                return jsonify({'error': 'Issue quantity must be positive'}), 400
            if inventory.received_quantity < issue_quantity:
                logger.warning(f"Insufficient stock for {item['warehouse_id']} by user {current_user.id}")
                return jsonify({'error': f'Insufficient stock for {item["warehouse_id"]}'}), 400
        logger.info(f"User {current_user.id} checked stock for {len(data)} items")
        return jsonify({'message': 'Stock check passed'}), 200
    except CSRFError:
        logger.error(f"CSRF validation failed for user {current_user.id}")
        return jsonify({'error': 'Invalid CSRF token'}), 403
    except ValidationError as e:
        logger.error(f"Validation error checking stock for user {current_user.id}: {str(e)}")
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error checking stock for user {current_user.id}: {str(e)}")
        return jsonify({'error': 'Failed to check stock'}), 500

@warehouse_bp.route('/api/opi', methods=['GET'])
@login_required
def api_get_opi():
    """Fetch Operational Performance Indicators (OPI) data."""
    try:
        logger.info(f"User {current_user.id} fetching OPI data")
        inventory = WarehouseInventory.query.filter_by(company_name=current_user.company_name).all()
        total_items = len(inventory)
        low_stock_threshold = 10.0  # Example threshold
        low_stock_items = sum(1 for item in inventory if item.received_quantity <= low_stock_threshold)
        accurate_items = sum(1 for item in inventory if item.condition == 'Good')  # Example metric
        turnover_data = [4.5, 5.2, 4.8, 5.0]  # Placeholder; replace with real data
        opi_data = {
            'accuracy': {
                'accurate': accurate_items,
                'inaccurate': total_items - accurate_items
            },
            'turnover': {
                'labels': ['Q1', 'Q2', 'Q3', 'Q4'],
                'data': turnover_data
            },
            'low_stock': {
                'normal': total_items - low_stock_items,
                'low': low_stock_items
            }
        }
        logger.info(f"User {current_user.id} fetched OPI data: {opi_data}")
        return jsonify(opi_data), 200
    except Exception as e:
        logger.error(f"Error fetching OPI data for user {current_user.id}: {str(e)}")
        return jsonify({'error': 'Failed to fetch OPI data'}), 500

@warehouse_bp.route('/report/<warehouse_id>', methods=['GET'])
@login_required
def warehouse_report(warehouse_id):
    """Render a detailed report for a specific warehouse entry."""
    try:
        inventory = WarehouseInventory.query.filter_by(warehouse_id=warehouse_id, company_name=current_user.company_name).first()
        if not inventory:
            logger.warning(f"Inventory {warehouse_id} not found for user {current_user.id}")
            return render_template('404.html', error='Inventory not found'), 404
        logger.info(f"User {current_user.id} accessed report for inventory {warehouse_id}")
        return render_template('warehouse_report.html', inventory=inventory)
    except Exception as e:
        logger.error(f"Error generating report for inventory {warehouse_id} for user {current_user.id}: {str(e)}")
        return render_template('500.html', error=str(e)), 500