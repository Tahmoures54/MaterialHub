from flask import Blueprint, render_template, request, jsonify, send_file
from flask_login import login_required, current_user
from flask_wtf.csrf import validate_csrf, CSRFError
from io import StringIO
import csv
import logging
from datetime import datetime
from models import db, WarehouseInventory, WarehouseTransaction, Delivery, MaterialMaster, WorkflowStatus, AccessLevel, ValidationError

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
        return render_template(
            'warehouse/warehouse_operations.html',
            company_name=current_user.company_name,
            read_only=read_only,
            current_user=current_user
        )
    except Exception as e:
        logger.error(f"Error rendering warehouse operations for user {current_user.id}: {str(e)}")
        return render_template('errors/500.html', error=str(e)), 500


def _resolve_material(data):
    """Resolve a required Material Master identity; legacy free-text codes are rejected."""
    material_id = data.get('material_id')
    if not material_id:
        return None
    try:
        return MaterialMaster.query.filter_by(
            id=int(material_id),
            company_name=current_user.company_name,
            status='active'
        ).first()
    except (TypeError, ValueError):
        return None

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
            required = ['warehouse_id', 'delivery_id', 'item_code', 'material_description']
            if not all(key in item for key in required) or not (item.get('received_quantity') or item.get('received_qty')):
                logger.warning(f"Missing required fields in inventory data for user {current_user.id}")
                return jsonify({'error': 'Missing required fields'}), 400
            material = _resolve_material(item)
            if not material:
                return jsonify({'error': 'Select a valid Material Master item.'}), 400
            item = dict(item)
            item['material_id'] = material.id
            item['item_code'] = material.material_code
            item['material_description'] = material.description
            item['unit'] = item.get('unit') or material.unit
            inventory = WarehouseInventory.query.filter_by(
                warehouse_id=item['warehouse_id'],
                material_id=material.id,
                company_name=current_user.company_name
            ).first()
            if inventory:
                inventory.received_qty += float(item.get('received_quantity') or item.get('received_qty') or 0)
                inventory.delivery_id = str(item.get('delivery_id') or inventory.delivery_id)
                inventory.remarks = item.get('remarks') or inventory.remarks
            else:
                inventory = WarehouseInventory.from_dict(item, current_user.company_name, current_user.id)
                db.session.add(inventory)
            db.session.flush()
            from utils import generate_next_warehouse_transaction_no
            tx = WarehouseTransaction(
                transaction_no=generate_next_warehouse_transaction_no(current_user.company_name),
                transaction_type='RECEIPT',
                warehouse_id=inventory.warehouse_id,
                material_id=material.id,
                item_code=inventory.item_code,
                material_description=inventory.material_description,
                quantity=float(inventory.received_qty),
                unit=inventory.unit,
                project_no=inventory.project_no,
                delivery_id=inventory.delivery_id,
                storage_location_id=inventory.storage_location_id,
                reference_no=inventory.delivery_id,
                remarks=inventory.remarks,
                company_name=current_user.company_name,
                user_id=current_user.id,
            )
            db.session.add(tx)
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
        data = request.get_json() or {}
        material_id = data.get('material_id')
        if not material_id:
            return jsonify({'error': 'Material Master item is required'}), 400
        material = _resolve_material(data)
        if not material:
            return jsonify({'error': 'Select a valid Material Master item.'}), 400
        inventory = WarehouseInventory.query.filter_by(warehouse_id=warehouse_id, material_id=material.id, company_name=current_user.company_name).first()
        if not inventory:
            logger.warning(f"Inventory {warehouse_id} not found for user {current_user.id}")
            return jsonify({'error': 'Inventory not found'}), 404
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
            material = _resolve_material(item)
            if not material:
                return jsonify({'error': 'Select a valid Material Master item.'}), 400
            inventory = WarehouseInventory.query.filter_by(warehouse_id=item['warehouse_id'], material_id=material.id, company_name=current_user.company_name).first()
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
            material = _resolve_material(item)
            if material and inventory.item_code != material.material_code:
                return jsonify({'error': 'Selected material does not match the stock record.'}), 409
            inventory.received_quantity -= issue_quantity
            from utils import generate_next_warehouse_transaction_no
            tx = WarehouseTransaction(
                transaction_no=generate_next_warehouse_transaction_no(current_user.company_name),
                transaction_type='ISSUE',
                warehouse_id=inventory.warehouse_id,
                material_id=inventory.material_id,
                item_code=inventory.item_code,
                material_description=inventory.material_description,
                quantity=issue_quantity,
                unit=inventory.unit,
                project_no=item.get('project_no') or inventory.project_no,
                contractor=item.get('contractor'),
                storage_location_id=inventory.storage_location_id,
                reference_no=item.get('reference_no'),
                remarks=item.get('remarks'),
                company_name=current_user.company_name,
                user_id=current_user.id,
            )
            db.session.add(tx)
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

@warehouse_bp.route('/api/transactions', methods=['GET'])
@login_required
def api_get_transactions():
    """Return the tenant-scoped warehouse movement ledger."""
    try:
        query = WarehouseTransaction.query.filter_by(company_name=current_user.company_name)
        transaction_type = request.args.get('type')
        item_code = request.args.get('item_code')
        warehouse_id = request.args.get('warehouse_id')
        limit = min(max(int(request.args.get('limit', 100)), 1), 500)
        if transaction_type:
            query = query.filter_by(transaction_type=transaction_type.upper())
        if item_code:
            query = query.filter(WarehouseTransaction.item_code.ilike(f'%{item_code.strip()}%'))
        if warehouse_id:
            query = query.filter_by(warehouse_id=warehouse_id.strip())
        rows = query.order_by(WarehouseTransaction.created_at.desc()).limit(limit).all()
        return jsonify([row.to_dict() for row in rows]), 200
    except (TypeError, ValueError):
        return jsonify({'error': 'Invalid transaction query'}), 400
    except Exception as e:
        logger.error(f"Error fetching warehouse transactions: {e}")
        return jsonify({'error': 'Failed to fetch transactions'}), 500


@warehouse_bp.route('/api/transactions', methods=['POST'])
@login_required
def api_create_transaction():
    """Record a controlled warehouse movement against a Material Master identity."""
    if current_user.access_level != AccessLevel.warehouse:
        return jsonify({'error': 'Unauthorized'}), 403
    try:
        data = request.get_json() or {}
        validate_csrf(data.get('csrf_token'))
        tx_type = str(data.get('transaction_type') or '').upper()
        allowed = {'RECEIPT', 'RETURN', 'ADJUSTMENT_IN', 'ADJUSTMENT_OUT', 'TRANSFER'}
        if tx_type not in allowed:
            return jsonify({'error': 'Unsupported transaction type'}), 400
        warehouse_id = str(data.get('warehouse_id') or '').strip()
        quantity = float(data.get('quantity') or 0)
        if not warehouse_id or quantity <= 0:
            return jsonify({'error': 'Stock ID and positive quantity are required'}), 400
        material = _resolve_material(data)
        if not material:
            return jsonify({'error': 'Select a valid Material Master item.'}), 400
        inventory = WarehouseInventory.query.filter_by(
            warehouse_id=warehouse_id, company_name=current_user.company_name
        ).first()
        if tx_type == 'RECEIPT':
            packing_list_no = str(data.get('packing_list_no') or '').strip()
            if not packing_list_no:
                return jsonify({'error': 'Packing List No. is required for a receipt.'}), 400
            if inventory and inventory.material_id and inventory.material_id != material.id:
                return jsonify({'error': 'Selected material does not match the stock record.'}), 409
            before = float(inventory.received_qty or 0) if inventory else 0.0
            if not inventory:
                inventory = WarehouseInventory.from_dict({
                    'warehouse_id': warehouse_id,
                    'delivery_id': data.get('delivery_id') or data.get('reference_no') or packing_list_no,
                    'item_code': material.material_code,
                    'material_id': material.id,
                    'material_description': material.description,
                    'material_category': material.material_group,
                    'received_quantity': 0,
                    'unit': material.unit,
                    'project_no': data.get('project_no'),
                    'remarks': data.get('remarks'),
                }, current_user.company_name, current_user.id)
                db.session.add(inventory)
                db.session.flush()
            destination = None
        else:
            if not inventory:
                return jsonify({'error': 'Inventory stock not found'}), 404
            if inventory.material_id and inventory.material_id != material.id:
                return jsonify({'error': 'Selected material does not match the stock record.'}), 409
            before = float(inventory.received_qty or 0)
            destination = None
        if tx_type == 'TRANSFER':
            destination_id = str(data.get('destination_warehouse_id') or '').strip()
            if not destination_id or destination_id == warehouse_id:
                return jsonify({'error': 'Select a different destination stock ID for a transfer.'}), 400
            destination = WarehouseInventory.query.filter_by(warehouse_id=destination_id, company_name=current_user.company_name).first()
            if not destination:
                return jsonify({'error': 'Destination stock must already exist for this material.'}), 404
            if destination.material_id and destination.material_id != material.id:
                return jsonify({'error': 'Destination stock belongs to a different material.'}), 409
            if before < quantity:
                return jsonify({'error': 'Insufficient stock'}), 400
            destination_before = float(destination.received_qty or 0)
            inventory.received_qty = before - quantity
            destination.received_qty = destination_before + quantity
            destination.material_id = material.id
            destination.item_code = material.material_code
            destination.material_description = material.description
            destination.unit = material.unit
        elif tx_type != 'RECEIPT':
            signed = quantity if tx_type in {'RETURN', 'ADJUSTMENT_IN'} else -quantity
            if signed < 0 and before < quantity:
                return jsonify({'error': 'Insufficient stock'}), 400
            inventory.received_qty = before + signed
            inventory.material_id = material.id
            inventory.item_code = material.material_code
            inventory.material_description = material.description
            inventory.unit = inventory.unit or material.unit
        from utils import generate_next_warehouse_transaction_no
        tx = WarehouseTransaction(
            transaction_no=generate_next_warehouse_transaction_no(current_user.company_name),
            transaction_type=tx_type, warehouse_id=inventory.warehouse_id, material_id=material.id,
            item_code=material.material_code, material_description=material.description,
            quantity=quantity, unit=material.unit, project_no=data.get('project_no') or inventory.project_no,
            contractor=data.get('contractor'), storage_location_id=inventory.storage_location_id,
            reference_no=data.get('reference_no'), remarks=data.get('remarks'),
            packing_list_no=str(data.get('packing_list_no') or '').strip() or None,
            packing_list_date=(
                datetime.strptime(str(data.get('packing_list_date')), '%Y-%m-%d').date()
                if data.get('packing_list_date') else None
            ),
            packing_list_document=str(data.get('packing_list_document') or '').strip() or None,
            supplier_name=str(data.get('supplier_name') or '').strip() or None,
            discrepancy_type=str(data.get('discrepancy_type') or '').strip() or None,
            discrepancy_details=str(data.get('discrepancy_details') or '').strip() or None,
            company_name=current_user.company_name, user_id=current_user.id,
            balance_before=before, balance_after=float(inventory.received_qty or 0),
            destination_warehouse_id=destination.warehouse_id if destination else None,
        )
        db.session.add(tx)
        db.session.commit()
        return jsonify({'message': 'Transaction recorded', 'transaction': tx.to_dict(),
                        'destination_balance': float(destination.received_qty) if destination else None}), 201
    except CSRFError:
        db.session.rollback()
        return jsonify({'error': 'Invalid CSRF token'}), 403
    except (TypeError, ValueError) as exc:
        db.session.rollback()
        return jsonify({'error': str(exc) or 'Invalid quantity'}), 400
    except Exception as e:
        db.session.rollback()
        logger.error(f'Error recording warehouse transaction: {e}')
        return jsonify({'error': 'Failed to record transaction'}), 500


@warehouse_bp.route('/reports', methods=['GET'])
@login_required
def warehouse_reports():
    """Warehouse print/report center for receiving and discrepancy documents."""
    if current_user.access_level not in {AccessLevel.warehouse, AccessLevel.project_manager, AccessLevel.quality}:
        return jsonify({'error': 'Unauthorized'}), 403
    transactions = WarehouseTransaction.query.filter_by(
        company_name=current_user.company_name
    ).order_by(WarehouseTransaction.created_at.desc()).limit(200).all()
    return render_template('warehouse/warehouse_reports.html', transactions=transactions)


def _tenant_transaction(transaction_id):
    return WarehouseTransaction.query.filter_by(
        id=transaction_id, company_name=current_user.company_name
    ).first()


@warehouse_bp.route('/reports/receipt/<int:transaction_id>', methods=['GET'])
@login_required
def warehouse_receipt_report(transaction_id):
    transaction = _tenant_transaction(transaction_id)
    if not transaction:
        return render_template('errors/404.html', error='Warehouse transaction not found'), 404
    return render_template('warehouse/warehouse_receipt_report.html', transaction=transaction)


@warehouse_bp.route('/reports/osid/<int:transaction_id>', methods=['GET'])
@login_required
def warehouse_osid_report(transaction_id):
    transaction = _tenant_transaction(transaction_id)
    if not transaction:
        return render_template('errors/404.html', error='Warehouse transaction not found'), 404
    return render_template('warehouse/warehouse_osid_report.html', transaction=transaction)


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
        from utils import generate_next_warehouse_id
        warehouse_id = generate_next_warehouse_id(current_user.company_name)
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
        low_stock_items = sum(1 for item in inventory if (item.received_qty or 0) <= low_stock_threshold)
        accurate_items = sum(1 for item in inventory if item.workflow_status == WorkflowStatus.approved)
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
            return render_template('errors/404.html', error='Inventory not found'), 404
        logger.info(f"User {current_user.id} accessed report for inventory {warehouse_id}")
        return render_template('warehouse/warehouse_report.html', inventory=inventory)
    except Exception as e:
        logger.error(f"Error generating report for inventory {warehouse_id} for user {current_user.id}: {str(e)}")
        return render_template('errors/500.html', error=str(e)), 500