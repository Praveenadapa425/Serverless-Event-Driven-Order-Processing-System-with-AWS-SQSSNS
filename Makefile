.PHONY: help setup up down logs clean test test-unit test-integration test-coverage db-connect lint format

help:
	@echo "Serverless Event-Driven Order Processing System"
	@echo "=============================================="
	@echo ""
	@echo "Available commands:"
	@echo "  make setup              - Complete setup and start services"
	@echo "  make up                 - Start Docker services"
	@echo "  make down               - Stop Docker services"
	@echo "  make logs               - View service logs"
	@echo "  make test               - Run all tests"
	@echo "  make test-unit          - Run unit tests only"
	@echo "  make test-integration   - Run integration tests"
	@echo "  make test-coverage      - Run tests with coverage report"
	@echo "  make db-connect         - Connect to PostgreSQL"
	@echo "  make clean              - Clean up containers and cache"
	@echo "  make lint               - Run code linting"
	@echo "  make format             - Format code"
	@echo ""

setup:
	@echo "Setting up project..."
	@bash scripts/setup.sh

up:
	@echo "Starting Docker services..."
	docker-compose up -d
	@echo "Services started. Waiting for health checks..."
	@sleep 10
	docker-compose ps

down:
	@echo "Stopping Docker services..."
	docker-compose down

logs:
	docker-compose logs -f

test:
	@echo "Running all tests..."
	pytest tests/ -v

test-unit:
	@echo "Running unit tests..."
	pytest tests/unit/ -v

test-integration:
	@echo "Running integration tests..."
	pytest tests/integration/ -v --tb=short

test-coverage:
	@echo "Running tests with coverage..."
	pytest tests/ -v --cov=src --cov-report=html --cov-report=term-missing
	@echo ""
	@echo "Coverage report generated in htmlcov/index.html"

db-connect:
	@echo "Connecting to PostgreSQL database..."
	docker exec -it postgres-db psql -U postgres -d orders_db

clean:
	@echo "Cleaning up..."
	docker-compose down -v
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -name .coverage -delete
	rm -rf htmlcov/
	@echo "Cleanup complete"

lint:
	@echo "Running linting..."
	flake8 src/ tests/ --max-line-length=120 --ignore=E501,W503

format:
	@echo "Formatting code..."
	black src/ tests/ --line-length=120

status:
	@echo "Service Status:"
	docker-compose ps

logs-localstack:
	docker-compose logs -f localstack

logs-postgres:
	docker-compose logs -f postgres-db

build:
	@echo "Building Docker images..."
	docker-compose build

dev-shell:
	@echo "Starting development shell..."
	docker-compose exec order-creator-service /bin/bash
