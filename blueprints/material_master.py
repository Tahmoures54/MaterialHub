import hashlib
import json
import logging
import re

from flask import Blueprint, jsonify, render_template, request
from flask_login import current_user, login_required
from flask_wtf.csrf import CSRFError, validate_csrf
from sqlalchemy import or_

from models import AccessLevel, MaterialMaster, db
from utils import generate_next_material_code

logger = logging.getLogger(__name__)

material_master_bp = Blueprint("material_master", __name__, template_folder="templates")

WRITE_ROLES = {
    AccessLevel.project_manager,
    AccessLevel.engineering,
    AccessLevel.purchase,
    AccessLevel.warehouse,
}

FAMILY_PREFIXES = {
    "Pipe": "PIP", "Valve": "VAL", "Fitting": "FIT", "Flange": "FLG",
    "Bolt": "BLT", "Gasket": "GSK", "Cable": "CAB", "Instrument": "INS",
    "Electrical": "ELE", "Equipment": "EQP", "Steel": "STL", "Consumable": "CON",
    "Safety": "SAF", "Other": "OTH",
}


def _can_write():
    return current_user.is_admin or current_user.access_level in WRITE_ROLES


def _clean(value):
    return str(value or "").strip()


def _fingerprint(data):
    """Stable identity key for duplicate detection; descriptions are deliberately excluded."""
    fields = (
        "family_code", "material_group", "discipline", "unit", "standard", "grade",
        "size", "schedule", "manufacturer", "manufacturer_part_no",
    )
    values = [_clean(data.get(k)).casefold() for k in fields]
    return hashlib.sha256("|".join(values).encode("utf-8")).hexdigest()


def _payload(data):
    family = _clean(data.get("family") or data.get("family_code") or "Other")
    family_code = FAMILY_PREFIXES.get(family, re.sub(r"[^A-Za-z0-9]", "", family).upper()[:6] or "OTH")
    description = _clean(data.get("description") or data.get("material_name"))
    name = _clean(data.get("material_name") or description)
    if not name or not description:
        raise ValueError("Material name and description are required.")
    unit = _clean(data.get("unit")) or "EA"
    return {
        "family_code": family_code,
        "material_name": name[:200],
        "description": description,
        "unit": unit[:20],
        "material_group": _clean(data.get("material_group"))[:100] or None,
        "discipline": _clean(data.get("discipline"))[:50] or None,
        "unspsc_code": _clean(data.get("unspsc_code"))[:20] or None,
        "eclass_code": _clean(data.get("eclass_code"))[:50] or None,
        "etim_class": _clean(data.get("etim_class"))[:50] or None,
        "standard": _clean(data.get("standard"))[:100] or None,
        "grade": _clean(data.get("grade"))[:100] or None,
        "size": _clean(data.get("size"))[:50] or None,
        "schedule": _clean(data.get("schedule"))[:50] or None,
        "manufacturer": _clean(data.get("manufacturer"))[:150] or None,
        "manufacturer_part_no": _clean(data.get("manufacturer_part_no"))[:100] or None,
        "supplier_material_no": _clean(data.get("supplier_material_no"))[:100] or None,
        "revision": _clean(data.get("revision"))[:30] or None,
        "certificate_required": bool(data.get("certificate_required", False)),
        "inspection_required": bool(data.get("inspection_required", False)),
        "lot_control": bool(data.get("lot_control", False)),
        "heat_control": bool(data.get("heat_control", False)),
        "serial_control": bool(data.get("serial_control", False)),
        "quarantine_allowed": bool(data.get("quarantine_allowed", True)),
        "project_peg_required": bool(data.get("project_peg_required", False)),
        "lifecycle_status": _clean(data.get("lifecycle_status")) or "active",
        "attributes": json.dumps(data.get("attributes") or {}, ensure_ascii=False, sort_keys=True),
        "status": _clean(data.get("status")) or "active",
    }


def _serialize_query(query):
    return [row.to_dict() for row in query.limit(50).all()]


@material_master_bp.route("/materials/catalog", methods=["GET"])
@login_required
def catalog():
    return render_template(
        "procurement/material_master.html",
        company_name=current_user.company_name,
        can_write=_can_write(),
        family_options=sorted(FAMILY_PREFIXES),
    )


@material_master_bp.route("/api/material-master", methods=["GET"])
@login_required
def api_list():
    query = MaterialMaster.query.filter_by(company_name=current_user.company_name)
    q = _clean(request.args.get("q"))
    family = _clean(request.args.get("family"))
    status = _clean(request.args.get("status"))
    if q:
        pattern = f"%{q}%"
        query = query.filter(
            or_(
                MaterialMaster.material_code.ilike(pattern),
                MaterialMaster.material_name.ilike(pattern),
                MaterialMaster.description.ilike(pattern),
                MaterialMaster.manufacturer_part_no.ilike(pattern),
            )
        )
    if family:
        query = query.filter_by(family_code=family.upper())
    if status:
        query = query.filter_by(status=status)
    rows = query.order_by(MaterialMaster.updated_at.desc()).limit(500).all()
    return jsonify([row.to_dict() for row in rows])


@material_master_bp.route("/api/material-master/<int:material_id>", methods=["GET"])
@login_required
def api_get(material_id):
    row = MaterialMaster.query.filter_by(id=material_id, company_name=current_user.company_name).first()
    if not row:
        return jsonify({"error": "Material not found."}), 404
    return jsonify(row.to_dict())


@material_master_bp.route("/api/material-master/check-duplicate", methods=["POST"])
@login_required
def api_check_duplicate():
    data = request.get_json(silent=True) or {}
    try:
        payload = _payload(data)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    fp = _fingerprint(payload)
    query = MaterialMaster.query.filter_by(company_name=current_user.company_name, fingerprint=fp)
    exclude_id = data.get("exclude_id")
    if exclude_id:
        query = query.filter(MaterialMaster.id != int(exclude_id))
    matches = query.order_by(MaterialMaster.updated_at.desc()).limit(10).all()
    return jsonify({"duplicate": bool(matches), "matches": [m.to_dict() for m in matches]})


@material_master_bp.route("/api/material-master", methods=["POST"])
@login_required
def api_create():
    if not _can_write():
        return jsonify({"error": "You do not have permission to create materials."}), 403
    try:
        data = request.get_json(silent=True) or {}
        validate_csrf(data.get("csrf_token"))
        payload = _payload(data)
        fp = _fingerprint(payload)
        existing = MaterialMaster.query.filter_by(
            company_name=current_user.company_name, fingerprint=fp
        ).first()
        if existing:
            return jsonify({
                "error": "A material with the same identity already exists.",
                "duplicate": existing.to_dict(),
            }), 409
        code = generate_next_material_code(current_user.company_name)
        row = MaterialMaster(
            material_code=code,
            fingerprint=fp,
            company_name=current_user.company_name,
            created_by=current_user.id,
            **payload,
        )
        db.session.add(row)
        db.session.commit()
        return jsonify({"message": "Material created.", "material": row.to_dict()}), 201
    except CSRFError:
        db.session.rollback()
        return jsonify({"error": "Invalid CSRF token."}), 403
    except (TypeError, ValueError) as exc:
        db.session.rollback()
        return jsonify({"error": str(exc)}), 400
    except Exception:
        db.session.rollback()
        logger.exception("Material Master creation failed")
        return jsonify({"error": "Failed to create material."}), 500


@material_master_bp.route("/api/material-master/<int:material_id>", methods=["PUT"])
@login_required
def api_update(material_id):
    if not _can_write():
        return jsonify({"error": "You do not have permission to update materials."}), 403
    try:
        data = request.get_json(silent=True) or {}
        validate_csrf(data.get("csrf_token"))
        row = MaterialMaster.query.filter_by(id=material_id, company_name=current_user.company_name).first()
        if not row:
            return jsonify({"error": "Material not found."}), 404
        payload = _payload(data)
        fp = _fingerprint(payload)
        duplicate = MaterialMaster.query.filter(
            MaterialMaster.company_name == current_user.company_name,
            MaterialMaster.fingerprint == fp,
            MaterialMaster.id != row.id,
        ).first()
        if duplicate:
            return jsonify({"error": "Another material already has the same identity.", "duplicate": duplicate.to_dict()}), 409
        for key, value in payload.items():
            setattr(row, key, value)
        row.fingerprint = fp
        db.session.commit()
        return jsonify({"message": "Material updated.", "material": row.to_dict()})
    except CSRFError:
        db.session.rollback()
        return jsonify({"error": "Invalid CSRF token."}), 403
    except (TypeError, ValueError) as exc:
        db.session.rollback()
        return jsonify({"error": str(exc)}), 400
    except Exception:
        db.session.rollback()
        logger.exception("Material Master update failed")
        return jsonify({"error": "Failed to update material."}), 500


@material_master_bp.route("/api/material-master/<int:material_id>", methods=["DELETE"])
@login_required
def api_delete(material_id):
    if not _can_write():
        return jsonify({"error": "You do not have permission to archive materials."}), 403
    try:
        data = request.get_json(silent=True) or {}
        validate_csrf(data.get("csrf_token"))
        row = MaterialMaster.query.filter_by(id=material_id, company_name=current_user.company_name).first()
        if not row:
            return jsonify({"error": "Material not found."}), 404
        row.status = "archived"
        db.session.commit()
        return jsonify({"message": "Material archived."})
    except CSRFError:
        db.session.rollback()
        return jsonify({"error": "Invalid CSRF token."}), 403
    except Exception:
        db.session.rollback()
        logger.exception("Material Master archive failed")
        return jsonify({"error": "Failed to archive material."}), 500


@material_master_bp.route("/api/material-master/export", methods=["GET"])
@login_required
def api_export():
    import csv
    import io
    rows = MaterialMaster.query.filter_by(company_name=current_user.company_name).order_by(MaterialMaster.material_code).all()
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow([
        "Material Code", "Family", "Material Name", "Description", "Unit", "Material Group",
        "Discipline", "UNSPSC", "eCl@ss", "ETIM Class", "Standard", "Grade", "Size",
        "Schedule", "Manufacturer", "Manufacturer Part No.", "Supplier Material No.", "Revision",
        "Certificate Required", "Inspection Required", "Lot Control", "Heat Control", "Serial Control",
        "Quarantine Allowed", "Project Peg Required", "Lifecycle Status", "Status",
    ])
    for row in rows:
        writer.writerow([
            row.material_code, row.family_code, row.material_name, row.description, row.unit,
            row.material_group or "", row.discipline or "", row.unspsc_code or "",
            row.eclass_code or "", row.etim_class or "", row.standard or "", row.grade or "",
            row.size or "", row.schedule or "", row.manufacturer or "",
            row.manufacturer_part_no or "", row.supplier_material_no or "", row.revision or "",
            "Yes" if row.certificate_required else "No", "Yes" if row.inspection_required else "No",
            "Yes" if row.lot_control else "No", "Yes" if row.heat_control else "No",
            "Yes" if row.serial_control else "No", "Yes" if row.quarantine_allowed else "No",
            "Yes" if row.project_peg_required else "No", row.lifecycle_status or "active", row.status,
        ])
    return (
        out.getvalue(),
        200,
        {
            "Content-Type": "text/csv; charset=utf-8",
            "Content-Disposition": "attachment; filename=material_master.csv",
        },
    )
