# Architecture Documentation

Comprehensive architecture documentation for the Serverless Event-Driven Order Processing System.

## System Architecture Overview

### High-Level Components

```
┌─────────────────────────────────────────────────────────────────────┐
│                     External Systems                               │
│  (Clients, Mobile Apps, Web Browsers)                             │
└────────────────────┬────────────────────────────────────────────────┘
                     │ HTTP/REST
                     ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    AWS API Gateway                                 │
│  • Routes POST /orders requests                                    │
│  • Provides endpoint throttling                                    │
│  • Handles CORS and authentication                                 │
└────────────────┬────────────────────────────────────────────────────┘
                 │ Synchronous Invoke
                 ▼
        ┌─────────────────────┐
        │  OrderCreator       │
        │    Lambda           │
        │                     │
        │ • Validates input   │
        │ • Generates ID      │
        │ • Persists to DB    │
        │ • Returns 202       │
        └─────────┬───────────┘
                  │ Async SQS Send
                  ▼
        ┌─────────────────────┐         ┌──────────────────┐
        │  Order Processing   │◄───────►│ Database         │
        │    Queue (SQS)      │         │ (PostgreSQL)     │
        │                     │         │                  │
        │ • Durable           │         │ • Orders table   │
        │ • Batching          │         │ • Audit trail    │
        │ • DLQ               │         └──────────────────┘
        └─────────┬───────────┘
                  │ Event Trigger
                  ▼
        ┌─────────────────────┐
        │ OrderProcessor      │
        │   Lambda            │
        │                     │
        │ • Batch processing  │
        │ • Idempotency       │
        │ • Simulate work     │
        │ • Update DB         │
        └─────────┬───────────┘
                  │ Async SNS Publish
                  ▼
        ┌─────────────────────┐
        │  Order Status       │
        │  Notifications      │
        │   (SNS Topic)       │
        │                     │
        │ • Fan-out messages  │
        │ • Multiple subs     │
        └─────────┬───────────┘
                  │ Event Trigger
                  ▼
        ┌─────────────────────┐
        │ Notification        │
        │   Service Lambda    │
        │                     │
        │ • Parse message     │
        │ • Log notification  │
        │ • Format output     │
        └─────────────────────┘
```

## Component Details

### 1. API Gateway

**Purpose**: Entry point for all order creation requests

**Responsibilities**:
- Route HTTP requests to Lambda functions
- Provide REST API interface
- Handle request/response transformation
- Apply throttling and authorization

**Configuration**:
- Method: POST
- Path: /orders
- Integration: Lambda proxy integration
- CORS: Enabled for cross-origin requests
- Authorization: API Key or custom authorizer (optional)

**Response Codes**:
- 202: Accepted (order created and queued)
- 400: Bad Request (validation error)
- 500: Internal Server Error (system error)

### 2. OrderCreator Lambda

**Purpose**: Process new order requests and initiate workflow

**Input**:
```json
{
  "body": "{\"product_id\": \"...\", \"quantity\": 1, \"user_id\": \"...\"}"
}
```

**Output** (202 Accepted):
```json
{
  "statusCode": 202,
  "body": {
    "order_id": "ORD-...",
    "message": "Order created successfully",
    "status": "PENDING"
  }
}
```

**Processing Steps**:
1. Parse and validate request body
2. Check all required fields and types
3. Generate unique order ID
4. Insert order into database (PENDING status)
5. Publish message to SQS queue
6. Return 202 response

**Error Handling**:
- Validation errors → 400 response
- Database errors → 500 response
- SQS errors → logged but don't fail request (order persisted)

**Key Features**:
- Stateless function (no persistent state)
- Fast execution (< 5 seconds typical)
- Immediate response to client
- Transactional database insert

**Configuration**:
- Memory: 512 MB
- Timeout: 30 seconds
- Logging: Structured JSON logs
- Concurrency: Auto-scaling

### 3. SQS Queue (Order Processing)

**Purpose**: Durable message storage for asynchronous processing

**Characteristics**:
- Queue Name: `OrderProcessingQueue`
- Visibility Timeout: 60 seconds
- Message Retention: 14 days
- Batch Size: 10 messages
- Batch Window: 10 seconds
- Dead-Letter Queue: `OrderProcessingDLQ`

**Message Format**:
```json
{
  "order_id": "ORD-ABC123",
  "user_id": "USER-001",
  "product_id": "PROD-001",
  "quantity": 5
}
```

**Message Attributes** (optional):
- Delivery attempt count
- Request ID for tracing
- Priority (for future enhancement)

**Features**:
- ✅ Message deduplication (implicit - no duplicates during batch)
- ✅ FIFO ordering within limits
- ✅ Automatic retry via visibility timeout
- ✅ DLQ for failed messages
- ✅ CloudWatch metrics

**Dead-Letter Queue**:
- Captures messages that fail 3 times
- Retained for 14 days
- Enables root cause analysis

### 4. OrderProcessor Lambda

**Purpose**: Process orders asynchronously from SQS

**Input** (SQS Event):
```json
{
  "Records": [
    {
      "messageId": "msg-123",
      "receiptHandle": "handle-123",
      "body": "{\"order_id\": \"ORD-...\", ...}"
    }
  ]
}
```

**Output**:
```json
{
  "statusCode": 200,
  "body": {
    "processed": 1,
    "results": [
      {
        "messageId": "msg-123",
        "orderId": "ORD-001",
        "status": "success",
        "newStatus": "CONFIRMED"
      }
    ]
  }
}
```

**Processing Steps**:
1. Receive batch of SQS messages (up to 10)
2. For each message:
   - Extract order ID
   - Check idempotency (prevent re-processing)
   - Retrieve order from database
   - Simulate processing (90% success rate)
   - Update order status (CONFIRMED/FAILED)
   - Publish to SNS topic
3. Return results

**Idempotency Implementation**:
- Maintains in-memory map of processed message IDs
- Checks map before processing
- Skips already-processed messages
- Cleans up old entries (keeps last 10,000)

**Error Handling**:
- Non-existent orders → logged, not retried
- Database errors → SQS retry (auto re-queue)
- SNS errors → logged but don't fail processing

**Configuration**:
- Memory: 512 MB
- Timeout: 60 seconds
- Batch Size: 10 messages
- Batch Window: 10 seconds
- Reserved Concurrency: Auto-scaling

### 5. SNS Topic (Order Status Notifications)

**Purpose**: Fan-out order status updates to multiple subscribers

**Topic Name**: `OrderStatusNotifications`

**Message Format**:
```json
{
  "order_id": "ORD-ABC123",
  "new_status": "CONFIRMED",
  "user_id": "USER-001",
  "product_id": "PROD-001",
  "timestamp": 1234567890
}
```

**Subscribers**:
- NotificationService Lambda (immediate)
- Email service (optional future)
- Analytics service (optional future)
- Mobile push notifications (optional future)

**Features**:
- ✅ Multiple subscribers
- ✅ Immediate delivery
- ✅ Retry logic (built-in)
- ✅ Dead-letter queue support
- ✅ CloudWatch metrics

### 6. NotificationService Lambda

**Purpose**: Process status notifications

**Input** (SNS Event):
```json
{
  "Records": [
    {
      "Sns": {
        "MessageId": "sns-123",
        "Subject": "Order Status Update",
        "Message": "{\"order_id\": \"...\", ...}"
      }
    }
  ]
}
```

**Processing Steps**:
1. Parse SNS message
2. Extract order details
3. Determine notification type (email/SMS/push)
4. Log notification details
5. Format response

**Output**:
```json
{
  "statusCode": 200,
  "body": {
    "processed": 1,
    "results": [
      {
        "messageId": "sns-123",
        "orderId": "ORD-001",
        "status": "sent",
        "notification_type": "email"
      }
    ]
  }
}
```

**Configuration**:
- Memory: 256 MB
- Timeout: 30 seconds
- Trigger: SNS topic

### 7. PostgreSQL Database

**Purpose**: Persistent storage for order data

**Schema**:

**Orders Table**:
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

CREATE INDEX idx_orders_user_id ON orders(user_id);
CREATE INDEX idx_orders_status ON orders(status);
CREATE INDEX idx_orders_created_at ON orders(created_at);
```

**Order Audit Table** (optional):
```sql
CREATE TABLE order_audit (
    id SERIAL PRIMARY KEY,
    order_id VARCHAR(255) REFERENCES orders(id),
    previous_status VARCHAR(50),
    new_status VARCHAR(50),
    changed_at TIMESTAMP WITH TIME ZONE,
    reason VARCHAR(500)
);
```

**Data Consistency**:
- ACID transactions for individual operations
- Eventual consistency across system
- No distributed transactions
- Audit trail for debugging

**Connection Management**:
- Connection pooling in production (PgBouncer)
- 30-second connection timeout
- Automatic connection cleanup

## Data Flow Sequences

### 1. Order Creation Flow

```
Client                API GW              OrderCreator        DB            SQS
  │                     │                     │                │             │
  ├──POST /orders──────►│                     │                │             │
  │                     ├──Invoke Lambda─────►│                │             │
  │                     │                     ├──Validate──────┐             │
  │                     │                     │                │             │
  │                     │                     ├──Generate ID───┐             │
  │                     │                     │                │             │
  │                     │                     ├──INSERT────────┤─────────────┐
  │                     │                     │                │             │
  │                     │                     ├──SQS Send─────────────────────►│
  │                     │                     │                │             │
  │                     │◄─202 Accepted───────┤                │             │
  │◄──202 Accepted──────┤                     │                │             │
  │ (order_id)          │                     │                │             │
```

### 2. Order Processing Flow

```
SQS                OrderProcessor        DB              SNS            NotifService
 │                      │                │               │                   │
 ├──Trigger────────────►│                │               │                   │
 │                      ├──Retrieve──────►│               │                   │
 │                      │◄──Order Data───┤               │                   │
 │                      ├──Process (90%) │               │                   │
 │                      ├──UPDATE────────►│               │                   │
 │                      │◄──Confirmed────┤               │                   │
 │                      ├──SNS Publish───────────────────►│                   │
 │                      │                │               ├──Trigger─────────►│
 │                      │                │               │                   ├─Log
 │◄──Delete─────────────┤                │               │                   │
```

## Asynchronous Communication Patterns

### 1. Publish-Subscribe (SNS)

**Pattern**: One-to-Many
**Use Case**: Status notifications to multiple subscribers
**Implementation**: SNS Topic with Lambda subscribers

```
OrderProcessor ──► SNS Topic ──┬────► NotificationService Lambda
                               ├────► Email Service (future)
                               └────► Analytics Service (future)
```

**Benefits**:
- Decoupled subscribers
- Easy to add new subscribers
- No coupling between services

### 2. Queue-Based Processing (SQS)

**Pattern**: Buffer-and-Batch
**Use Case**: Durable message storage and retry
**Implementation**: SQS Queue with Lambda consumer

```
OrderCreator ──► SQS Queue ──► OrderProcessor Lambda
                     ▲
                     └─ Auto-retry on failure
                        (visibility timeout)
```

**Benefits**:
- Durable message storage
- Built-in retry mechanism
- Backpressure handling
- Batch processing

## Idempotency Strategy

### Problem
Messages can be redelivered in distributed systems:
- Lambda timeout during processing
- Network issues
- Explicit retry

### Solution

**In-Memory Idempotency**:
```python
processed_messages = {}

# Check
if is_message_processed(message_id):
    return "skipped"

# Process
result = process_order(order_id)

# Mark
mark_message_processed(message_id)
```

**Advantages**:
- ✅ Simple implementation
- ✅ Fast lookup (O(1))
- ✅ Thread-safe (Lambda single-threaded)

**Limitations**:
- ❌ Lost on Lambda restart
- ❌ Won't prevent duplicates across instances

**Production Enhancement**:
Use DynamoDB with conditional writes:
```python
idempotency_table.put_item(
    Item={'message_id': msg_id, 'timestamp': now},
    ConditionExpression='attribute_not_exists(message_id)'
)
```

## Error Handling & Resilience

### 1. Validation Errors (400)

**Source**: Invalid API input
**Handling**: Return 400 immediately
**Recovery**: Client must correct input

```
Invalid Input ──► Validation ──► Return 400 ──► No retry, not queued
```

### 2. Database Errors (500)

**Source**: Connection failure, constraint violation
**Handling**: Return 500 to client
**Recovery**: 
- Client may retry
- Infrastructure team investigates

```
DB Failure ──► Catch Error ──► Return 500 ──► Client Retry (external)
```

### 3. SQS Publish Errors

**Source**: Queue unavailable
**Handling**: Log error but don't fail request
**Reason**: Order already persisted to database

```
SQS Failure ──► Log Error ──► Return 202 (order persisted)
                              ~~> Client sees success
                              ~~> Order may not be processed (manual intervention)
```

### 4. SQS Message Processing Errors

**Source**: Transient failures during processing
**Handling**: 
- Message visibility timeout expires
- Lambda re-triggered by SQS
- Up to 3 retry attempts (configurable)

```
Processing Failure ──► Visibility Timeout ──► Auto-Retry
                            (60s)              (up to 3x)
                                                    ▼
                                          Dead-Letter Queue
```

### 5. Dead-Letter Queue (DLQ)

**Purpose**: Capture permanently failed messages

**Trigger**: Message fails after max receive count (3)

**Contents**: Messages that cannot be processed

**Analysis**: 
- Inspect DLQ messages
- Identify failure pattern
- Fix root cause
- Retry or discard

## Scalability Characteristics

### 1. API Layer

**Scaling**: Automatic (API Gateway)
- Scales: 0 to 10,000+ concurrent requests
- Throttling: Configurable per stage
- Cost: Per request + data transfer

### 2. Compute Layer

**Scaling**: Automatic (Lambda)
- Concurrent Executions: 0 to 1,000 (default, configurable)
- Reserved Concurrency: Pre-allocated for predictability
- Cost: Per 100ms of execution time

### 3. Message Queue

**Scaling**: Automatic (SQS)
- Throughput: Unlimited (per partition)
- Message Size: Up to 256 KB (default)
- Retention: 1 minute to 14 days

### 4. Notification Layer

**Scaling**: Automatic (SNS)
- Throughput: Unlimited
- Subscribers: Many
- Cost: Per publish + per delivery

### 5. Database

**Scaling**: Manual (RDS)
- Instance Class: t3.micro to r6i.metal
- Storage: Auto-scaling (optional)
- Connections: Pooled, limited by instance class
- Cost: Per instance-hour + storage

## Performance Characteristics

### Latencies (Typical)

| Operation | Latency | Notes |
|-----------|---------|-------|
| API Request → Lambda | 100-500ms | Cold start ~1s first time |
| Lambda → Database | 10-50ms | Same AZ optimal |
| Lambda → SQS | 50-200ms | Message durability trade-off |
| Lambda → SNS | 50-200ms | Fan-out messaging |
| SQS → Lambda trigger | 100-1000ms | Polling interval |
| **Total (OrderCreator)** | **200-1000ms** | Excluding cold start |
| **Total (OrderProcessor)** | **500-3000ms** | Batch of 10 messages |

### Throughput

| Component | Throughput | Bottleneck |
|-----------|-----------|-----------|
| API Endpoint | 10K+ req/s | API Gateway quota |
| OrderCreator Lambda | 1000 concurrent | Reserved concurrency |
| SQS Queue | Unlimited | Message size (256KB) |
| OrderProcessor Lambda | 1000 concurrent | Reserved concurrency |
| Database | Instance-dependent | Connection pool, CPU |

## Cost Optimization

### 1. Lambda Memory

**Trade-off**: More memory = higher cost but faster execution

```
256 MB  → $0.0000041667 per 100ms
512 MB  → $0.0000083333 per 100ms (2x)
1024 MB → $0.0000166667 per 100ms (4x)
```

**Optimal**: 512MB balances cost and performance

### 2. Database

**Sizing**: 
- Dev: db.t3.micro (burstable, low cost)
- Staging/Prod: db.t3.small or larger

**Optimization**:
- Read replicas for heavy queries
- Connection pooling (PgBouncer)
- Query optimization and indexing

### 3. Message Routing

**SQS vs SNS**:
- Use SQS for: Durable, sequenced processing
- Use SNS for: Fast, fan-out notifications

**Best Practice**: SQS → Lambda → SNS (as in this system)

## Monitoring & Observability

### Metrics to Track

**Lambda**:
- Execution Duration (target: < 5s for OrderCreator, < 10s for OrderProcessor)
- Errors (target: < 1%)
- Throttles (target: 0)
- Cold Starts

**SQS**:
- Queue Depth (target: < 100)
- Age of Oldest Message (target: < 1min)
- Dead-Letter Queue Messages (target: 0)

**API Gateway**:
- 4XX Errors (target: < 5%)
- 5XX Errors (target: < 1%)
- Latency P99 (target: < 5s)

**Database**:
- Query Latency (target: < 100ms)
- Connection Count (target: < max pool size)
- Replication Lag (if multi-region)

### Alarms

```
OrderProcessor Errors > 5 in 5min ──► SNS Topic ──► PagerDuty/Slack
DLQ Message Count  > 0 ──────────────► SNS Topic ──► Investigation
Queue Depth > 1000 ───────────────────► CloudWatch Dashboard
```

---

This architecture is designed for:
- ✅ **Scalability**: Auto-scaling serverless components
- ✅ **Resilience**: Built-in retry, DLQ, fault isolation
- ✅ **Maintainability**: Clear separation of concerns
- ✅ **Cost-effectiveness**: Pay per use
- ✅ **Developer Experience**: Local development with LocalStack
