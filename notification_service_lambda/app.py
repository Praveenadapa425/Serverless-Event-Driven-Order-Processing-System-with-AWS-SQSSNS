"""Notification Service Lambda Function - Consumes messages from SNS."""
import json
import sys
import os
import base64

# Add shared module to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from shared import setup_logger

logger = setup_logger(__name__)


def lambda_handler(event, context):
    """
    Process order status notifications from SNS.
    
    Expected SNS event structure:
    {
        "Records": [
            {
                "Sns": {
                    "Message": "{\"order_id\": \"...\", \"new_status\": \"...\"}"
                }
            }
        ]
    }
    """
    
    logger.info("Notification Service Lambda invoked")
    logger.info(f"Processing {len(event.get('Records', []))} notifications")
    
    results = []
    
    for record in event.get('Records', []):
        try:
            # Extract SNS message
            sns_message = record.get('Sns', {})
            message_text = sns_message.get('Message')
            message_id = sns_message.get('MessageId')
            subject = sns_message.get('Subject', 'No Subject')
            
            logger.info(f"Received SNS notification: {message_id}")
            logger.info(f"Subject: {subject}")
            
            # Parse message body
            message_data = json.loads(message_text)
            
            order_id = message_data.get('order_id')
            new_status = message_data.get('new_status')
            user_id = message_data.get('user_id')
            product_id = message_data.get('product_id')
            timestamp = message_data.get('timestamp')
            
            # Log notification
            logger.info(f"Order Status Update Notification:")
            logger.info(f"  Order ID: {order_id}")
            logger.info(f"  New Status: {new_status}")
            logger.info(f"  User ID: {user_id}")
            logger.info(f"  Product ID: {product_id}")
            logger.info(f"  Timestamp: {timestamp}")
            
            # Simulate sending notification (e.g., email, SMS, push notification)
            notification_result = send_notification(
                user_id=user_id,
                order_id=order_id,
                new_status=new_status,
                product_id=product_id
            )
            
            logger.info(f"Notification sent to {user_id}: {notification_result}")
            
            results.append({
                'messageId': message_id,
                'orderId': order_id,
                'status': 'sent',
                'notification_type': notification_result
            })
            
        except Exception as e:
            logger.error(f"Error processing notification: {str(e)}", exc_info=True)
            results.append({
                'messageId': sns_message.get('MessageId'),
                'status': 'error',
                'error': str(e)
            })
    
    logger.info(f"Notification processing complete: {len(results)} messages")
    
    return {
        'statusCode': 200,
        'body': json.dumps({
            'processed': len(results),
            'results': results
        })
    }


def send_notification(user_id: str, order_id: str, new_status: str, product_id: str) -> str:
    """
    Simulate sending a notification to the user.
    In production, this could send an email, SMS, or push notification.
    """
    
    logger.info(f"Sending {new_status} notification to user {user_id}")
    
    # Determine notification type based on status
    if new_status == 'CONFIRMED':
        notification_type = 'email'
        message = f"""
        Hi {user_id},
        
        Your order {order_id} has been confirmed!
        Product: {product_id}
        Status: {new_status}
        
        Thank you for your purchase!
        """
    elif new_status == 'FAILED':
        notification_type = 'email'
        message = f"""
        Hi {user_id},
        
        We regret to inform you that your order {order_id} could not be processed.
        Product: {product_id}
        Status: {new_status}
        
        Please contact our support team for assistance.
        """
    else:
        notification_type = 'sms'
        message = f"Order {order_id} status: {new_status}"
    
    logger.info(f"Notification message: {message}")
    
    return notification_type
