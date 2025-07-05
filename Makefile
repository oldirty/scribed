# Development Makefile for Scribed

.PHONY: help install install-dev test test-watch lint format type-check clean run docs

help:  ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Targets:'
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  %-15s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

install:  ## Install the package
	pip install -e .

install-dev:  ## Install development dependencies
	pip install -e ".[dev]"
	pre-commit install

test:  ## Run tests
	pytest

test-watch:  ## Run tests in watch mode
	pytest-watch

test-cov:  ## Run tests with coverage
	pytest --cov=scribed --cov-report=html --cov-report=term

lint:  ## Run linting
	flake8 src tests

format:  ## Format code
	black src tests

format-check:  ## Check code formatting
	black --check src tests

type-check:  ## Run type checking
	mypy src

clean:  ## Clean build artifacts
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	rm -rf .coverage
	rm -rf htmlcov/
	rm -rf .pytest_cache/
	rm -rf .mypy_cache/
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

run:  ## Run the daemon
	scribed start

run-config:  ## Run with example config
	scribed start --config config.yaml.example

docs:  ## Generate documentation (placeholder)
	@echo "Documentation generation not yet implemented"

build:  ## Build the package
	python -m build

dev-setup:  ## Complete development setup
	$(MAKE) install-dev
	$(MAKE) format
	$(MAKE) test
	@echo "Development environment ready!"

ci:  ## Run CI checks locally
	$(MAKE) format-check
	$(MAKE) lint
	$(MAKE) type-check
	$(MAKE) test
