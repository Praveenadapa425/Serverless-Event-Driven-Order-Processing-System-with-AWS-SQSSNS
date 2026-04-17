import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def lambda_handler(event, context):
    logger.info("NotificationService placeholder received event", extra={"event": event})
    return {"status": "placeholder"}
