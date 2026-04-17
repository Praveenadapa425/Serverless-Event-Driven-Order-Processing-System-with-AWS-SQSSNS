"""AWS service utilities for SQS and SNS interactions."""
import json
import os
import logging
from typing import Dict, Any, Optional
import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class SQSClient:
    """Client for SQS operations."""
    
    def __init__(self):
        self.endpoint_url = os.environ.get('AWS_ENDPOINT_URL', None)
        self.region = os.environ.get('AWS_REGION', 'us-east-1')
        self.queue_url = os.environ.get('ORDER_PROCESSING_QUEUE_URL')
        
        self.client = boto3.client(
            'sqs',
            endpoint_url=self.endpoint_url,
            region_name=self.region
        )
    
    def send_message(self, message_body: Dict[str, Any], message_attributes: Optional[Dict] = None) -> str:
        """Send a message to SQS queue."""
        try:
            msg_body = json.dumps(message_body) if isinstance(message_body, dict) else message_body
            
            params = {
                'QueueUrl': self.queue_url,
                'MessageBody': msg_body,
            }
            
            if message_attributes:
                params['MessageAttributes'] = message_attributes
            
            response = self.client.send_message(**params)
            message_id = response['MessageId']
            logger.info(f"Message sent to SQS: {message_id}")
            return message_id
        except ClientError as e:
            logger.error(f"Failed to send message to SQS: {str(e)}")
            raise
    
    def delete_message(self, queue_url: str, receipt_handle: str):
        """Delete a message from SQS queue."""
        try:
            self.client.delete_message(
                QueueUrl=queue_url,
                ReceiptHandle=receipt_handle
            )
            logger.info(f"Message deleted from SQS")
        except ClientError as e:
            logger.error(f"Failed to delete message: {str(e)}")
            raise


class SNSClient:
    """Client for SNS operations."""
    
    def __init__(self):
        self.endpoint_url = os.environ.get('AWS_ENDPOINT_URL', None)
        self.region = os.environ.get('AWS_REGION', 'us-east-1')
        self.topic_arn = os.environ.get('ORDER_STATUS_TOPIC_ARN')
        
        self.client = boto3.client(
            'sns',
            endpoint_url=self.endpoint_url,
            region_name=self.region
        )
    
    def publish_message(self, message_body: Dict[str, Any], subject: str = 'Order Status Update') -> str:
        """Publish a message to SNS topic."""
        try:
            msg_body = json.dumps(message_body) if isinstance(message_body, dict) else message_body
            
            response = self.client.publish(
                TopicArn=self.topic_arn,
                Message=msg_body,
                Subject=subject
            )
            
            message_id = response['MessageId']
            logger.info(f"Message published to SNS: {message_id}")
            return message_id
        except ClientError as e:
            logger.error(f"Failed to publish message to SNS: {str(e)}")
            raise


def get_sqs_client() -> SQSClient:
    """Factory function to get SQS client."""
    return SQSClient()


def get_sns_client() -> SNSClient:
    """Factory function to get SNS client."""
    return SNSClient()
