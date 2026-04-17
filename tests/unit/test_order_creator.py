"""Unit tests for OrderCreator Lambda handler."""
import pytest
import json
import sys
import os
from unittest.mock import Mock, patch, MagicMock

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))

from order_creator_lambda.app import lambda_handler, create_response, create_error_response


class TestOrderCreatorLambda:
    """Test OrderCreator Lambda handler."""
    
    def test_successful_order_creation(self):
        """Test successful order creation."""
        event = {
            'body': json.dumps({
                'product_id': 'PROD-001',
                'quantity': 5,
                'user_id': 'USER-001'
            })
        }
        
        with patch('order_creator_lambda.app.get_db_connection') as mock_db, \
             patch('order_creator_lambda.app.get_sqs_client') as mock_sqs:
            
            # Mock database
            db_mock = MagicMock()
            db_mock.insert_order.return_value = True
            mock_db.return_value = db_mock
            
            # Mock SQS
            sqs_mock = MagicMock()
            sqs_mock.send_message.return_value = 'msg-123'
            mock_sqs.return_value = sqs_mock
            
            response = lambda_handler(event, None)
            
            assert response['statusCode'] == 202
            body = json.loads(response['body'])
            assert 'order_id' in body
            assert body['status'] == 'PENDING'
    
    def test_invalid_payload(self):
        """Test with invalid payload."""
        event = {
            'body': json.dumps({
                'product_id': 'PROD-001',
                # Missing quantity and user_id
            })
        }
        
        response = lambda_handler(event, None)
        
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert 'error' in body
    
    def test_database_insert_failure(self):
        """Test handling of database insert failure."""
        event = {
            'body': json.dumps({
                'product_id': 'PROD-001',
                'quantity': 5,
                'user_id': 'USER-001'
            })
        }
        
        with patch('order_creator_lambda.app.get_db_connection') as mock_db:
            db_mock = MagicMock()
            db_mock.insert_order.return_value = False
            mock_db.return_value = db_mock
            
            response = lambda_handler(event, None)
            
            assert response['statusCode'] == 500
    
    def test_missing_body(self):
        """Test with missing body."""
        event = {}
        
        response = lambda_handler(event, None)
        
        assert response['statusCode'] == 400


class TestCreateResponse:
    """Test response creation functions."""
    
    def test_create_response_success(self):
        """Test successful response creation."""
        response = create_response(200, {'message': 'success'})
        
        assert response['statusCode'] == 200
        assert response['headers']['Content-Type'] == 'application/json'
        assert response['body'] == json.dumps({'message': 'success'})
    
    def test_create_error_response(self):
        """Test error response creation."""
        response = create_error_response(400, 'Bad request')
        
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert body['error'] == 'Bad request'
