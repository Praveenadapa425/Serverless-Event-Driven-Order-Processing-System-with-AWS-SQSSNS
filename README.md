# Serverless Event-Driven Order Processing System (AWS SQS/SNS)

Robust backend for asynchronous order processing using API Gateway, Lambda, SQS, SNS, and PostgreSQL.

This project implements an event-driven workflow where order submission is fast and non-blocking while processing happens asynchronously and reliably.

## Features

- POST /orders endpoint via API Gateway -> OrderCreator Lambda
- Strong request validation for product_id, quantity, user_id
- Order persistence in PostgreSQL with initial PENDING status
- Reliable async processing with SQS + DLQ
- OrderProcessor Lambda updates order status to CONFIRMED or FAILED
- SNS fan-out notifications to NotificationService Lambda
- Structured JSON logging across all Lambda functions
- Local development with Docker Compose + LocalStack
- Unit and integration test suites
- Infrastructure templates under infrastructure/

## Latest Compliance Fixes

- 202 is returned only after successful enqueue:
	- OrderCreator now returns 500 if SQS enqueue fails.
- Durable idempotency across cold starts and multiple instances:
	- OrderProcessor now uses PostgreSQL-backed idempotency (processed_messages table) instead of in-memory state.

## High-Level Architecture

1. Client sends POST /orders.
2. OrderCreator Lambda validates payload, creates order row in PostgreSQL (PENDING), enqueues order_id to OrderProcessingQueue, returns 202.
3. SQS triggers OrderProcessor Lambda.
4. OrderProcessor performs durable idempotency check, processes order, updates status in DB.
5. OrderProcessor publishes order status event to OrderStatusNotifications SNS topic.
6. NotificationService Lambda receives SNS event and logs notification details.

See also:
- API details: API_DOCS.md
- Architecture notes: ARCHITECTURE.md

## Project Structure

src/
- order_creator_lambda/
- order_processor_lambda/
- notification_service_lambda/
- shared/

tests/
- unit/
- integration/

infrastructure/
- serverless.yml
- template.yaml

scripts/
- init-localstack.sh
- init-db.sql
- setup.sh
- deploy-to-aws.sh
- deploy-to-aws.ps1

## Tech Stack

- Python 3.9 (Lambda runtime)
- AWS API Gateway, Lambda, SQS, SNS
- PostgreSQL
- LocalStack
- Docker Compose
- pytest

## Prerequisites

- Docker and Docker Compose
- Python 3.9+ and pip
- Node.js and npm (for serverless deployment tooling)
- AWS CLI (for cloud deployment)

## Environment Variables

Copy .env.example to .env and update values as needed.

Core variables:
- AWS_ENDPOINT_URL
- AWS_DEFAULT_REGION
- AWS_ACCESS_KEY_ID
- AWS_SECRET_ACCESS_KEY
- DB_HOST
- DB_PORT
- DB_NAME
- DB_USER
- DB_PASSWORD
- ORDER_PROCESSING_QUEUE_URL
- ORDER_PROCESSING_DLQ_URL
- ORDER_STATUS_TOPIC_ARN

## Local Setup

### Option A: One-command setup (Linux/macOS)

```bash
bash scripts/setup.sh
```

### Option B: Manual setup (all platforms)

```bash
docker-compose build
docker-compose up -d
```

What starts:
- localstack container (API Gateway, Lambda, SQS, SNS)
- postgres-db container
- lambda runtime images for local testing

Health checks are defined for:
- localstack
- postgres-db

## API

### Create Order

Endpoint:
- POST /orders

Sample request body:

```json
{
	"product_id": "PROD-001",
	"quantity": 2,
	"user_id": "USER-123"
}
```

Success response:
- 202 Accepted
- returns generated order_id

Validation failures:
- 400 Bad Request

System failures (example: enqueue failure):
- 500 Internal Server Error

Detailed contract and examples are in API_DOCS.md.

## Database Schema

orders table:
- id (PK)
- user_id
- product_id
- quantity
- status
- created_at
- updated_at

Additional table for durable idempotency:
- processed_messages
	- message_id (PK)
	- order_id
	- processed_at

## Idempotency and Consistency

- OrderProcessor performs a DB-backed insert-once check using message_id.
- Duplicate SQS redeliveries are safely skipped.
- Status transitions are persisted transactionally in PostgreSQL.

## Running Tests

Install dependencies:

```bash
pip install -r requirements.txt
pip install pytest pytest-cov flake8 black
```

Run unit tests:

```bash
pytest tests/unit -v
```

Run integration tests:

```bash
pytest tests/integration -v --tb=short
```

Run all tests with coverage:

```bash
pytest tests -v --cov=src --cov-report=term-missing
```

## Useful Commands

Using Makefile:

```bash
make up
make test-unit
make test-integration
make logs
make down
```

Direct Docker logs:

```bash
docker-compose logs -f localstack
docker-compose logs -f postgres-db
```

## Deployment (AWS)

### Linux/macOS

```bash
bash scripts/deploy-to-aws.sh
```

### Windows PowerShell

```powershell
./scripts/deploy-to-aws.ps1 -Stage dev -Region us-east-1
```

Infrastructure definitions:
- infrastructure/serverless.yml
- infrastructure/template.yaml

## Requirement Coverage Summary

- POST /orders endpoint: implemented
- OrderCreator validation: implemented
- Initial order persistence: implemented
- SQS publish and immediate async workflow: implemented
- SQS DLQ: implemented
- OrderProcessor SQS trigger: implemented
- Idempotent processing: implemented with durable DB tracking
- Order status updates + SNS publish: implemented
- NotificationService SNS subscription + logging: implemented
- LocalStack + Docker Compose local environment: implemented
- Unit/integration tests: implemented

## Troubleshooting

- Error: No module named pytest
	- Install test dependencies:
		- pip install pytest pytest-cov

- LocalStack not healthy
	- Check logs:
		- docker-compose logs -f localstack

- DB connection failures
	- Verify DB_* values in .env
	- Confirm postgres-db is healthy:
		- docker-compose ps

## License

For educational and portfolio use.
