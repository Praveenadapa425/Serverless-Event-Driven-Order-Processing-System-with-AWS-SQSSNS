import json
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def lambda_handler(event, context):
    logger.info("OrderProcessor placeholder received event", extra={"event": event})
    return {"status": "placeholder", "records": len(event.get("Records", []))}
