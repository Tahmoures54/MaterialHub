# ai_analysis.py
import random
from datetime import datetime, timedelta
import logging
from models import Warehouse, SupplierMaterial, Delivery, User

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def predict_stock_needs(inventory_items):
    """
    Predict stock needs based on current inventory levels.

    Args:
        inventory_items (list): List of Warehouse objects representing inventory items.

    Returns:
        list: A list of predictions with material details, current stock, and suggested order quantity.
    """
    predictions = []
    
    # Check if inventory_items is empty
    if not inventory_items:
        logger.warning("No inventory items provided for stock prediction.")
        return predictions

    for item in inventory_items:
        try:
            # Ensure item is a Warehouse object
            if not isinstance(item, Warehouse):
                logger.warning(f"Item {item} is not a Warehouse object. Skipping.")
                continue

            # Use received_quantity instead of stock_level
            current_stock = item.received_quantity
            if current_stock is None:
                logger.warning(f"No received_quantity found for Warehouse item {item.warehouse_id}. Skipping.")
                continue

            # Suggest an order if stock is below threshold (20 units)
            if current_stock < 20:
                suggested_order = 50 - current_stock  # Suggest enough to reach 50 units
                # Get material details via the user relationship
                user = item.user
                if not user:
                    logger.warning(f"No user associated with Warehouse item {item.warehouse_id}. Skipping.")
                    continue

                # Check if user has materials (only suppliers have materials)
                if user.access_level != "supplier" or not user.materials:
                    logger.warning(f"User {user.company_email} is not a supplier or has no materials. Skipping.")
                    continue

                material = user.materials[0]  # Assume the first material for simplicity
                predictions.append({
                    "material": material.material_name,
                    "current_stock": current_stock,
                    "suggested_order": suggested_order
                })
                logger.info(f"Predicted stock need for material {material.material_name}: {suggested_order} units.")
        except Exception as e:
            logger.error(f"Error predicting stock need for item {getattr(item, 'warehouse_id', 'unknown')}: {str(e)}")
            continue

    return predictions

def predict_delivery_risk(supply_item):
    """
    Predict the risk of delay for a delivery item.

    Args:
        supply_item (Delivery): A Delivery object representing a supply item.

    Returns:
        float: A risk score between 0 and 1 (higher means higher risk).
    """
    # Define risk factors based on delivery_status
    risk_factors = {
        "in_transit": 0.3,  # Moderate risk for items in transit
        "delayed": 0.7,     # High risk for already delayed items
        "delivered": 0.1,   # Low risk for delivered items
        "pending": 0.4      # Slightly higher risk for pending deliveries
    }

    try:
        # Ensure supply_item is a Delivery object
        if not isinstance(supply_item, Delivery):
            logger.error(f"Supply item {supply_item} is not a Delivery object.")
            return 0.5  # Default risk score

        # Use delivery_status instead of status
        status = supply_item.delivery_status.lower() if supply_item.delivery_status else None
        if not status:
            logger.warning(f"No delivery_status found for Delivery item {supply_item.delivery_id}.")
            return 0.5

        # Get base risk based on delivery_status
        base_risk = risk_factors.get(status, 0.5)
        if status not in risk_factors:
            logger.warning(f"Unknown delivery_status '{status}' for Delivery item {supply_item.delivery_id}. Using default risk of 0.5.")

        # Adjust risk based on delivery date (if overdue, increase risk)
        risk_adjustment = 0.0
        if supply_item.delivery_date:
            days_overdue = (datetime.now().date() - supply_item.delivery_date).days
            if days_overdue > 0:
                risk_adjustment = min(days_overdue * 0.05, 0.3)  # Increase risk by 0.05 per day, up to 0.3

        final_risk = min(base_risk + risk_adjustment, 1.0)  # Cap risk at 1.0
        final_risk = max(final_risk + random.uniform(-0.1, 0.1), 0.0)  # Add small random variation, cap at 0.0
        logger.info(f"Predicted delivery risk for item {supply_item.delivery_id}: {final_risk:.2f}")
        return final_risk

    except Exception as e:
        logger.error(f"Error predicting delivery risk for item {getattr(supply_item, 'delivery_id', 'unknown')}: {str(e)}")
        return 0.5  # Default risk score in case of error