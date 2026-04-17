"""Validation utilities for order data."""
import logging
from typing import Tuple, Dict, Any
import uuid

logger = logging.getLogger(__name__)


def validate_order_payload(payload: Dict[str, Any]) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Validate incoming order payload.
    Returns (is_valid, error_message, validated_data)
    """
    
    # Check required fields
    required_fields = ['product_id', 'quantity', 'user_id']
    for field in required_fields:
        if field not in payload:
            return False, f"Missing required field: {field}", {}
    
    product_id = payload.get('product_id', '').strip()
    user_id = payload.get('user_id', '').strip()
    quantity = payload.get('quantity')
    
    # Validate product_id
    if not product_id:
        return False, "product_id cannot be empty", {}
    
    if len(product_id) > 255:
        return False, "product_id is too long (max 255 characters)", {}
    
    # Validate user_id
    if not user_id:
        return False, "user_id cannot be empty", {}
    
    if len(user_id) > 255:
        return False, "user_id is too long (max 255 characters)", {}
    
    # Validate quantity
    if not isinstance(quantity, int):
        return False, "quantity must be an integer", {}
    
    if quantity <= 0:
        return False, "quantity must be greater than 0", {}
    
    if quantity > 10000:
        return False, "quantity is too large (max 10000)", {}
    
    validated_data = {
        'product_id': product_id,
        'user_id': user_id,
        'quantity': quantity
    }
    
    logger.info(f"Order payload validated successfully")
    return True, "", validated_data


def generate_order_id() -> str:
    """Generate a unique order ID."""
    return f"ORD-{uuid.uuid4().hex[:12].upper()}"


class ValidationError(Exception):
    """Custom exception for validation errors."""
    pass
