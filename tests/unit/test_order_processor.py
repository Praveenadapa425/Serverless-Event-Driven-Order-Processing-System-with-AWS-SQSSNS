"""Unit tests for OrderProcessor Lambda handler."""
import pytest
import json
import sys
import os
from unittest.mock import Mock, patch, MagicMock

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))

from order_processor_lambda.app import (
    lambda_handler,
    simulate_order_processing,
    is_message_processed,
    mark_message_processed
)


class TestOrderProcessorLambda:
    """Test OrderProcessor Lambda handler."""
    
    def test_successful_order_processing(self):
        """Test successful order processing."""
        event = {
            'Records': [
                {
                    'messageId': 'msg-123',
                    'receiptHandle': 'handle-123',
                    'body': json.dumps({
                        'order_id': 'ORD-001',
                        'user_id': 'USER-001',
                        'product_id': 'PROD-001',
                        'quantity': 5
                    })
                }
            ]
        }
        
        with patch('order_processor_lambda.app.get_db_connection') as mock_db, \
             patch('order_processor_lambda.app.get_sns_client') as mock_sns, \
             patch('order_processor_lambda.app.simulate_order_processing') as mock_sim:
            
            # Mock database
            db_mock = MagicMock()
            order_data = {
                'id': 'ORD-001',
                'user_id': 'USER-001',
                'product_id': 'PROD-001',
                'quantity': 5,
                'status': 'PENDING'
            }
            db_mock.get_order.return_value = order_data
            db_mock.update_order_status.return_value = True
            mock_db.return_value = db_mock
            
            # Mock SNS
            sns_mock = MagicMock()
            sns_mock.publish_message.return_value = 'sns-msg-123'
            mock_sns.return_value = sns_mock
            
            # Mock processing
            mock_sim.return_value = (True, 'CONFIRMED')
            
            response = lambda_handler(event, None)
            
            assert response['statusCode'] == 200
            body = json.loads(response['body'])
            assert body['processed'] == 1
            assert body['results'][0]['status'] == 'success'
    
    def test_order_not_found(self):
        """Test handling when order is not found."""
        event = {
            'Records': [
                {
                    'messageId': 'msg-123',
                    'receiptHandle': 'handle-123',
                    'body': json.dumps({
                        'order_id': 'ORD-NONEXISTENT',
                        'user_id': 'USER-001'
                    })
                }
            ]
        }
        
        with patch('order_processor_lambda.app.get_db_connection') as mock_db:
            db_mock = MagicMock()
            db_mock.get_order.return_value = None
            mock_db.return_value = db_mock
            
            response = lambda_handler(event, None)
            
            assert response['statusCode'] == 200
            body = json.loads(response['body'])
            assert body['results'][0]['status'] == 'failed'
            assert 'order_not_found' in body['results'][0]['reason']
    
    def test_idempotent_processing(self):
        """Test idempotent message processing."""
        message_id = 'msg-123'
        
        # Mark message as processed
        mark_message_processed(message_id)
        
        # Check if marked as processed
        assert is_message_processed(message_id) is True
    
    def test_empty_records(self):
        """Test handling of empty records."""
        event = {'Records': []}
        
        response = lambda_handler(event, None)
        
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['processed'] == 0


class TestSimulateOrderProcessing:
    """Test order processing simulation."""
    
    def test_order_processing_returns_status(self):
        """Test that order processing returns a status."""
        success, status = simulate_order_processing('ORD-001')
        
        assert status in ['CONFIRMED', 'FAILED']
    
    def test_order_processing_success_rate(self):
        """Test that success rate is approximately 90%."""
        successes = 0
        total = 1000
        
        for _ in range(total):
            success, status = simulate_order_processing(f'ORD-{_}')
            if status == 'CONFIRMED':
                successes += 1
        
        success_rate = successes / total
        # Allow 5% deviation from 90%
        assert 0.85 < success_rate < 0.95
