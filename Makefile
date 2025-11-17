.PHONY: test test-verbose test-coverage install clean help

# Default target
help:
	@echo "TrashAlert - Available make commands:"
	@echo ""
	@echo "  make install        Install dependencies"
	@echo "  make test          Run all tests"
	@echo "  make test-verbose  Run tests with verbose output"
	@echo "  make test-coverage Run tests with coverage report"
	@echo "  make clean         Clean up temporary files"
	@echo ""

# Install dependencies
install:
	pip install -r requirements.txt

# Run all tests
test:
	python -m pytest

# Run tests with verbose output
test-verbose:
	python -m pytest -v

# Run tests with coverage
test-coverage:
	python -m pytest --cov=src --cov-report=html --cov-report=term

# Clean up temporary files
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	rm -rf htmlcov
	rm -rf .coverage
	rm -f trashalert.db
