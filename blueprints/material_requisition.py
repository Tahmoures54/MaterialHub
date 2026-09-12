from flask import (
    Blueprint, render_template, request, jsonify, abort, send_file
)
from flask_login import login_required, current_user
from models import db, MaterialRequisition, ApprovalStatus
from utils import generate_next_mr_no, parse_enum
import csv
import io
import datetime
import logging

logger = logging.getLogger(__name__)

material_requisition_bp = Blueprint(
    'material_requisitions', __name__, template_folder='templates'
)

@material_requisition_bp.route('/', methods=['GET'])
@material_requisition_bp.route('/material_requisitions', methods=['GET'])
@login_required
def material_requisitions():
    """Render the material requisitions dashboard for the user."""
    logger.info(f"User {current_user.company_email} accessing material requisitions dashboard")
    return render_template(
        'procurement/material_requisition.html',
        company_name=current_user.company_name,
        current_user=current_user,
        read_only=(current_user.access_level.name != 'engineering')
    )

@material_requisition_bp.route('/api/material_requisitions', methods=['GET'])
@login_required
def api_get_material_requisitions():
    """Get material requisitions for the current user."""
    try:
        discipline = request.args.get('discipline')
        query = MaterialRequisition.query.filter_by(company_name=current_user.company_name)
        if discipline:
            query = query.filter_by(discipline=discipline)
        rows = query.order_by(MaterialRequisition.created_at.desc()).all()
        result = [mr.to_dict() for mr in rows]
        logger.info(f"User {current_user.company_email} fetched {len(result)} material requisitions")
        return jsonify(result), 200
    except Exception as e:
        logger.error(f"Error fetching material requisitions for user {current_user.company_email}: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@material_requisition_bp.route('/api/material_requisitions', methods=['POST'])
@login_required
def api_create_material_requisitions():
    """Create new material requisitions."""
    if current_user.access_level.name != 'engineering':
        logger.warning(f"User {current_user.company_email} attempted to create MR without engineering access")
        return jsonify({'error': 'Only engineering users can create MRs.'}), 403

    try:
        material_requisitions_data = request.get_json(force=True)
        if not material_requisitions_data:
            return jsonify({'error': 'No data provided'}), 400
        if not isinstance(material_requisitions_data, list):
            material_requisitions_data = [material_requisitions_data]
        new_mrs = []
        for row in material_requisitions_data:
            if not row.get('mr_no'):
                row['mr_no'] = generate_next_mr_no(current_user.company_name)
            mr = MaterialRequisition.from_dict(row, current_user.company_name, user_id=current_user.id)
            mr.added_by = current_user.full_name
            mr.edited_by = current_user.full_name
            mr.created_at = datetime.datetime.utcnow()
            db.session.add(mr)
            new_mrs.append(mr)
        db.session.commit()
        logger.info(f"User {current_user.company_email} created {len(new_mrs)} MR(s)")
        return jsonify({'message': f'{len(new_mrs)} MR(s) created.', 'mr_nos': [mr.mr_no for mr in new_mrs]}), 201
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error creating material requisitions for user {current_user.company_email}: {str(e)}")
        return jsonify({'error': str(e)}), 400

@material_requisition_bp.route('/api/material_requisitions/<mr_no>', methods=['PUT'])
@login_required
def api_update_material_requisition(mr_no):
    """Update an existing material requisition."""
    mr = MaterialRequisition.query.filter_by(mr_no=mr_no, company_name=current_user.company_name).first()
    if not mr:
        logger.warning(f"User {current_user.company_email} attempted to update non-existent MR {mr_no}")
        return jsonify({'error': 'MR not found.'}), 404
    if current_user.access_level.name != 'engineering':
        logger.warning(f"User {current_user.company_email} attempted to update MR {mr_no} without engineering access")
        return jsonify({'error': 'Only engineering users can update MRs.'}), 403

    try:
        data = request.get_json(force=True)
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        if isinstance(data, list):
            data = data[0]
        mr.update_from_dict(data)
        mr.edited_by = current_user.full_name
        mr.updated_at = datetime.datetime.utcnow()
        db.session.commit()
        logger.info(f"User {current_user.company_email} updated MR {mr_no}")
        return jsonify({'message': 'MR updated.'}), 200
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error updating MR {mr_no} for user {current_user.company_email}: {str(e)}")
        return jsonify({'error': str(e)}), 400

@material_requisition_bp.route('/api/material_requisitions/<mr_no>', methods=['DELETE'])
@login_required
def api_delete_material_requisition(mr_no):
    """Delete a material requisition."""
    mr = MaterialRequisition.query.filter_by(mr_no=mr_no, company_name=current_user.company_name).first()
    if not mr:
        logger.warning(f"User {current_user.company_email} attempted to delete non-existent MR {mr_no}")
        return jsonify({'error': 'MR not found.'}), 404
    if current_user.access_level.name != 'engineering':
        logger.warning(f"User {current_user.company_email} attempted to delete MR {mr_no} without engineering access")
        return jsonify({'error': 'Only engineering users can delete MRs.'}), 403
    try:
        db.session.delete(mr)
        db.session.commit()
        logger.info(f"User {current_user.company_email} deleted MR {mr_no}")
        return jsonify({'message': f'MR {mr_no} deleted.'}), 200
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error deleting MR {mr_no} for user {current_user.company_email}: {str(e)}")
        return jsonify({'error': str(e)}), 500

@material_requisition_bp.route('/api/generate_mr_no', methods=['GET'])
@login_required
def api_generate_mr_no():
    """Generate a new material requisition number."""
    try:
        mr_no = generate_next_mr_no(current_user.company_name)
        logger.info(f"Generated MR number {mr_no} for user {current_user.company_email}")
        return jsonify({'mr_no': mr_no}), 200
    except Exception as e:
        logger.error(f"Error generating MR number for user {current_user.company_email}: {str(e)}")
        return jsonify({'error': str(e)}), 500

@material_requisition_bp.route('/api/upload_csv', methods=['POST'])
@login_required
def api_upload_csv():
    """Upload a CSV file to create material requisitions."""
    if current_user.access_level.name != 'engineering':
        logger.warning(f"User {current_user.company_email} attempted to upload CSV without engineering access")
        return jsonify({'error': 'Only engineering users can import MRs.'}), 403

    file = request.files.get('file')
    if not file or not file.filename.endswith('.csv'):
        logger.warning(f"User {current_user.company_email} uploaded invalid file for CSV import")
        return jsonify({'error': 'CSV file not provided.'}), 400

    try:
        stream = io.StringIO(file.stream.read().decode('utf-8'))
        reader = csv.DictReader(stream)
        count = 0
        for row in reader:
            if not row.get('mr_no'):
                row['mr_no'] = generate_next_mr_no(current_user.company_name)
            mr = MaterialRequisition.from_dict(row, current_user.company_name, user_id=current_user.id)
            mr.added_by = current_user.full_name
            mr.edited_by = current_user.full_name
            mr.created_at = datetime.datetime.utcnow()
            db.session.add(mr)
            count += 1
        db.session.commit()
        logger.info(f"User {current_user.company_email} imported {count} MRs from CSV")
        return jsonify({'message': f'{count} MRs imported from CSV.'}), 201
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error importing CSV for user {current_user.company_email}: {str(e)}")
        return jsonify({'error': str(e)}), 400

@material_requisition_bp.route('/api/approve', methods=['POST'])
@login_required
def api_approve_mr():
    """Approve a material requisition."""
    if current_user.access_level.name != 'project_manager':
        logger.warning(f"User {current_user.company_email} attempted to approve MR without project_manager access")
        return jsonify({'error': 'Only project managers can approve MRs.'}), 403

    try:
        data = request.get_json(force=True)
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        mr_no = data.get('mr_no')
        status = data.get('approval_status')
        comments = data.get('comments', '')
        mr = MaterialRequisition.query.filter_by(mr_no=mr_no, company_name=current_user.company_name).first()
        if not mr:
            logger.warning(f"User {current_user.company_email} attempted to approve non-existent MR {mr_no}")
            return jsonify({'error': 'MR not found.'}), 404
        parsed_status = parse_enum(ApprovalStatus, status, mr.status)
        if parsed_status:
            mr.status = parsed_status
        if comments:
            mr.remarks = comments
        mr.edited_by = current_user.full_name
        mr.updated_at = datetime.datetime.utcnow()
        db.session.commit()
        logger.info(f"User {current_user.company_email} set MR {mr_no} to status {parsed_status.value}")
        return jsonify({'message': f'MR {mr_no} {parsed_status.value}.'}), 200
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error approving MR for user {current_user.company_email}: {str(e)}")
        return jsonify({'error': str(e)}), 400

@material_requisition_bp.route('/api/export_csv', methods=['GET'])
@login_required
def api_export_csv():
    """Export material requisitions to CSV."""
    try:
        discipline = request.args.get('discipline')
        query = MaterialRequisition.query.filter_by(company_name=current_user.company_name)
        if discipline:
            query = query.filter_by(discipline=discipline)
        rows = query.order_by(MaterialRequisition.created_at.desc()).all()

        output = io.StringIO()
        writer = csv.writer(output)
        headers = MaterialRequisition.csv_headers()
        writer.writerow(headers)
        for mr in rows:
            writer.writerow([getattr(mr, field, '') for field in MaterialRequisition.csv_fields()])
        output.seek(0)
        logger.info(f"User {current_user.company_email} exported {len(rows)} MRs to CSV")
        return send_file(
            io.BytesIO(output.read().encode('utf-8')),
            mimetype='text/csv',
            as_attachment=True,
            download_name='material_requisitions.csv'
        )
    except Exception as e:
        logger.error(f"Error exporting CSV for user {current_user.company_email}: {str(e)}")
        return jsonify({'error': str(e)}), 500

@material_requisition_bp.route('/api/material_requisitions/<mr_no>', methods=['GET'])
@login_required
def api_get_single_mr(mr_no):
    """Get a single material requisition."""
    try:
        mr = MaterialRequisition.query.filter_by(mr_no=mr_no, company_name=current_user.company_name).first()
        if not mr:
            logger.warning(f"User {current_user.company_email} requested non-existent MR {mr_no}")
            return jsonify({'error': 'MR not found.'}), 404
        logger.info(f"User {current_user.company_email} fetched MR {mr_no}")
        return jsonify(mr.to_dict()), 200
    except Exception as e:
        logger.error(f"Error fetching MR {mr_no} for user {current_user.company_email}: {str(e)}")
        return jsonify({'error': str(e)}), 500

@material_requisition_bp.route('/report/<mr_no>', methods=['GET'])
@login_required
def material_requisition_report(mr_no):
    """Render a report for a material requisition."""
    try:
        mr = MaterialRequisition.query.filter_by(mr_no=mr_no, company_name=current_user.company_name).first()
        if not mr:
            logger.warning(f"User {current_user.company_email} requested report for non-existent MR {mr_no}")
            abort(404)
        logger.info(f"User {current_user.company_email} accessed report for MR {mr_no}")
        return render_template(
            'procurement/material_requisition.html',
            mr=mr,
            company_name=current_user.company_name,
            current_user=current_user
        )
    except Exception as e:
        logger.error(f"Error rendering report for MR {mr_no} for user {current_user.company_email}: {str(e)}")
        abort(500)