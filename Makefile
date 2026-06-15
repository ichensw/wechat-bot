.PHONY: install test lint clean run check init

# Configuration
CONFIG ?= config.yaml
PYTHON ?= python3

# Default target
help:
	@echo "WeChatBot v2.0 - Available targets:"
	@echo "  make install    - Install Python dependencies"
	@echo "  make test       - Run all tests"
	@echo "  make lint       - Run linter (ruff)"
	@echo "  make clean      - Remove generated files"
	@echo "  make run        - Start the bot"
	@echo "  make check      - Check WeChat login status"
	@echo "  make init       - Create default config"

# Install dependencies
install:
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -r requirements.txt
	$(PYTHON) -m pip install -e ".[dev]"

# Run tests
test:
	$(PYTHON) -m pytest tests/ -v --tb=short

# Run tests with coverage
test-cov:
	$(PYTHON) -m pytest tests/ -v --tb=short --cov=bot --cov-report=term-missing

# Lint
lint:
	$(PYTHON) -m ruff check bot/ tests/ main.py
	$(PYTHON) -m ruff format --check bot/ tests/ main.py

# Format
format:
	$(PYTHON) -m ruff format bot/ tests/ main.py
	$(PYTHON) -m ruff check --fix bot/ tests/ main.py

# Clean
clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name *.egg-info -exec rm -rf {} + 2>/dev/null || true
	rm -rf data/ dist/ build/ .mypy_cache/

# Run the bot
run:
	$(PYTHON) main.py -c $(CONFIG)

# Check WeChat login
check:
	$(PYTHON) main.py --check -c $(CONFIG)

# Create default config
init:
	$(PYTHON) main.py --init -c $(CONFIG)

# Docker build
docker-build:
	docker build -t wechat-bot:latest .

# Docker run
docker-run:
	docker compose up -d

# Docker logs
docker-logs:
	docker compose logs -f wechat-bot
