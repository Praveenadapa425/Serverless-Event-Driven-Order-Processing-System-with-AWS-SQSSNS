#!/bin/bash

set -euo pipefail

echo "Initializing LocalStack resources..."

export AWS_ACCESS_KEY_ID=test
export AWS_SECRET_ACCESS_KEY=test
export AWS_DEFAULT_REGION=us-east-1

ROLE_ARN="arn:aws:iam::000000000000:role/lambda-execution-role"
ORDER_CREATOR_FN="OrderCreatorFunction"
ORDER_PROCESSOR_FN="OrderProcessorFunction"
NOTIFICATION_FN="NotificationServiceFunction"
ORDER_QUEUE_NAME="OrderProcessingQueue"
DLQ_NAME="OrderProcessingDLQ"
TOPIC_NAME="OrderStatusNotifications"
API_NAME="OrderProcessingAPI"

ORDER_CREATOR_IMAGE="local/order-creator-lambda:latest"
ORDER_PROCESSOR_IMAGE="local/order-processor-lambda:latest"
NOTIFICATION_IMAGE="local/notification-service-lambda:latest"

for i in $(seq 1 30); do
  if awslocal sts get-caller-identity >/dev/null 2>&1; then
    break
  fi
  echo "Waiting for LocalStack readiness ($i/30)..."
  sleep 2
done

echo "Creating SQS queues..."
awslocal sqs create-queue --queue-name "$ORDER_QUEUE_NAME" >/dev/null
awslocal sqs create-queue --queue-name "$DLQ_NAME" >/dev/null

QUEUE_URL=$(awslocal sqs get-queue-url --queue-name "$ORDER_QUEUE_NAME" --query 'QueueUrl' --output text)
QUEUE_ARN=$(awslocal sqs get-queue-attributes --queue-url "$QUEUE_URL" --attribute-names QueueArn --query 'Attributes.QueueArn' --output text)
DLQ_URL=$(awslocal sqs get-queue-url --queue-name "$DLQ_NAME" --query 'QueueUrl' --output text)
DLQ_ARN=$(awslocal sqs get-queue-attributes --queue-url "$DLQ_URL" --attribute-names QueueArn --query 'Attributes.QueueArn' --output text)

awslocal sqs set-queue-attributes \
  --queue-url "$QUEUE_URL" \
  --attributes RedrivePolicy="{\"deadLetterTargetArn\":\"$DLQ_ARN\",\"maxReceiveCount\":3}"

echo "Creating SNS topic..."
TOPIC_ARN=$(awslocal sns create-topic --name "$TOPIC_NAME" --query 'TopicArn' --output text)

upsert_lambda_image() {
  local function_name=$1
  local image_uri=$2
  local env_vars=$3

  if awslocal lambda get-function --function-name "$function_name" >/dev/null 2>&1; then
    echo "Updating Lambda image for $function_name"
    awslocal lambda update-function-code --function-name "$function_name" --image-uri "$image_uri" >/dev/null
    awslocal lambda update-function-configuration --function-name "$function_name" --environment "$env_vars" >/dev/null
  else
    echo "Creating Lambda $function_name"
    awslocal lambda create-function \
      --function-name "$function_name" \
      --package-type Image \
      --code ImageUri="$image_uri" \
      --role "$ROLE_ARN" \
      --timeout 30 \
      --memory-size 512 \
      --environment "$env_vars" >/dev/null
  fi
}

ORDER_CREATOR_ENV="Variables={AWS_ENDPOINT_URL=http://host.docker.internal:4566,AWS_REGION=us-east-1,AWS_ACCESS_KEY_ID=test,AWS_SECRET_ACCESS_KEY=test,DB_HOST=host.docker.internal,DB_PORT=5432,DB_NAME=orders_db,DB_USER=postgres,DB_PASSWORD=postgres,ORDER_PROCESSING_QUEUE_URL=$QUEUE_URL}"
ORDER_PROCESSOR_ENV="Variables={AWS_ENDPOINT_URL=http://host.docker.internal:4566,AWS_REGION=us-east-1,AWS_ACCESS_KEY_ID=test,AWS_SECRET_ACCESS_KEY=test,DB_HOST=host.docker.internal,DB_PORT=5432,DB_NAME=orders_db,DB_USER=postgres,DB_PASSWORD=postgres,ORDER_STATUS_TOPIC_ARN=$TOPIC_ARN}"
NOTIFICATION_ENV="Variables={AWS_ENDPOINT_URL=http://host.docker.internal:4566,AWS_REGION=us-east-1,AWS_ACCESS_KEY_ID=test,AWS_SECRET_ACCESS_KEY=test}"

upsert_lambda_image "$ORDER_CREATOR_FN" "$ORDER_CREATOR_IMAGE" "$ORDER_CREATOR_ENV"
upsert_lambda_image "$ORDER_PROCESSOR_FN" "$ORDER_PROCESSOR_IMAGE" "$ORDER_PROCESSOR_ENV"
upsert_lambda_image "$NOTIFICATION_FN" "$NOTIFICATION_IMAGE" "$NOTIFICATION_ENV"

ORDER_CREATOR_ARN=$(awslocal lambda get-function --function-name "$ORDER_CREATOR_FN" --query 'Configuration.FunctionArn' --output text)
ORDER_PROCESSOR_ARN=$(awslocal lambda get-function --function-name "$ORDER_PROCESSOR_FN" --query 'Configuration.FunctionArn' --output text)
NOTIFICATION_ARN=$(awslocal lambda get-function --function-name "$NOTIFICATION_FN" --query 'Configuration.FunctionArn' --output text)

echo "Configuring SQS -> OrderProcessor event source mapping..."
MAPPING_EXISTS=$(awslocal lambda list-event-source-mappings \
  --function-name "$ORDER_PROCESSOR_FN" \
  --event-source-arn "$QUEUE_ARN" \
  --query 'length(EventSourceMappings)' \
  --output text)

if [ "$MAPPING_EXISTS" = "0" ]; then
  awslocal lambda create-event-source-mapping \
    --function-name "$ORDER_PROCESSOR_FN" \
    --event-source-arn "$QUEUE_ARN" \
    --batch-size 10 >/dev/null
fi

echo "Configuring SNS -> NotificationService subscription..."
awslocal lambda add-permission \
  --function-name "$NOTIFICATION_FN" \
  --statement-id allow-sns-invoke \
  --action lambda:InvokeFunction \
  --principal sns.amazonaws.com \
  --source-arn "$TOPIC_ARN" >/dev/null 2>&1 || true

SUB_EXISTS=$(awslocal sns list-subscriptions-by-topic \
  --topic-arn "$TOPIC_ARN" \
  --query "length(Subscriptions[?Endpoint=='$NOTIFICATION_ARN'])" \
  --output text)

if [ "$SUB_EXISTS" = "0" ]; then
  awslocal sns subscribe \
    --topic-arn "$TOPIC_ARN" \
    --protocol lambda \
    --notification-endpoint "$NOTIFICATION_ARN" >/dev/null
fi

echo "Creating API Gateway and Lambda proxy integration..."
API_ID=$(awslocal apigateway get-rest-apis --query "items[?name=='$API_NAME'].id | [0]" --output text)
if [ "$API_ID" = "None" ]; then
  API_ID=$(awslocal apigateway create-rest-api --name "$API_NAME" --description 'API for order processing' --query 'id' --output text)
fi

ROOT_RESOURCE=$(awslocal apigateway get-resources --rest-api-id "$API_ID" --query "items[?path=='/'].id | [0]" --output text)
ORDERS_RESOURCE=$(awslocal apigateway get-resources --rest-api-id "$API_ID" --query "items[?path=='/orders'].id | [0]" --output text)

if [ "$ORDERS_RESOURCE" = "None" ]; then
  ORDERS_RESOURCE=$(awslocal apigateway create-resource \
    --rest-api-id "$API_ID" \
    --parent-id "$ROOT_RESOURCE" \
    --path-part orders \
    --query 'id' \
    --output text)
fi

awslocal apigateway put-method \
  --rest-api-id "$API_ID" \
  --resource-id "$ORDERS_RESOURCE" \
  --http-method POST \
  --authorization-type NONE >/dev/null 2>&1 || true

LAMBDA_URI="arn:aws:apigateway:us-east-1:lambda:path/2015-03-31/functions/${ORDER_CREATOR_ARN}/invocations"

awslocal apigateway put-integration \
  --rest-api-id "$API_ID" \
  --resource-id "$ORDERS_RESOURCE" \
  --http-method POST \
  --type AWS_PROXY \
  --integration-http-method POST \
  --uri "$LAMBDA_URI" >/dev/null

awslocal lambda add-permission \
  --function-name "$ORDER_CREATOR_FN" \
  --statement-id allow-apigw-invoke \
  --action lambda:InvokeFunction \
  --principal apigateway.amazonaws.com \
  --source-arn "arn:aws:execute-api:us-east-1:000000000000:${API_ID}/*/POST/orders" >/dev/null 2>&1 || true

awslocal apigateway create-deployment \
  --rest-api-id "$API_ID" \
  --stage-name dev >/dev/null

echo "LocalStack initialization complete"
echo "API ID: $API_ID"
echo "POST endpoint: http://localhost:4566/restapis/$API_ID/dev/_user_request_/orders"
