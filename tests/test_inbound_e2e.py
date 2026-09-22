"""End-to-end inbound material workflow regression.

MR -> PO -> Delivery -> Packing List -> Goods Receipt -> QC -> Warehouse.
This test intentionally uses the public application APIs for PL/GR/QC and
asserts the persisted inventory state and OS&D generation.
"""
from datetime import date

from flask_wtf.csrf import generate_csrf

from extensions import db
from models import (
    AccessLevel, Delivery, DeliveryStatus, InspectionStatus, MaterialMaster,
    MaterialRequisition, Project, PurchaseOrder, PurchaseOrderItem,
    PurchaseOrderStatus, User, ApprovalStatus, WarehouseInventory,
    PackingList, GoodsReceipt, OSDReport,
)
from tests.test_app_integration import _persist_user, _authenticate_session


def _csrf(client):
    with client:
        return generate_csrf()


def test_full_mr_po_delivery_pl_grn_qc_warehouse_flow(client, app):
    company = "Inbound E2E EPC"
    engineer = _persist_user(app, "flow-engineer@example.com", AccessLevel.engineering, company)
    buyer = _persist_user(app, "flow-buyer@example.com", AccessLevel.purchase, company)
    delivery_user = _persist_user(app, "flow-delivery@example.com", AccessLevel.delivery, company)
    warehouse = _persist_user(app, "flow-warehouse@example.com", AccessLevel.warehouse, company)
    quality = _persist_user(app, "flow-quality@example.com", AccessLevel.quality, company)
    supplier = _persist_user(app, "flow-supplier@example.com", AccessLevel.supplier, company)

    with app.app_context():
        project = Project(project_no="FLOW-001", project_name="Inbound E2E Project", company_name=company)
        db.session.add(project)
        db.session.flush()

        material = MaterialMaster(
            material_code="FLOW-PIPE",
            family_code="PIP",
            material_name="Carbon Steel Pipe",
            description="12 inch carbon steel pipe",
            unit="EA",
            discipline="Piping",
            fingerprint=(f"test:{company}:FLOW-PIPE").encode().hex().ljust(64, "0")[:64],
            company_name=company,
            created_by=engineer.id,
            status="active",
            lifecycle_status="active",
            inspection_required=True,
            lot_control=True,
            heat_control=True,
        )
        db.session.add(material)
        db.session.flush()

        mr = MaterialRequisition.from_dict({
            "mr_no": "MR-FLOW-0001",
            "material_id": material.id,
            "item_code": material.material_code,
            "material_description": material.description,
            "quantity": 10,
            "project_no": project.project_no,
            "discipline": "Piping",
            "status": "approved",
        }, company, engineer.id)
        mr.status = ApprovalStatus.approved
        db.session.add(mr)
        db.session.flush()

        po = PurchaseOrder(
            order_no="PO-FLOW-0001",
            project_id=project.id,
            user_id=buyer.id,
            supplier_id=supplier.id,
            total_price=10000,
            status=PurchaseOrderStatus.issued,
            company_name=company,
        )
        db.session.add(po)
        db.session.flush()

        item = PurchaseOrderItem(
            purchase_order_id=po.id,
            material_requisition_id=mr.id,
            material_id=material.id,
            quantity=10,
            unit_price=1000,
        )
        db.session.add(item)

        delivery = Delivery(
            order_id=po.id,
            material_id=material.id,
            user_id=delivery_user.id,
            delivery_id="DLV-0001",
            status=DeliveryStatus.delivered,
            delivered_date=date.today(),
            company_name=company,
        )
        db.session.add(delivery)
        db.session.commit()
        po_id, delivery_id, material_id = po.id, delivery.id, material.id

    _authenticate_session(client, buyer)
    csrf = _csrf(client)
    pl_response = client.post("/warehouse/api/packing-lists", json={
        "csrf_token": csrf,
        "delivery_id": delivery_id,
        "packing_list_no": "PL-FLOW-0001",
        "packing_list_date": date.today().isoformat(),
        "vehicle_no": "TRK-E2E",
        "package_count": 2,
        "lines": [{
            "material_id": material_id,
            "quantity": 10,
            "package_no": "PKG-01",
            "lot_no": "LOT-E2E-01",
            "heat_no": "HEAT-E2E-01",
        }],
    })
    assert pl_response.status_code == 201, pl_response.get_json()
    pl_payload = pl_response.get_json()
    pl_id = pl_payload["id"]
    pl_line_id = pl_payload["lines"][0]["id"]
    assert pl_payload["packing_list_no"] == "PL-FLOW-0001"

    _authenticate_session(client, warehouse)
    csrf = _csrf(client)
    gr_response = client.post("/warehouse/api/goods-receipts", json={
        "csrf_token": csrf,
        "packing_list_id": pl_id,
        "warehouse_id": "WH-FLOW-0001",
        "receipt_date": date.today().isoformat(),
        "final_receipt": True,
        "lines": [{
            "packing_list_line_id": pl_line_id,
            "received_qty": 8,
            "storage_location_id": "RACK-A01",
        }],
    })
    assert gr_response.status_code == 201, gr_response.get_json()
    gr_payload = gr_response.get_json()
    receipt = gr_payload["receipt"]
    assert receipt["packing_list_id"] == pl_id
    assert receipt["lines"][0]["expected_qty"] == 10
    assert receipt["lines"][0]["received_qty"] == 8
    assert receipt["lines"][0]["variance_qty"] == -2
    assert receipt["lines"][0]["inspection_status"] == "pending"
    assert gr_payload["osd"] is not None
    assert gr_payload["osd"]["status"] == "open"

    with app.app_context():
        inventory = WarehouseInventory.query.filter_by(
            company_name=company, warehouse_id="WH-FLOW-0001", material_id=material_id
        ).one()
        assert inventory.received_qty == 8
        assert inventory.available_qty == 0
        assert inventory.quarantine_qty == 8
        assert GoodsReceipt.query.filter_by(id=receipt["id"], company_name=company).one()
        assert OSDReport.query.filter_by(goods_receipt_id=receipt["id"], company_name=company).count() == 1

    _authenticate_session(client, quality)
    csrf = _csrf(client)
    qc_response = client.patch(
        f"/quality_control/api/receipt-inspections/{receipt['lines'][0]['id']}",
        json={"csrf_token": csrf, "status": "passed", "remarks": "E2E accepted"},
    )
    assert qc_response.status_code == 200, qc_response.get_json()
    qc_payload = qc_response.get_json()
    assert qc_payload["quality_control"]["status"] == "passed"
    assert qc_payload["receipt_line"]["inspection_status"] == "passed"
    assert qc_payload["inventory"]["quarantine_qty"] == 0
    assert qc_payload["inventory"]["available_qty"] == 8

    # A second pass must not release the same stock twice.
    csrf = _csrf(client)
    repeat = client.patch(
        f"/quality_control/api/receipt-inspections/{receipt['lines'][0]['id']}",
        json={"csrf_token": csrf, "status": "passed"},
    )
    assert repeat.status_code == 200, repeat.get_json()
    assert repeat.get_json()["inventory"]["available_qty"] == 8
    assert repeat.get_json()["inventory"]["quarantine_qty"] == 0

    _authenticate_session(client, warehouse)
    assert client.get("/warehouse/api/inventory").status_code == 200
    assert client.get("/warehouse/api/transactions").status_code == 200
    assert client.get(f"/warehouse/api/goods-receipts/{receipt['id']}").status_code == 200
    assert client.get(f"/warehouse/api/osd-reports/{gr_payload['osd']['id']}").status_code == 200

    with app.app_context():
        inventory = WarehouseInventory.query.filter_by(
            company_name=company, warehouse_id="WH-FLOW-0001", material_id=material_id
        ).one()
        assert inventory.received_qty == 8
        assert inventory.available_qty == 8
        assert inventory.quarantine_qty == 0

        tx = __import__("models").WarehouseTransaction.query.filter_by(
            company_name=company, receipt_line_id=receipt["lines"][0]["id"]
        ).one()
        assert tx.quantity == 8
        assert tx.packing_list_id == pl_id
        assert tx.goods_receipt_id == receipt["id"]

    # Another tenant cannot read the inbound chain.
    other = _persist_user(app, "flow-other@example.com", AccessLevel.warehouse, "Other Inbound EPC")
    _authenticate_session(client, other)
    assert client.get(f"/warehouse/api/goods-receipts/{receipt['id']}").status_code == 404
    assert client.get(f"/warehouse/api/osd-reports/{gr_payload['osd']['id']}").status_code == 404
