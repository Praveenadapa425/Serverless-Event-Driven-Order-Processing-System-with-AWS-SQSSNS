"""Unit tests for NotificationService Lambda handler."""
import pytest
import json
import sys
import os
from unittest.mock import patch

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))

from notification_service_lambda.app import lambda_handler, send_notification


class TestNotificationServiceLambda:
    """Test NotificationService Lambda handler."""
    
    def test_successful_notification_processing(self):
        """Test successful notification processing."""
        event = {
            'Records': [
                {
                    'Sns': {
                        'MessageId': 'sns-msg-123',
                        'Message': json.dumps({
                            'order_id': 'ORD-001',
                            'new_status': 'CONFIRMED',
                            'user_id': 'USER-001',
                            'product_id': 'PROD-001',
                            'timestamp': 1234567890
                        }),
                        'Subject': 'Order Status Update'
                    }
                }
            ]
        }
        
        response = lambda_handler(event, None)
        
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['processed'] == 1
        assert body['results'][0]['status'] == 'sent'
    
    def test_notification_for_confirmed_order(self):
        """Test notification for confirmed order."""
        event = {
            'Records': [
                {
                    'Sns': {
                        'MessageId': 'sns-msg-123',
                        'Message': json.dumps({
                            'order_id': 'ORD-001',
                            'new_status': 'CONFIRMED',
                            'user_id': 'USER-001',
                            'product_id': 'PROD-001',
                            'timestamp': 1234567890
                        }),
                        'Subject': 'Order Status Update'
                    }
                }
            ]
        }
        
        response = lambda_handler(event, None)
        
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['results'][0]['notification_type'] == 'email'
    
    def test_notification_for_failed_order(self):
        """Test notification for failed order."""
        event = {
            'Records': [
                {
                    'Sns': {
                        'MessageId': 'sns-msg-123',
                        'Message': json.dumps({
                            'order_id': 'ORD-001',
                            'new_status': 'FAILED',
                            'user_id': 'USER-001',
                            'product_id': 'PROD-001',
                            'timestamp': 1234567890
                        }),
                        'Subject': 'Order Status Update'
                    }
                }
            ]
        }
        
        response = lambda_handler(event, None)
        
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['results'][0]['notification_type'] == 'email'
    
    def test_empty_records(self):
        """Test handling of empty records."""
        event = {'Records': []}
        
        response = lambda_handler(event, None)
        
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['processed'] == 0
    
    def test_multiple_notifications(self):
        """Test handling of multiple notifications."""
        event = {
            'Records': [
                {
                    'Sns': {
                        'MessageId': 'sns-msg-1',
                        'Message': json.dumps({
                            'order_id': 'ORD-001',
                            'new_status': 'CONFIRMED',
                            'user_id': 'USER-001',
                            'product_id': 'PROD-001'
                        }),
                        'Subject': 'Order 1 Status Update'
                    }
                },
                {
                    'Sns': {
                        'MessageId': 'sns-msg-2',
                        'Message': json.dumps({
                            'order_id': 'ORD-002',
                            'new_status': 'FAILED',
                            'user_id': 'USER-002',
                            'product_id': 'PROD-002'
                        }),
                        'Subject': 'Order 2 Status Update'
                    }
                }
            ]
        }
        
        response = lambda_handler(event, None)
        
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['processed'] == 2


class TestSendNotification:
    """Test send_notification function."""
    
    def test_send_confirmed_notification(self):
        """Test sending confirmation notification."""
        result = send_notification('USER-001', 'ORD-001', 'CONFIRMED', 'PROD-001')
        
        assert result == 'email'
    
    def test_send_failed_notification(self):
        """Test sending failure notification."""
        result = send_notification('USER-001', 'ORD-001', 'FAILED', 'PROD-001')
        
        assert result == 'email'
    
    def test_send_other_status_notification(self):
        """Test sending notification for other status."""
        result = send_notification('USER-001', 'ORD-001', 'PROCESSING', 'PROD-001')
        
        assert result == 'sms'
