.PHONY: test test-verbose test-coverage install clean help docker-up docker-down docker-logs docker-ps docker-rebuild migrate downgrade reset-db

# Default target
help:
	@echo "TrashAlert - Available make commands:"
	@echo ""
	@echo "Development:"
	@echo "  make install        Install dependencies"
	@echo "  make test          Run all tests"
	@echo "  make test-verbose  Run tests with verbose output"
	@echo "  make test-coverage Run tests with coverage report"
	@echo "  make clean         Clean up temporary files"
	@echo ""
	@echo "Database Migrations:"
	@echo "  make migrate       Run database migrations (upgrade to latest)"
	@echo "  make downgrade     Rollback last database migration"
	@echo "  make reset-db      Reset database (WARNING: deletes all data)"
	@echo ""
	@echo "Docker Deployment:"
	@echo "  make docker-up      Build and start all containers"
	@echo "  make docker-down    Stop and remove all containers"
	@echo "  make docker-logs    View logs from all containers"
	@echo "  make docker-ps      Show status of all containers"
	@echo "  make docker-rebuild Rebuild containers from scratch"
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

# Docker commands
docker-up:
	@echo "Building and starting TrashAlert containers..."
	docker-compose up --build -d
	@echo ""
	@echo "TrashAlert is starting up!"
	@echo "API will be available at: http://localhost (via nginx)"
	@echo "Use 'make docker-logs' to view logs"
	@echo "Use 'make docker-ps' to check container status"

docker-down:
	@echo "Stopping and removing TrashAlert containers..."
	docker-compose down
	@echo "TrashAlert containers stopped."

docker-logs:
	docker-compose logs -f

docker-ps:
	docker-compose ps

docker-rebuild:
	@echo "Rebuilding TrashAlert containers from scratch..."
	docker-compose down
	docker-compose build --no-cache
	docker-compose up -d
	@echo "TrashAlert containers rebuilt and started."

# Database migration commands
migrate:
	@echo "Running database migrations..."
	alembic upgrade head
	@echo "Migrations complete!"

downgrade:
	@echo "Rolling back last database migration..."
	alembic downgrade -1
	@echo "Rollback complete!"

reset-db:
	@echo "WARNING: This will delete all database data!"
	@read -p "Are you sure? [y/N] " -n 1 -r; \
	echo; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		echo "Resetting database..."; \
		rm -f trashalert.db; \
		alembic downgrade base; \
		alembic upgrade head; \
		echo "Database reset complete!"; \
		echo "Run 'python init_db.py' to add sample data."; \
	else \
		echo "Database reset cancelled."; \
	fi
