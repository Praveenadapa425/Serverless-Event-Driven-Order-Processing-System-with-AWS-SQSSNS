#!/bin/bash
# AWS Setup and Deployment Script
# Automates the entire AWS deployment process

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
AWS_REGION=${AWS_REGION:-us-east-1}
STAGE=${STAGE:-dev}
PROJECT_NAME="serverless-order-processing"

echo -e "${BLUE}╔════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   AWS Deployment Setup for Order Processing       ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════╝${NC}"
echo ""

# Step 1: Check Prerequisites
echo -e "${YELLOW}[1/8] Checking Prerequisites...${NC}"

check_command() {
    if ! command -v $1 &> /dev/null; then
        echo -e "${RED}✗ $1 is not installed${NC}"
        return 1
    else
        echo -e "${GREEN}✓ $1 found${NC}"
        return 0
    fi
}

check_command "aws" || exit 1
check_command "node" || exit 1
check_command "npm" || exit 1
check_command "python" || exit 1

echo ""

# Step 2: Configure AWS Credentials
echo -e "${YELLOW}[2/8] Configuring AWS Credentials...${NC}"

mkdir -p ~/.aws

# Check if credentials already exist
if [ -f ~/.aws/credentials ]; then
    echo -e "${GREEN}✓ AWS credentials file found${NC}"
else
    echo -e "${RED}✗ AWS credentials file not found at ~/.aws/credentials${NC}"
    echo -e "${YELLOW}Run 'aws configure' first, then re-run this script.${NC}"
    exit 1
fi

# Create AWS config
if [ ! -f ~/.aws/config ]; then
    cat > ~/.aws/config << EOF
[default]
region = $AWS_REGION
output = json
EOF
    echo -e "${GREEN}✓ AWS config created${NC}"
fi

echo ""

# Step 3: Verify AWS Credentials
echo -e "${YELLOW}[3/8] Verifying AWS Credentials...${NC}"

ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text 2>/dev/null)
if [ -z "$ACCOUNT_ID" ]; then
    echo -e "${RED}✗ Failed to verify AWS credentials${NC}"
    exit 1
else
    echo -e "${GREEN}✓ AWS credentials verified${NC}"
    echo "  Account ID: $ACCOUNT_ID"
fi

echo ""

# Step 4: Install Serverless Framework
echo -e "${YELLOW}[4/8] Installing Serverless Framework...${NC}"

npm install -g serverless --silent 2>/dev/null || npm install -g serverless

if command -v serverless &> /dev/null; then
    echo -e "${GREEN}✓ Serverless Framework installed${NC}"
    echo "  Version: $(serverless --version)"
else
    echo -e "${RED}✗ Failed to install Serverless Framework${NC}"
    exit 1
fi

echo ""

# Step 5: Install Serverless Plugins
echo -e "${YELLOW}[5/8] Installing Serverless Plugins...${NC}"

cd infrastructure/ 2>/dev/null || cd ../infrastructure/ 2>/dev/null || true

if [ -f package.json ]; then
    npm install --silent 2>/dev/null || npm install
    echo -e "${GREEN}✓ Serverless plugins installed${NC}"
else
    echo -e "${YELLOW}⚠ No package.json found in infrastructure/$(NC}"
fi

cd - > /dev/null

echo ""

# Step 6: Build and Package
echo -e "${YELLOW}[6/8] Building Lambda Functions...${NC}"

pip install -q -r requirements.txt 2>/dev/null || pip install -r requirements.txt

echo -e "${GREEN}✓ Dependencies installed${NC}"

echo ""

# Step 7: Deploy to AWS
echo -e "${YELLOW}[7/8] Deploying to AWS...${NC}"

read -p "Enter database password (minimum 8 characters): " -s DB_PASSWORD
echo ""

if [ ${#DB_PASSWORD} -lt 8 ]; then
    echo -e "${RED}✗ Password must be at least 8 characters${NC}"
    exit 1
fi

cd infrastructure/ 2>/dev/null || cd ../infrastructure/ 2>/dev/null || true

echo -e "${YELLOW}Starting deployment to $STAGE environment...${NC}"

serverless deploy \
    --stage $STAGE \
    --region $AWS_REGION \
    --param="dbPassword=$DB_PASSWORD" \
    --verbose

DEPLOY_STATUS=$?

if [ $DEPLOY_STATUS -eq 0 ]; then
    echo -e "${GREEN}✓ Deployment completed successfully${NC}"
else
    echo -e "${RED}✗ Deployment failed${NC}"
    exit 1
fi

echo ""

# Step 8: Display Deployment Information
echo -e "${YELLOW}[8/8] Deployment Information...${NC}"

echo -e "${GREEN}Service Details:${NC}"
serverless info --stage $STAGE --region $AWS_REGION

echo ""
echo -e "${GREEN}Deployment Outputs:${NC}"

# Get outputs from CloudFormation
aws cloudformation describe-stacks \
    --stack-name "$PROJECT_NAME-$STAGE" \
    --region $AWS_REGION \
    --query 'Stacks[0].Outputs' \
    --output table 2>/dev/null || true

cd - > /dev/null

echo ""

# Display next steps
echo -e "${BLUE}═══════════════════════════════════════════════════${NC}"
echo -e "${GREEN}✓ AWS Deployment Complete!${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════${NC}"
echo ""
echo -e "${YELLOW}Next Steps:${NC}"
echo "1. Initialize the database:"
echo "   psql -h <RDS-ENDPOINT> -U postgres -d orders_db -f scripts/init-db.sql"
echo ""
echo "2. Test the API endpoint:"
echo "   curl -X POST <API-ENDPOINT> \\"
echo "     -H 'Content-Type: application/json' \\"
echo "     -d '{\"product_id\": \"TEST-001\", \"quantity\": 1, \"user_id\": \"TEST-USER\"}'"
echo ""
echo "3. Monitor logs:"
echo "   serverless logs -f orderCreator --stage $STAGE --region $AWS_REGION --tail"
echo ""
echo "4. Remove deployment (when done):"
echo "   serverless remove --stage $STAGE --region $AWS_REGION"
echo ""
