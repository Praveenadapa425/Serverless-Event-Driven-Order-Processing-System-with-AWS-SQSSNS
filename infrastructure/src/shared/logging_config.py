"""Logging configuration for Lambda functions."""
import json
import logging
import sys
from typing import Any, Dict


class JsonFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging."""
    
    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            'timestamp': self.formatTime(record),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'function': record.funcName,
            'line': record.lineno
        }
        
        # Add exception info if present
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)
        
        # Add custom fields if available
        if hasattr(record, 'order_id'):
            log_data['order_id'] = record.order_id
        
        return json.dumps(log_data)


def setup_logger(name: str) -> logging.Logger:
    """Setup structured logger for Lambda functions."""
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    
    # Remove existing handlers
    logger.handlers = []
    
    # Create console handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.INFO)
    
    # Set JSON formatter
    formatter = JsonFormatter()
    handler.setFormatter(formatter)
    
    # Add handler to logger
    logger.addHandler(handler)
    
    return logger


def log_with_context(logger: logging.Logger, level: str, message: str, **context):
    """Log message with additional context."""
    record = logger.makeRecord(
        logger.name,
        getattr(logging, level.upper()),
        "()",  # filename
        0,     # lineno
        message,
        (),    # args
        None   # exc_info
    )
    
    # Add context to record
    for key, value in context.items():
        setattr(record, key, value)
    
    logger.handle(record)
