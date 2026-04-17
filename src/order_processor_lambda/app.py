"""Order Processor Lambda Function - Consumes messages from SQS and updates order status."""
import json
import sys
import os
import random
import time

# Add shared module to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from shared import (
    setup_logger,
    get_db_connection,
    get_sns_client
)

logger = setup_logger(__name__)


def lambda_handler(event, context):
    """
    Process order from SQS queue.
    
    Expected SQS event structure:
    {
        "Records": [
            {
                "messageId": "...",
                "body": "{\"order_id\": \"...\", ...}"
            }
        ]
    }
    """
    
    logger.info("Order Processor Lambda invoked")
    logger.info(f"Processing {len(event.get('Records', []))} messages")
    
    results = []
    
    for record in event.get('Records', []):
        try:
            # Extract message details
            message_id = record.get('messageId')
            receipt_handle = record.get('receiptHandle')
            
            # Parse message body
            body = json.loads(record.get('body', '{}'))
            order_id = body.get('order_id')
            
            logger.info(f"Processing message: {message_id}, Order: {order_id}")
            
            # Retrieve order from database
            db = None
            try:
                db = get_db_connection()

                # Ensure durable idempotency table exists and acquire first-process token.
                db.ensure_processed_messages_table()
                first_processing_attempt = db.mark_message_processed_once(message_id, order_id)

                if not first_processing_attempt:
                    logger.info(f"Message {message_id} already processed (idempotent)")
                    results.append({
                        'messageId': message_id,
                        'status': 'skipped',
                        'reason': 'already_processed'
                    })
                    continue

                order = db.get_order(order_id)
                
                if not order:
                    logger.warning(f"Order {order_id} not found in database")
                    results.append({
                        'messageId': message_id,
                        'status': 'failed',
                        'reason': 'order_not_found'
                    })
                    continue
                
                logger.info(f"Retrieved order {order_id}: {order}")
                
                # Simulate processing logic (random success/failure)
                processing_status, new_status = simulate_order_processing(order_id)
                
                logger.info(f"Processing result for {order_id}: {new_status}")
                
                # Update order status in database
                success = db.update_order_status(order_id, new_status)
                
                if not success:
                    logger.error(f"Failed to update order {order_id} status")
                    results.append({
                        'messageId': message_id,
                        'status': 'failed',
                        'reason': 'database_update_failed'
                    })
                    continue
                
                logger.info(f"Order {order_id} status updated to {new_status}")
                
            finally:
                if db:
                    db.close()
            
            # Publish notification to SNS
            try:
                sns = get_sns_client()
                notification_message = {
                    'order_id': order_id,
                    'new_status': new_status,
                    'user_id': body.get('user_id'),
                    'product_id': body.get('product_id'),
                    'timestamp': int(time.time())
                }
                
                message_id_sns = sns.publish_message(
                    notification_message,
                    subject=f'Order {order_id} Status: {new_status}'
                )
                
                logger.info(f"SNS notification published: {message_id_sns}")
            except Exception as e:
                logger.error(f"Failed to publish SNS notification: {str(e)}")
                # Don't fail the processing if SNS fails
            
            results.append({
                'messageId': message_id,
                'orderId': order_id,
                'status': 'success',
                'newStatus': new_status
            })
            
            logger.info(f"Message {message_id} processed successfully")
        
        except Exception as e:
            logger.error(f"Error processing message: {str(e)}", exc_info=True)
            results.append({
                'messageId': message_id,
                'status': 'error',
                'error': str(e)
            })
    
    logger.info(f"Batch processing complete: {len(results)} messages")
    
    return {
        'statusCode': 200,
        'body': json.dumps({
            'processed': len(results),
            'results': results
        })
    }


def simulate_order_processing(order_id: str) -> tuple:
    """
    Simulate order processing logic.
    Returns (success: bool, new_status: str)
    """
    
    logger.info(f"Starting order processing simulation for {order_id}")
    
    # Simulate processing time
    time.sleep(random.uniform(0.5, 2.0))
    
    # Simulate 90% success rate
    success_chance = random.random()
    
    if success_chance < 0.90:
        logger.info(f"Order {order_id} processing succeeded")
        return True, 'CONFIRMED'
    else:
        logger.warning(f"Order {order_id} processing failed")
        return False, 'FAILED'
