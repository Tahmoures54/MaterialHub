from datetime import date, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from extensions import db
from models import (
    PurchaseOrder, PurchaseOrderStatus, AccessLevel, WarehouseInventory,
    MaterialRequisition, ApprovalStatus, QualityControl, InspectionStatus
)
from models_intelligence import (
    RFQ, RFQSupplier, RFQStatus, Receipt, SupplierInvoice,
    ThreeWayMatch, MatchStatus, MaterialPriceHistory, SupplierScore
)

operations_copilot_bp = Blueprint("operations_copilot", __name__)


def _tenant(query, model):
    return query if current_user.is_admin else query.filter(model.company_name == current_user.company_name)


def _allowed():
    return current_user.is_admin or current_user.access_level in {
        AccessLevel.project_manager, AccessLevel.purchase,
        AccessLevel.delivery, AccessLevel.warehouse, AccessLevel.quality
    }


@operations_copilot_bp.get("/operations-copilot")
@login_required
def dashboard():
    if not _allowed():
        flash("You do not have permission to access Operations Copilot.", "danger")
        return redirect(url_for("role_workspace.my_workspace"))

    pos = _tenant(PurchaseOrder.query, PurchaseOrder).order_by(PurchaseOrder.created_at.desc()).limit(50).all()
    open_pos = [p for p in pos if p.status in (PurchaseOrderStatus.pending, PurchaseOrderStatus.issued)]
    exceptions = _tenant(ThreeWayMatch.query, ThreeWayMatch).filter(
        ThreeWayMatch.status == MatchStatus.exception
    ).order_by(ThreeWayMatch.created_at.desc()).limit(10).all()

    risks = []
    for mr in _tenant(MaterialRequisition.query, MaterialRequisition).filter(
        MaterialRequisition.status != ApprovalStatus.rejected
    ).order_by(MaterialRequisition.required_date.asc()).limit(50).all():
        stock = sum((x.received_qty or 0) for x in _tenant(WarehouseInventory.query, WarehouseInventory)
                    .filter_by(item_code=mr.item_code).all())
        open_qty = sum(
            (item.quantity or 0)
            for po in open_pos
            for item in po.items
            if item.material_requisition and item.material_requisition.item_code == mr.item_code
        )
        coverage = stock + open_qty
        if coverage < (mr.quantity or 0) or (
            mr.required_date and (mr.required_date - date.today()).days <= 14 and open_qty == 0
        ):
            risks.append({
                "item_code": mr.item_code,
                "description": mr.material_description,
                "required_date": mr.required_date,
                "required_qty": mr.quantity,
                "stock": stock,
                "open_po": open_qty,
                "coverage": coverage,
                "days": (mr.required_date - date.today()).days if mr.required_date else None,
            })

    rfqs = _tenant(RFQ.query, RFQ).filter(
        RFQ.status.in_([RFQStatus.sent, RFQStatus.quoted])
    ).order_by(RFQ.due_date.asc()).limit(10).all()

    price_rows = _tenant(MaterialPriceHistory.query, MaterialPriceHistory).order_by(
        MaterialPriceHistory.recorded_at.desc()
    ).limit(12).all()

    suppliers = _tenant(SupplierScore.query, SupplierScore).order_by(
        SupplierScore.overall_score.desc()
    ).limit(8).all()

    return render_template(
        "intelligence/operations_copilot.html",
        pos=pos, open_pos=open_pos, exceptions=exceptions, risks=risks[:12],
        rfqs=rfqs, price_rows=price_rows, suppliers=suppliers,
        today=date.today(),
    )


@operations_copilot_bp.route("/operations-copilot/receive/<int:po_id>", methods=["GET", "POST"])
@login_required
def receive(po_id):
    if not _allowed():
        flash("You do not have permission to receive materials.", "danger")
        return redirect(url_for("operations_copilot.dashboard"))

    po = _tenant(PurchaseOrder.query, PurchaseOrder).filter_by(id=po_id).first_or_404()
    if request.method == "POST":
        try:
            received_qty = float(request.form.get("received_qty") or 0)
            accepted_qty = float(request.form.get("accepted_qty") or 0)
            invoice_amount = float(request.form.get("invoice_amount") or 0)
            if received_qty <= 0 or accepted_qty < 0 or accepted_qty > received_qty:
                raise ValueError("Received/accepted quantities are invalid.")

            receipt = Receipt(
                receipt_no=(request.form.get("receipt_no") or "").strip(),
                po_id=po.id, received_qty=received_qty, accepted_qty=accepted_qty,
                rejected_qty=max(received_qty - accepted_qty, 0),
                receipt_date=date.today(), company_name=current_user.company_name,
            )
            invoice = SupplierInvoice(
                invoice_no=(request.form.get("invoice_no") or "").strip(),
                po_id=po.id, invoice_amount=invoice_amount,
                invoice_date=date.today(), company_name=current_user.company_name,
            )
            if not receipt.receipt_no or not invoice.invoice_no:
                raise ValueError("Receipt number and invoice number are required.")

            db.session.add_all([receipt, invoice])
            db.session.flush()

            variance = abs((po.total_price or 0) - invoice_amount)
            tolerance = max(1.0, abs(po.total_price or 0) * 0.02)
            status = MatchStatus.matched if variance <= tolerance and accepted_qty > 0 else MatchStatus.exception
            match = ThreeWayMatch(
                po_id=po.id, receipt_id=receipt.id, invoice_id=invoice.id,
                po_amount=po.total_price or 0, receipt_amount=accepted_qty,
                invoice_amount=invoice_amount, variance_amount=variance,
                status=status,
                notes="Operations Copilot receiving check",
            )
            invoice.status = status
            invoice.variance_amount = variance
            db.session.add(match)
            db.session.commit()

            if status == MatchStatus.exception:
                flash(
                    f"Receiving recorded, but a matching exception was detected. "
                    f"Invoice variance: {variance:g}. Review before approval.",
                    "warning",
                )
            else:
                flash("Receiving recorded and the PO/receipt/invoice check passed.", "success")
            return redirect(url_for("operations_copilot.dashboard"))
        except Exception as exc:
            db.session.rollback()
            flash(str(exc), "danger")

    expected_qty = sum((item.quantity or 0) for item in po.items)
    return render_template("intelligence/operations_receive.html", po=po, expected_qty=expected_qty)


@operations_copilot_bp.get("/operations-copilot/rfq/<int:rfq_id>")
@login_required
def rfq_detail(rfq_id):
    rfq = _tenant(RFQ.query, RFQ).filter_by(id=rfq_id).first_or_404()
    quotes = RFQSupplier.query.filter_by(rfq_id=rfq.id).order_by(
        RFQSupplier.quoted_price.asc().nullslast()
    ).all()
    return render_template("intelligence/rfq_compare.html", rfq=rfq, quotes=quotes)
