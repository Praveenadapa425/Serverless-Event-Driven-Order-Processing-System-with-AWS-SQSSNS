import json
import logging
import os
import uuid
from datetime import datetime, timezone

import boto3
import psycopg

logger = logging.getLogger()
logger.setLevel(logging.INFO)

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "orders_db")
DB_USER = os.getenv("DB_USER", "orders_user")
DB_PASSWORD = os.getenv("DB_PASSWORD", "orders_password")

AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
AWS_ENDPOINT_URL = os.getenv("AWS_ENDPOINT_URL")
ORDER_QUEUE_NAME = os.getenv("ORDER_QUEUE_NAME", "OrderProcessingQueue")


def _response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }


def _log(level, message, **context):
    payload = {"message": message, **context}
    getattr(logger, level)(json.dumps(payload))


def _parse_event_body(event):
    body = event.get("body") if isinstance(event, dict) else None
    if body is None:
        raise ValueError("Missing request body")

    if isinstance(body, str):
        try:
            return json.loads(body)
        except json.JSONDecodeError as exc:
            raise ValueError("Request body must be valid JSON") from exc

    if isinstance(body, dict):
        return body

    raise ValueError("Unsupported request body format")


def _validate_payload(payload):
    errors = []

    user_id = payload.get("user_id")
    product_id = payload.get("product_id")
    quantity = payload.get("quantity")

    if not isinstance(user_id, str) or not user_id.strip():
        errors.append("user_id must be a non-empty string")

    if not isinstance(product_id, str) or not product_id.strip():
        errors.append("product_id must be a non-empty string")

    if not isinstance(quantity, int) or quantity <= 0:
        errors.append("quantity must be a positive integer")

    if errors:
        raise ValueError("; ".join(errors))

    return {
        "user_id": user_id.strip(),
        "product_id": product_id.strip(),
        "quantity": quantity,
    }


def _get_db_connection():
    return psycopg.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
    )


def _create_order_record(payload):
    order_id = str(uuid.uuid4())

    with _get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO orders (id, user_id, product_id, quantity, status)
                VALUES (%s, %s, %s, %s, 'PENDING')
                """,
                (order_id, payload["user_id"], payload["product_id"], payload["quantity"]),
            )
        conn.commit()

    return order_id


def _get_sqs_client():
    kwargs = {"region_name": AWS_REGION}
    if AWS_ENDPOINT_URL:
        kwargs["endpoint_url"] = AWS_ENDPOINT_URL
    return boto3.client("sqs", **kwargs)


def _publish_order_placed(order_id, payload):
    sqs_client = _get_sqs_client()
    queue_url = sqs_client.get_queue_url(QueueName=ORDER_QUEUE_NAME)["QueueUrl"]

    sqs_client.send_message(
        QueueUrl=queue_url,
        MessageBody=json.dumps(
            {
                "event_type": "ORDER_PLACED",
                "order_id": order_id,
                "user_id": payload["user_id"],
                "product_id": payload["product_id"],
                "quantity": payload["quantity"],
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        ),
        MessageAttributes={
            "event_type": {"DataType": "String", "StringValue": "ORDER_PLACED"},
            "order_id": {"DataType": "String", "StringValue": order_id},
        },
    )


def lambda_handler(event, context):
    request_id = getattr(context, "aws_request_id", "local-request")
    _log("info", "OrderCreator invoked", request_id=request_id)

    try:
        payload = _validate_payload(_parse_event_body(event))
    except ValueError as exc:
        _log("warning", "Validation failed", request_id=request_id, error=str(exc))
        return _response(400, {"error": str(exc)})

    try:
        order_id = _create_order_record(payload)
        _publish_order_placed(order_id, payload)
    except Exception as exc:
        _log("error", "Failed to create order", request_id=request_id, error=str(exc))
        return _response(
            500,
            {
                "error": "Failed to create order",
                "request_id": request_id,
            },
        )

    _log("info", "Order accepted", request_id=request_id, order_id=order_id)
    return _response(
        202,
        {
            "message": "Order accepted for asynchronous processing",
            "order_id": order_id,
            "status": "PENDING",
        },
    )
