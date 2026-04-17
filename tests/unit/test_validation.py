"""Unit tests for validation module."""
import pytest
import sys
import os

# Add shared module to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../src'))

from shared.validation import validate_order_payload, generate_order_id


class TestValidateOrderPayload:
    """Test order payload validation."""
    
    def test_valid_payload(self):
        """Test validation of a valid order payload."""
        payload = {
            'product_id': 'PROD-001',
            'quantity': 5,
            'user_id': 'USER-001'
        }
        
        is_valid, error_msg, validated_data = validate_order_payload(payload)
        
        assert is_valid is True
        assert error_msg == ""
        assert validated_data['product_id'] == 'PROD-001'
        assert validated_data['quantity'] == 5
        assert validated_data['user_id'] == 'USER-001'
    
    def test_missing_product_id(self):
        """Test validation with missing product_id."""
        payload = {
            'quantity': 5,
            'user_id': 'USER-001'
        }
        
        is_valid, error_msg, _ = validate_order_payload(payload)
        
        assert is_valid is False
        assert 'product_id' in error_msg.lower()
    
    def test_missing_quantity(self):
        """Test validation with missing quantity."""
        payload = {
            'product_id': 'PROD-001',
            'user_id': 'USER-001'
        }
        
        is_valid, error_msg, _ = validate_order_payload(payload)
        
        assert is_valid is False
        assert 'quantity' in error_msg.lower()
    
    def test_missing_user_id(self):
        """Test validation with missing user_id."""
        payload = {
            'product_id': 'PROD-001',
            'quantity': 5
        }
        
        is_valid, error_msg, _ = validate_order_payload(payload)
        
        assert is_valid is False
        assert 'user_id' in error_msg.lower()
    
    def test_empty_product_id(self):
        """Test validation with empty product_id."""
        payload = {
            'product_id': '',
            'quantity': 5,
            'user_id': 'USER-001'
        }
        
        is_valid, error_msg, _ = validate_order_payload(payload)
        
        assert is_valid is False
    
    def test_invalid_quantity_non_integer(self):
        """Test validation with non-integer quantity."""
        payload = {
            'product_id': 'PROD-001',
            'quantity': '5',
            'user_id': 'USER-001'
        }
        
        is_valid, error_msg, _ = validate_order_payload(payload)
        
        assert is_valid is False
        assert 'integer' in error_msg.lower()
    
    def test_invalid_quantity_zero(self):
        """Test validation with zero quantity."""
        payload = {
            'product_id': 'PROD-001',
            'quantity': 0,
            'user_id': 'USER-001'
        }
        
        is_valid, error_msg, _ = validate_order_payload(payload)
        
        assert is_valid is False
        assert 'greater than 0' in error_msg.lower()
    
    def test_invalid_quantity_negative(self):
        """Test validation with negative quantity."""
        payload = {
            'product_id': 'PROD-001',
            'quantity': -5,
            'user_id': 'USER-001'
        }
        
        is_valid, error_msg, _ = validate_order_payload(payload)
        
        assert is_valid is False
    
    def test_product_id_too_long(self):
        """Test validation with product_id exceeding max length."""
        payload = {
            'product_id': 'A' * 300,
            'quantity': 5,
            'user_id': 'USER-001'
        }
        
        is_valid, error_msg, _ = validate_order_payload(payload)
        
        assert is_valid is False
        assert 'too long' in error_msg.lower()
    
    def test_quantity_too_large(self):
        """Test validation with quantity exceeding max value."""
        payload = {
            'product_id': 'PROD-001',
            'quantity': 50000,
            'user_id': 'USER-001'
        }
        
        is_valid, error_msg, _ = validate_order_payload(payload)
        
        assert is_valid is False
        assert 'too large' in error_msg.lower()
    
    def test_whitespace_stripping(self):
        """Test that whitespace is stripped from product_id and user_id."""
        payload = {
            'product_id': '  PROD-001  ',
            'quantity': 5,
            'user_id': '  USER-001  '
        }
        
        is_valid, error_msg, validated_data = validate_order_payload(payload)
        
        assert is_valid is True
        assert validated_data['product_id'] == 'PROD-001'
        assert validated_data['user_id'] == 'USER-001'


class TestGenerateOrderId:
    """Test order ID generation."""
    
    def test_generate_order_id(self):
        """Test that order ID is generated."""
        order_id = generate_order_id()
        
        assert order_id is not None
        assert order_id.startswith('ORD-')
        assert len(order_id) > 10
    
    def test_generate_unique_order_ids(self):
        """Test that generated order IDs are unique."""
        order_ids = [generate_order_id() for _ in range(100)]
        
        # All IDs should be unique
        assert len(set(order_ids)) == 100
