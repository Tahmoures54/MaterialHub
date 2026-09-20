"""
Simple rule-based analysis helpers for MaterialHub.
These are not machine-learning models; they provide basic inventory and delivery risk insights.
"""

import logging
from datetime import datetime, date
from models import WarehouseInventory, Delivery, DeliveryStatus, AccessLevel

logger = logging.getLogger(__name__)


def predict_stock_needs(inventory_items, low_threshold=20, target_stock=50):
    """
    Predict stock needs based on current inventory levels.

    Args:
        inventory_items: List of WarehouseInventory objects.
        low_threshold: Stock level below which we suggest reordering.
        target_stock: Desired stock level after reorder.

    Returns:
        List of dicts with material info and suggested order quantity.
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

            current_stock = item.received_qty
            if current_stock is None:
                logger.warning(f"No received_qty for WarehouseInventory {item.warehouse_id}. Skipping.")
                continue

            if current_stock < low_threshold:
                suggested_order = max(target_stock - current_stock, 0)
                predictions.append({
                    "warehouse_id": item.warehouse_id,
                    "item_code": item.item_code,
                    "material_description": item.material_description,
                    "current_stock": current_stock,
                    "unit": item.unit,
                    "suggested_order": round(suggested_order, 2),
                    "project_no": item.project_no,
                })
                logger.info(
                    f"Predicted stock need for {item.item_code}: {suggested_order} {item.unit}"
                )
        except Exception as e:
            logger.error(
                f"Error predicting stock need for item {getattr(item, 'warehouse_id', 'unknown')}: {e}"
            )
            continue

    return predictions


def predict_delivery_risk(delivery_item):
    """
    Predict the risk of delay for a delivery.

    Args:
        delivery_item: A Delivery object.

    Returns:
        float: Risk score between 0.0 and 1.0 (higher = higher risk).
    """
    risk_factors = {
        DeliveryStatus.in_transit: 0.30,
        DeliveryStatus.delayed: 0.75,
        DeliveryStatus.delivered: 0.05,
        DeliveryStatus.pending: 0.40,
    }

    try:
        if not isinstance(delivery_item, Delivery):
            logger.error(f"Supply item {delivery_item} is not a Delivery object.")
            return 0.5

        status = delivery_item.status
        base_risk = risk_factors.get(status, 0.5)

        risk_adjustment = 0.0
        if delivery_item.delivered_date and status != DeliveryStatus.delivered:
            # If expected delivery date has passed
            days_overdue = (date.today() - delivery_item.delivered_date).days
            if days_overdue > 0:
                risk_adjustment = min(days_overdue * 0.05, 0.35)

        final_risk = min(base_risk + risk_adjustment, 1.0)
        final_risk = max(final_risk, 0.0)

        logger.info(
            f"Predicted delivery risk for {delivery_item.delivery_id}: {final_risk:.2f}"
        )
        return round(final_risk, 2)

    except Exception as e:
        logger.error(
            f"Error predicting delivery risk for item "
            f"{getattr(delivery_item, 'delivery_id', 'unknown')}: {e}"
        )
        return 0.5
