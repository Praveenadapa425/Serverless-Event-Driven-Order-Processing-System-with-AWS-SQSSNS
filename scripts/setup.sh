#!/bin/bash
# Setup and run the complete order processing system

set -e

echo "🚀 Serverless Event-Driven Order Processing System Setup"
echo "========================================================"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check prerequisites
echo -e "${YELLOW}Checking prerequisites...${NC}"

if ! command -v docker &> /dev/null; then
    echo -e "${RED}Docker is not installed${NC}"
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo -e "${RED}Docker Compose is not installed${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Docker and Docker Compose found${NC}"

# Copy environment file
if [ ! -f .env ]; then
    echo -e "${YELLOW}Creating .env file from template...${NC}"
    cp .env.example .env
    echo -e "${GREEN}✓ .env created${NC}"
else
    echo -e "${GREEN}✓ .env already exists${NC}"
fi

# Install Python dependencies
echo -e "${YELLOW}Installing Python dependencies...${NC}"
pip install -q -r requirements.txt
echo -e "${GREEN}✓ Dependencies installed${NC}"

# Build and start services
echo -e "${YELLOW}Building and starting Docker services...${NC}"
docker-compose build --quiet
echo -e "${GREEN}✓ Docker images built${NC}"

echo -e "${YELLOW}Starting services (this may take 30-60 seconds)...${NC}"
docker-compose up -d

# Wait for services to be healthy
echo -e "${YELLOW}Waiting for services to be ready...${NC}"

MAX_RETRIES=30
RETRY=0

while [ $RETRY -lt $MAX_RETRIES ]; do
    if curl -s http://localhost:4566/_localstack/health > /dev/null 2>&1; then
        echo -e "${GREEN}✓ LocalStack is ready${NC}"
        break
    fi
    
    RETRY=$((RETRY + 1))
    if [ $RETRY -eq $MAX_RETRIES ]; then
        echo -e "${RED}LocalStack failed to start after $MAX_RETRIES attempts${NC}"
        exit 1
    fi
    
    echo "Attempt $RETRY/$MAX_RETRIES..."
    sleep 2
done

# Check database
RETRY=0
while [ $RETRY -lt $MAX_RETRIES ]; do
    if docker exec postgres-db pg_isready -U postgres -d orders_db > /dev/null 2>&1; then
        echo -e "${GREEN}✓ PostgreSQL is ready${NC}"
        break
    fi
    
    RETRY=$((RETRY + 1))
    if [ $RETRY -eq $MAX_RETRIES ]; then
        echo -e "${RED}PostgreSQL failed to start${NC}"
        exit 1
    fi
    
    sleep 2
done

# Display service status
echo ""
echo -e "${YELLOW}Service Status:${NC}"
docker-compose ps

# Display setup information
echo ""
echo -e "${GREEN}========================================================"
echo "✓ Setup Complete!"
echo "========================================================${NC}"
echo ""
echo "Available commands:"
echo "  - pytest tests/unit/ -v                    # Run unit tests"
echo "  - pytest tests/integration/ -v             # Run integration tests"
echo "  - pytest tests/ --cov=src                  # Run all tests with coverage"
echo "  - docker-compose logs localstack           # View LocalStack logs"
echo "  - docker-compose logs postgres-db          # View database logs"
echo "  - docker-compose down                      # Stop all services"
echo ""
echo "LocalStack endpoint: http://localhost:4566"
echo "PostgreSQL endpoint: localhost:5432"
echo ""

echo -e "${YELLOW}Running unit tests...${NC}"
pytest tests/unit/ -v --tb=short

echo ""
echo -e "${GREEN}✓ All unit tests passed!${NC}"
echo ""
echo "To run integration tests, use:"
echo "  pytest tests/integration/ -v"
echo ""
