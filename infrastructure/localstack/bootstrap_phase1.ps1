$ErrorActionPreference = "Stop"

$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
$BuildDir = Join-Path $ProjectRoot ".build"
$PackageDir = Join-Path $BuildDir "order_creator_package"
$ZipPath = Join-Path $BuildDir "order_creator_lambda.zip"

$AWS_REGION = $env:AWS_REGION; if (-not $AWS_REGION) { $AWS_REGION = "us-east-1" }
$AWS_ENDPOINT_URL = $env:AWS_ENDPOINT_URL_HOST; if (-not $AWS_ENDPOINT_URL) { $AWS_ENDPOINT_URL = "http://localhost:4566" }

$ORDER_QUEUE_NAME = $env:ORDER_QUEUE_NAME; if (-not $ORDER_QUEUE_NAME) { $ORDER_QUEUE_NAME = "OrderProcessingQueue" }
$ORDER_DLQ_NAME = $env:ORDER_DLQ_NAME; if (-not $ORDER_DLQ_NAME) { $ORDER_DLQ_NAME = "OrderProcessingDLQ" }
$ORDER_CREATOR_FUNCTION_NAME = $env:ORDER_CREATOR_FUNCTION_NAME; if (-not $ORDER_CREATOR_FUNCTION_NAME) { $ORDER_CREATOR_FUNCTION_NAME = "OrderCreatorFunction" }
$ORDER_API_NAME = $env:ORDER_API_NAME; if (-not $ORDER_API_NAME) { $ORDER_API_NAME = "OrderServiceApi" }

$DB_HOST = $env:DB_HOST; if (-not $DB_HOST) { $DB_HOST = "postgres" }
$DB_PORT = $env:DB_PORT; if (-not $DB_PORT) { $DB_PORT = "5432" }
$DB_NAME = $env:DB_NAME; if (-not $DB_NAME) { $DB_NAME = "orders_db" }
$DB_USER = $env:DB_USER; if (-not $DB_USER) { $DB_USER = "orders_user" }
$DB_PASSWORD = $env:DB_PASSWORD; if (-not $DB_PASSWORD) { $DB_PASSWORD = "orders_password" }

$RoleArn = "arn:aws:iam::000000000000:role/lambda-role"
$AwsBase = @("--endpoint-url", $AWS_ENDPOINT_URL, "--region", $AWS_REGION)

if (Test-Path $PackageDir) { Remove-Item $PackageDir -Recurse -Force }
if (Test-Path $ZipPath) { Remove-Item $ZipPath -Force }
New-Item -Path $PackageDir -ItemType Directory -Force | Out-Null

python -m pip install --upgrade pip | Out-Null
python -m pip install -r (Join-Path $ProjectRoot "src/order_creator_lambda/requirements.txt") -t $PackageDir | Out-Null
Copy-Item (Join-Path $ProjectRoot "src/order_creator_lambda/app.py") (Join-Path $PackageDir "app.py")
Compress-Archive -Path (Join-Path $PackageDir "*") -DestinationPath $ZipPath -Force

Write-Host "Creating DLQ and processing queue..."
$DlqUrl = aws @AwsBase sqs create-queue --queue-name $ORDER_DLQ_NAME --query QueueUrl --output text
$DlqArn = aws @AwsBase sqs get-queue-attributes --queue-url $DlqUrl --attribute-names QueueArn --query "Attributes.QueueArn" --output text
$RedrivePolicy = "{\"maxReceiveCount\":\"5\",\"deadLetterTargetArn\":\"$DlqArn\"}"
aws @AwsBase sqs create-queue --queue-name $ORDER_QUEUE_NAME --attributes RedrivePolicy=$RedrivePolicy | Out-Null

Write-Host "Deploying OrderCreator Lambda..."
$FunctionExists = $true
try {
  aws @AwsBase lambda get-function --function-name $ORDER_CREATOR_FUNCTION_NAME | Out-Null
} catch {
  $FunctionExists = $false
}

$EnvVars = "Variables={AWS_REGION=$AWS_REGION,AWS_ENDPOINT_URL=$AWS_ENDPOINT_URL,ORDER_QUEUE_NAME=$ORDER_QUEUE_NAME,DB_HOST=$DB_HOST,DB_PORT=$DB_PORT,DB_NAME=$DB_NAME,DB_USER=$DB_USER,DB_PASSWORD=$DB_PASSWORD}"
if ($FunctionExists) {
  aws @AwsBase lambda update-function-code --function-name $ORDER_CREATOR_FUNCTION_NAME --zip-file ("fileb://" + $ZipPath) | Out-Null
  aws @AwsBase lambda update-function-configuration --function-name $ORDER_CREATOR_FUNCTION_NAME --runtime python3.12 --handler app.lambda_handler --environment $EnvVars | Out-Null
} else {
  aws @AwsBase lambda create-function --function-name $ORDER_CREATOR_FUNCTION_NAME --runtime python3.12 --handler app.lambda_handler --zip-file ("fileb://" + $ZipPath) --timeout 30 --role $RoleArn --environment $EnvVars | Out-Null
}

Write-Host "Configuring API Gateway..."
$ApiId = aws @AwsBase apigateway get-rest-apis --query "items[?name=='$ORDER_API_NAME'].id | [0]" --output text
if ([string]::IsNullOrWhiteSpace($ApiId) -or $ApiId -eq "None") {
  $ApiId = aws @AwsBase apigateway create-rest-api --name $ORDER_API_NAME --query id --output text
}

$RootId = aws @AwsBase apigateway get-resources --rest-api-id $ApiId --query "items[?path=='/'].id | [0]" --output text
$OrdersResourceId = aws @AwsBase apigateway get-resources --rest-api-id $ApiId --query "items[?path=='/orders'].id | [0]" --output text
if ([string]::IsNullOrWhiteSpace($OrdersResourceId) -or $OrdersResourceId -eq "None") {
  $OrdersResourceId = aws @AwsBase apigateway create-resource --rest-api-id $ApiId --parent-id $RootId --path-part orders --query id --output text
}

try {
  aws @AwsBase apigateway put-method --rest-api-id $ApiId --resource-id $OrdersResourceId --http-method POST --authorization-type NONE | Out-Null
} catch {
}

$LambdaArn = "arn:aws:lambda:$AWS_REGION:000000000000:function:$ORDER_CREATOR_FUNCTION_NAME"
$IntegrationUri = "arn:aws:apigateway:$AWS_REGION:lambda:path/2015-03-31/functions/$LambdaArn/invocations"
aws @AwsBase apigateway put-integration --rest-api-id $ApiId --resource-id $OrdersResourceId --http-method POST --type AWS_PROXY --integration-http-method POST --uri $IntegrationUri | Out-Null

try {
  aws @AwsBase lambda add-permission --function-name $ORDER_CREATOR_FUNCTION_NAME --statement-id "apigateway-invoke-post-orders" --action lambda:InvokeFunction --principal apigateway.amazonaws.com --source-arn "arn:aws:execute-api:$AWS_REGION:000000000000:$ApiId/*/POST/orders" | Out-Null
} catch {
}

aws @AwsBase apigateway create-deployment --rest-api-id $ApiId --stage-name local | Out-Null

Write-Host "Phase 1 bootstrap complete."
Write-Host "POST endpoint: $AWS_ENDPOINT_URL/restapis/$ApiId/local/_user_request_/orders"
