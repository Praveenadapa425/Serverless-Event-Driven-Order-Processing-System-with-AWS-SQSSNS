# API Documentation - Order Processing System

Complete API reference for the Serverless Event-Driven Order Processing System.

## Base URL

**Local Development:**
```
http://localhost:4566/restapis/{API_ID}/orders
```

**Production (AWS):**
```
https://{API_ID}.execute-api.{region}.amazonaws.com/{stage}
```

## API Endpoints

### 1. Create Order

Create a new order for processing.

**Endpoint:**
```
POST /orders
```

**Request Headers:**
```
Content-Type: application/json
```

**Request Body:**
```json
{
  "product_id": "PROD-001",
  "quantity": 5,
  "user_id": "USER-001"
}
```

**Request Body Parameters:**

| Parameter | Type | Required | Max Length | Constraints |
|-----------|------|----------|------------|-------------|
| `product_id` | string | Yes | 255 | Non-empty |
| `quantity` | integer | Yes | - | > 0, ≤ 10000 |
| `user_id` | string | Yes | 255 | Non-empty |

**Response (202 Accepted):**
```
HTTP/1.1 202 Accepted
Content-Type: application/json
```

```json
{
  "statusCode": 202,
  "body": {
    "order_id": "ORD-ABC123DEF456",
    "message": "Order created successfully",
    "status": "PENDING"
  }
}
```

**Response Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `statusCode` | integer | HTTP status (always 202 for success) |
| `order_id` | string | Unique order identifier |
| `message` | string | Success message |
| `status` | string | Initial order status (always "PENDING") |

**Error Response (400 Bad Request):**
```
HTTP/1.1 400 Bad Request
Content-Type: application/json
```

```json
{
  "statusCode": 400,
  "body": {
    "error": "Missing required field: product_id",
    "status_code": 400
  }
}
```

**Error Response (500 Internal Server Error):**
```
HTTP/1.1 500 Internal Server Error
Content-Type: application/json
```

```json
{
  "statusCode": 500,
  "body": {
    "error": "Internal server error",
    "status_code": 500
  }
}
```

### Examples

#### cURL Example

```bash
# Create a new order
curl -X POST http://localhost:4566/restapis/api-id/orders \
  -H "Content-Type: application/json" \
  -d '{
    "product_id": "LAPTOP-001",
    "quantity": 2,
    "user_id": "customer-789"
  }'
```

**Response:**
```json
{
  "statusCode": 202,
  "body": {
    "order_id": "ORD-ABC123DEF456",
    "message": "Order created successfully",
    "status": "PENDING"
  }
}
```

#### Python/Requests Example

```python
import requests
import json

url = "http://localhost:4566/restapis/api-id/orders"
headers = {"Content-Type": "application/json"}
payload = {
    "product_id": "PHONE-001",
    "quantity": 1,
    "user_id": "user-123"
}

response = requests.post(url, headers=headers, json=payload)
print(response.status_code)
print(json.dumps(response.json(), indent=2))
```

#### JavaScript/Fetch Example

```javascript
const url = 'http://localhost:4566/restapis/api-id/orders';
const payload = {
  product_id: 'TABLET-001',
  quantity: 3,
  user_id: 'user-456'
};

fetch(url, {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json'
  },
  body: JSON.stringify(payload)
})
.then(response => response.json())
.then(data => console.log(data))
.catch(error => console.error('Error:', error));
```

## Status Codes

### Success Codes

| Code | Status | Description |
|------|--------|-------------|
| 202 | Accepted | Order created and queued for processing |

### Error Codes

| Code | Status | Description |
|------|--------|-------------|
| 400 | Bad Request | Invalid input (missing/malformed fields) |
| 500 | Internal Server Error | System error (database, queue, etc.) |

## Validation Rules

### Product ID (`product_id`)
- **Type**: String
- **Required**: Yes
- **Max Length**: 255 characters
- **Constraints**: Cannot be empty or whitespace-only
- **Example**: `"PROD-001"`, `"LAPTOP-2024"`, `"SKU123"`

**Validation Examples:**

❌ **Invalid:**
```json
// Empty
{"product_id": ""}

// Whitespace only
{"product_id": "   "}

// Too long (>255 chars)
{"product_id": "A very long product ID that exceeds the maximum..."}
```

✅ **Valid:**
```json
{"product_id": "PROD-001"}
{"product_id": "LAPTOP-GAMING-RTX"}
{"product_id": "SKU-2024-Q1"}
```

### Quantity (`quantity`)
- **Type**: Integer
- **Required**: Yes
- **Min Value**: 1
- **Max Value**: 10,000
- **Constraints**: Must be a whole number greater than 0
- **Example**: `1`, `5`, `100`

**Validation Examples:**

❌ **Invalid:**
```json
// Zero
{"quantity": 0}

// Negative
{"quantity": -5}

// String instead of integer
{"quantity": "5"}

// Float
{"quantity": 5.5}

// Too large
{"quantity": 50000}
```

✅ **Valid:**
```json
{"quantity": 1}
{"quantity": 100}
{"quantity": 10000}
```

### User ID (`user_id`)
- **Type**: String
- **Required**: Yes
- **Max Length**: 255 characters
- **Constraints**: Cannot be empty or whitespace-only
- **Example**: `"USER-001"`, `"customer@example.com"`, `"user-789"`

**Validation Examples:**

❌ **Invalid:**
```json
// Empty
{"user_id": ""}

// Only whitespace
{"user_id": "   "}

// Too long
{"user_id": "A very long user identifier that exceeds..."}
```

✅ **Valid:**
```json
{"user_id": "USER-001"}
{"user_id": "customer@example.com"}
{"user_id": "user-789"}
```

## Event Flow

### Complete Order Lifecycle

```
1. Client submits POST /orders
   ├─ OrderCreator Lambda receives request
   ├─ Validates input
   ├─ Generates order ID (e.g., ORD-ABC123)
   ├─ Inserts into database with PENDING status
   ├─ Publishes to SQS OrderProcessingQueue
   └─ Returns 202 Accepted to client

2. SQS triggers OrderProcessor Lambda
   ├─ Retrieves message from queue
   ├─ Checks idempotency (has this message been processed?)
   ├─ Fetches order from database
   ├─ Simulates processing (90% success rate)
   ├─ Updates order status to CONFIRMED or FAILED
   ├─ Publishes to SNS OrderStatusNotifications
   └─ Deletes message from queue

3. SNS triggers NotificationService Lambda
   ├─ Receives status update
   ├─ Determines notification type
   ├─ Logs notification (email/SMS simulation)
   └─ Completes
```

## Database Schema

### Orders Table

```sql
CREATE TABLE orders (
    id VARCHAR(255) PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    product_id VARCHAR(255) NOT NULL,
    quantity INTEGER NOT NULL,
    status VARCHAR(50) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE,
    updated_at TIMESTAMP WITH TIME ZONE
);
```

### Order Status Values

| Status | Description |
|--------|-------------|
| `PENDING` | Order created, awaiting processing |
| `CONFIRMED` | Order successfully processed |
| `FAILED` | Order processing failed |

## Message Formats

### SQS Message (OrderCreator → OrderProcessor)

```json
{
  "order_id": "ORD-ABC123DEF456",
  "user_id": "USER-001",
  "product_id": "PROD-001",
  "quantity": 5
}
```

### SNS Message (OrderProcessor → NotificationService)

```json
{
  "order_id": "ORD-ABC123DEF456",
  "new_status": "CONFIRMED",
  "user_id": "USER-001",
  "product_id": "PROD-001",
  "timestamp": 1234567890
}
```

## Rate Limiting & Quotas

Currently, there are no rate limits for local development. In production:

- **API Gateway Throttling**: Configurable per stage
- **Lambda Concurrency**: Default 1000, configurable in AWS
- **SQS Queue**: Up to 120,000 messages/second per partition
- **SNS Topic**: Unlimited messages

## Timeout & Retry Behavior

| Component | Timeout | Retry |
|-----------|---------|-------|
| API Gateway | 30 seconds | None (client-side: depends on caller) |
| OrderCreator Lambda | 30 seconds | None (async, client retries) |
| OrderProcessor Lambda | 60 seconds | 3 attempts (max receive count) |
| SQS Visibility | 60 seconds | Auto-retry on Lambda failure |
| SNS Publish | Immediate | Automatic retries by SNS |

## Error Handling

### Validation Errors

```javascript
// Missing field
{
  "statusCode": 400,
  "body": {
    "error": "Missing required field: quantity",
    "status_code": 400
  }
}

// Invalid type
{
  "statusCode": 400,
  "body": {
    "error": "quantity must be an integer",
    "status_code": 400
  }
}

// Out of range
{
  "statusCode": 400,
  "body": {
    "error": "quantity must be greater than 0",
    "status_code": 400
  }
}
```

### Server Errors

```javascript
// Database failure
{
  "statusCode": 500,
  "body": {
    "error": "Internal server error",
    "status_code": 500
  }
}

// SQS publish failure
{
  "statusCode": 202,
  "body": {
    "order_id": "ORD-...",
    "message": "Order created successfully (queue publish delayed)",
    "status": "PENDING"
  }
}
```

## Monitoring & Logging

### Log Structure

JSON-formatted logs containing:
- `timestamp`: ISO format timestamp
- `level`: LOG_LEVEL (INFO, WARNING, ERROR)
- `logger`: Module name
- `message`: Log message
- `function`: Function name
- `order_id`: (Optional) Associated order ID

### Example Log Entry

```json
{
  "timestamp": "2024-01-15T10:30:45.123456",
  "level": "INFO",
  "logger": "order_creator_lambda.app",
  "message": "Order ABC123 persisted to database",
  "function": "lambda_handler",
  "order_id": "ORD-ABC123"
}
```

## Testing the API

### Using curl

```bash
# Create order
curl -X POST http://localhost:4566/restapis/api-id/orders \
  -H "Content-Type: application/json" \
  -d '{"product_id":"TEST-001","quantity":1,"user_id":"TEST-USER"}'

# Test validation error
curl -X POST http://localhost:4566/restapis/api-id/orders \
  -H "Content-Type: application/json" \
  -d '{"product_id":"TEST-001"}'  # Missing quantity and user_id
```

### Using Postman

1. **Method**: POST
2. **URL**: `http://localhost:4566/restapis/{API_ID}/orders`
3. **Headers**:
   - `Content-Type: application/json`
4. **Body** (raw JSON):
   ```json
   {
     "product_id": "PROD-001",
     "quantity": 5,
     "user_id": "USER-001"
   }
   ```

### Automated Testing

```bash
# Run integration tests
pytest tests/integration/ -v

# Run specific API test
pytest tests/integration/test_integration.py::test_sqs_message_sending -v
```

## Best Practices

1. **Always include Content-Type header**
   ```
   Content-Type: application/json
   ```

2. **Validate response status before parsing body**
   ```python
   if response.status_code == 202:
       order_id = response.json()['body']['order_id']
   ```

3. **Implement exponential backoff for retries**
   ```python
   import time
   for attempt in range(3):
       try:
           response = requests.post(url, json=payload)
           break
       except requests.exceptions.RequestException:
           wait_time = 2 ** attempt
           time.sleep(wait_time)
   ```

4. **Store order_id for order tracking**
   - Use to query order status in production
   - Include in customer communications

5. **Monitor API response times**
   - Track 202 response times
   - Alert on timeouts

---

**API Version**: 1.0.0  
**Last Updated**: 2024
