#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
BUILD_DIR="$PROJECT_ROOT/.build"
PACKAGE_DIR="$BUILD_DIR/order_creator_package"
ZIP_PATH="$BUILD_DIR/order_creator_lambda.zip"

AWS_REGION="${AWS_REGION:-us-east-1}"
AWS_ENDPOINT_URL="${AWS_ENDPOINT_URL:-http://localhost:4566}"

ORDER_QUEUE_NAME="${ORDER_QUEUE_NAME:-OrderProcessingQueue}"
ORDER_DLQ_NAME="${ORDER_DLQ_NAME:-OrderProcessingDLQ}"
ORDER_CREATOR_FUNCTION_NAME="${ORDER_CREATOR_FUNCTION_NAME:-OrderCreatorFunction}"
ORDER_API_NAME="${ORDER_API_NAME:-OrderServiceApi}"

DB_HOST="${DB_HOST:-postgres}"
DB_PORT="${DB_PORT:-5432}"
DB_NAME="${DB_NAME:-orders_db}"
DB_USER="${DB_USER:-orders_user}"
DB_PASSWORD="${DB_PASSWORD:-orders_password}"

ROLE_ARN="arn:aws:iam::000000000000:role/lambda-role"

AWS_CMD=(aws --endpoint-url "$AWS_ENDPOINT_URL" --region "$AWS_REGION")

mkdir -p "$PACKAGE_DIR"
rm -rf "$PACKAGE_DIR"/* "$ZIP_PATH"

python -m pip install --upgrade pip >/dev/null
python -m pip install -r "$PROJECT_ROOT/src/order_creator_lambda/requirements.txt" -t "$PACKAGE_DIR" >/dev/null
cp "$PROJECT_ROOT/src/order_creator_lambda/app.py" "$PACKAGE_DIR/app.py"
(
  cd "$PACKAGE_DIR"
  zip -qr "$ZIP_PATH" .
)

echo "Creating DLQ and processing queue..."
DLQ_URL=$("${AWS_CMD[@]}" sqs create-queue --queue-name "$ORDER_DLQ_NAME" --query QueueUrl --output text)
DLQ_ARN=$("${AWS_CMD[@]}" sqs get-queue-attributes --queue-url "$DLQ_URL" --attribute-names QueueArn --query "Attributes.QueueArn" --output text)

REDRIVE_POLICY=$(printf '{"maxReceiveCount":"5","deadLetterTargetArn":"%s"}' "$DLQ_ARN")
"${AWS_CMD[@]}" sqs create-queue --queue-name "$ORDER_QUEUE_NAME" --attributes RedrivePolicy="$REDRIVE_POLICY" >/dev/null

echo "Deploying OrderCreator Lambda..."
if "${AWS_CMD[@]}" lambda get-function --function-name "$ORDER_CREATOR_FUNCTION_NAME" >/dev/null 2>&1; then
  "${AWS_CMD[@]}" lambda update-function-code --function-name "$ORDER_CREATOR_FUNCTION_NAME" --zip-file "fileb://${ZIP_PATH}" >/dev/null
  "${AWS_CMD[@]}" lambda update-function-configuration \
    --function-name "$ORDER_CREATOR_FUNCTION_NAME" \
    --runtime python3.12 \
    --handler app.lambda_handler \
    --environment "Variables={AWS_REGION=${AWS_REGION},AWS_ENDPOINT_URL=${AWS_ENDPOINT_URL},ORDER_QUEUE_NAME=${ORDER_QUEUE_NAME},DB_HOST=${DB_HOST},DB_PORT=${DB_PORT},DB_NAME=${DB_NAME},DB_USER=${DB_USER},DB_PASSWORD=${DB_PASSWORD}}" >/dev/null
else
  "${AWS_CMD[@]}" lambda create-function \
    --function-name "$ORDER_CREATOR_FUNCTION_NAME" \
    --runtime python3.12 \
    --handler app.lambda_handler \
    --zip-file "fileb://${ZIP_PATH}" \
    --timeout 30 \
    --role "$ROLE_ARN" \
    --environment "Variables={AWS_REGION=${AWS_REGION},AWS_ENDPOINT_URL=${AWS_ENDPOINT_URL},ORDER_QUEUE_NAME=${ORDER_QUEUE_NAME},DB_HOST=${DB_HOST},DB_PORT=${DB_PORT},DB_NAME=${DB_NAME},DB_USER=${DB_USER},DB_PASSWORD=${DB_PASSWORD}}" >/dev/null
fi

echo "Configuring API Gateway..."
API_ID=$("${AWS_CMD[@]}" apigateway get-rest-apis --query "items[?name=='${ORDER_API_NAME}'].id | [0]" --output text)
if [ "$API_ID" = "None" ] || [ -z "$API_ID" ]; then
  API_ID=$("${AWS_CMD[@]}" apigateway create-rest-api --name "$ORDER_API_NAME" --query id --output text)
fi

ROOT_ID=$("${AWS_CMD[@]}" apigateway get-resources --rest-api-id "$API_ID" --query "items[?path=='/'].id | [0]" --output text)
ORDERS_RESOURCE_ID=$("${AWS_CMD[@]}" apigateway get-resources --rest-api-id "$API_ID" --query "items[?path=='/orders'].id | [0]" --output text)
if [ "$ORDERS_RESOURCE_ID" = "None" ] || [ -z "$ORDERS_RESOURCE_ID" ]; then
  ORDERS_RESOURCE_ID=$("${AWS_CMD[@]}" apigateway create-resource --rest-api-id "$API_ID" --parent-id "$ROOT_ID" --path-part orders --query id --output text)
fi

"${AWS_CMD[@]}" apigateway put-method --rest-api-id "$API_ID" --resource-id "$ORDERS_RESOURCE_ID" --http-method POST --authorization-type NONE >/dev/null || true

LAMBDA_ARN="arn:aws:lambda:${AWS_REGION}:000000000000:function:${ORDER_CREATOR_FUNCTION_NAME}"
INTEGRATION_URI="arn:aws:apigateway:${AWS_REGION}:lambda:path/2015-03-31/functions/${LAMBDA_ARN}/invocations"

"${AWS_CMD[@]}" apigateway put-integration \
  --rest-api-id "$API_ID" \
  --resource-id "$ORDERS_RESOURCE_ID" \
  --http-method POST \
  --type AWS_PROXY \
  --integration-http-method POST \
  --uri "$INTEGRATION_URI" >/dev/null

"${AWS_CMD[@]}" lambda add-permission \
  --function-name "$ORDER_CREATOR_FUNCTION_NAME" \
  --statement-id "apigateway-invoke-post-orders" \
  --action lambda:InvokeFunction \
  --principal apigateway.amazonaws.com \
  --source-arn "arn:aws:execute-api:${AWS_REGION}:000000000000:${API_ID}/*/POST/orders" >/dev/null 2>&1 || true

"${AWS_CMD[@]}" apigateway create-deployment --rest-api-id "$API_ID" --stage-name local >/dev/null

echo "Phase 1 bootstrap complete."
echo "POST endpoint: ${AWS_ENDPOINT_URL}/restapis/${API_ID}/local/_user_request_/orders"
