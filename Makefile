.PHONY: help start stop clean install test

help:
	@echo "AutoTrader AI - Development Commands"
	@echo ""
	@echo "  make start    - Start local development environment"
	@echo "  make stop     - Stop all services"
	@echo "  make clean    - Clean all data and volumes"
	@echo "  make install  - Install all dependencies"
	@echo "  make test     - Run all tests"

start:
	./scripts/start-local.sh

stop:
	./scripts/stop-local.sh

clean:
	./scripts/clean-local.sh

install:
	@echo "📦 Installing dependencies..."
	cd services && mvn clean install -DskipTests
	cd web-app && npm install
	cd ml-services && pip install -r requirements.txt

test:
	@echo "🧪 Running tests..."
	cd services && mvn test
	cd web-app && npm test
	cd ml-services && pytest
