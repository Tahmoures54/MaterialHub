"""
Rule-based analysis helpers for MaterialHub.
These provide practical inventory and delivery risk insights.
They are intentionally simple and transparent (not black-box ML).
"""

import logging
from datetime import date
from models import WarehouseInventory, Delivery, DeliveryStatus

logger = logging.getLogger(__name__)


def predict_stock_needs(inventory_items, low_threshold=20, target_stock=50):
    """
    Suggest reorder quantities when stock falls below a threshold.

    Args:
        inventory_items: Iterable of WarehouseInventory objects.
        low_threshold: Stock level that triggers a reorder suggestion.
        target_stock: Desired stock level after reorder.

    Returns:
        List of dicts containing material info and suggested order quantity.
    """
    predictions = []

    if not inventory_items:
        logger.warning("No inventory items provided for stock prediction.")
        return predictions

    for item in inventory_items:
        try:
            if not isinstance(item, WarehouseInventory):
                logger.warning(f"Item {item} is not a WarehouseInventory object. Skipping.")
                continue

            current_stock = getattr(item, 'received_qty', None)
            if current_stock is None:
                logger.warning(
                    f"No received_qty for WarehouseInventory "
                    f"{getattr(item, 'warehouse_id', 'unknown')}. Skipping."
                )
                continue

            if current_stock < low_threshold:
                suggested_order = max(target_stock - current_stock, 0)
                predictions.append({
                    "warehouse_id": getattr(item, 'warehouse_id', None),
                    "item_code": getattr(item, 'item_code', None),
                    "material_description": getattr(item, 'material_description', None),
                    "current_stock": current_stock,
                    "unit": getattr(item, 'unit', None),
                    "suggested_order": round(suggested_order, 2),
                    "project_no": getattr(item, 'project_no', None),
                    "priority": "high" if current_stock < low_threshold / 2 else "medium",
                })
                logger.info(
                    f"Predicted stock need for {getattr(item, 'item_code', '?')}: "
                    f"{suggested_order} {getattr(item, 'unit', '')}"
                )
        except Exception as e:
            logger.error(
                f"Error predicting stock need for item "
                f"{getattr(item, 'warehouse_id', 'unknown')}: {e}"
            )
            continue

    return predictions


def predict_delivery_risk(delivery_item):
    """
    Calculate a simple risk score (0.0 – 1.0) for a delivery.

    Higher score = higher chance of delay or problem.
    Factors: current status + how many days overdue (if any).
    """
    risk_factors = {
        DeliveryStatus.in_transit: 0.30,
        DeliveryStatus.delayed: 0.80,
        DeliveryStatus.delivered: 0.05,
        DeliveryStatus.pending: 0.40,
    }

    try:
        if not isinstance(delivery_item, Delivery):
            logger.error(f"Item {delivery_item} is not a Delivery object.")
            return 0.5

        status = delivery_item.status
        base_risk = risk_factors.get(status, 0.50)

        risk_adjustment = 0.0
        expected_date = getattr(delivery_item, 'delivered_date', None) or getattr(
            delivery_item, 'expected_delivery_date', None
        )

        if expected_date and status != DeliveryStatus.delivered:
            if isinstance(expected_date, date):
                days_overdue = (date.today() - expected_date).days
                if days_overdue > 0:
                    # +0.05 per day overdue, capped at +0.40
                    risk_adjustment = min(days_overdue * 0.05, 0.40)

        final_risk = min(base_risk + risk_adjustment, 1.0)
        final_risk = max(final_risk, 0.0)

        logger.info(
            f"Predicted delivery risk for "
            f"{getattr(delivery_item, 'delivery_id', 'unknown')}: {final_risk:.2f}"
        )
        return round(final_risk, 2)

    except Exception as e:
        logger.error(
            f"Error predicting delivery risk for item "
            f"{getattr(delivery_item, 'delivery_id', 'unknown')}: {e}"
        )
        return 0.5


def summarize_risks(deliveries):
    """
    Return a short summary of high-risk deliveries.
    Useful for dashboards.
    """
    high_risk = []
    for d in deliveries or []:
        score = predict_delivery_risk(d)
        if score >= 0.6:
            high_risk.append({
                "delivery_id": getattr(d, 'delivery_id', None),
                "risk_score": score,
                "status": str(getattr(d, 'status', None)),
            })
    return sorted(high_risk, key=lambda x: x["risk_score"], reverse=True)
