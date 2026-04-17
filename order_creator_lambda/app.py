"""Order Creator Lambda Function - Handles POST /orders endpoint."""
import json
import sys
import os

# Add shared module to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from shared import (
    setup_logger,
    validate_order_payload,
    generate_order_id,
    get_db_connection,
    get_sqs_client
)

logger = setup_logger(__name__)


def lambda_handler(event, context):
    """
    Handle incoming POST /orders requests.
    
    Expected input:
    {
        "product_id": "prod-123",
        "quantity": 5,
        "user_id": "user-456"
    }
    
    Returns:
    {
        "statusCode": 202,
        "body": {
            "order_id": "ORD-...",
            "message": "Order created successfully"
        }
    }
    """
    
    logger.info("Order Creator Lambda invoked")
    
    try:
        # Parse request body
        if isinstance(event.get('body'), str):
            body = json.loads(event.get('body', '{}'))
        else:
            body = event.get('body', {})
        
        logger.info(f"Received order request: {body}")
        
        # Validate payload
        is_valid, error_msg, validated_data = validate_order_payload(body)
        
        if not is_valid:
            logger.warning(f"Validation failed: {error_msg}")
            return create_error_response(400, error_msg)
        
        # Extract validated data
        product_id = validated_data['product_id']
        user_id = validated_data['user_id']
        quantity = validated_data['quantity']
        
        # Generate unique order ID
        order_id = generate_order_id()
        logger.info(f"Generated order ID: {order_id}")
        
        # Store order in database
        db = None
        try:
            db = get_db_connection()
            success = db.insert_order(order_id, user_id, product_id, quantity)
            
            if not success:
                logger.error(f"Failed to insert order {order_id}")
                return create_error_response(
                    500,
                    f"Order {order_id} already exists or database error occurred"
                )
            
            logger.info(f"Order {order_id} persisted to database")
        finally:
            if db:
                db.close()
        
        # Publish message to SQS queue
        try:
            sqs = get_sqs_client()
            message_body = {
                'order_id': order_id,
                'user_id': user_id,
                'product_id': product_id,
                'quantity': quantity
            }
            
            message_id = sqs.send_message(message_body)
            logger.info(f"SQS message published: {message_id}")
        except Exception as e:
            logger.error(f"Failed to publish SQS message: {str(e)}")
            # Don't fail the request if SQS fails - the order is persisted
            # In production, you might want to use a DLQ or retry mechanism
        
        # Return 202 Accepted response
        response_body = {
            'order_id': order_id,
            'message': 'Order created successfully',
            'status': 'PENDING'
        }
        
        logger.info(f"Returning 202 response for order {order_id}")
        return create_response(202, response_body)
    
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        return create_error_response(500, "Internal server error")


def create_response(status_code, body):
    """Create Lambda proxy response."""
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
        },
        'body': json.dumps(body)
    }


def create_error_response(status_code, message):
    """Create error response."""
    return create_response(status_code, {
        'error': message,
        'status_code': status_code
    })
