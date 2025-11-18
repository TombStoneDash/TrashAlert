---
sidebar_position: 5
title: Running Tests
slug: /guides/testing
---

# Testing Guide

How to run tests for TrashAlert to ensure code quality and correctness.

## Test Structure

TrashAlert has comprehensive test coverage:

```
tests/
├── unit/              # Unit tests for individual functions
├── integration/       # Integration tests for API endpoints
├── fixtures/          # Test data and fixtures
└── conftest.py        # Pytest configuration
```

## Running Tests

### All Tests

```bash
# Run all tests
pytest

# With verbose output
pytest -v

# Show print statements
pytest -s

# With coverage report
pytest --cov=app --cov=api
```

### Specific Tests

```bash
# Run specific test file
pytest tests/unit/test_utils.py

# Run specific test function
pytest tests/unit/test_utils.py::test_normalize_address

# Run tests matching pattern
pytest -k "lookup"

# Run only integration tests
pytest tests/integration/
```

### Test Coverage

```bash
# Generate coverage report
pytest --cov=app --cov=api --cov-report=html

# View report
open htmlcov/index.html
```

## Unit Tests

Test individual functions and components.

### Example: Testing Address Normalization

```python
# tests/unit/test_utils.py
import pytest
from app.utils import normalize_address

def test_normalize_address():
    """Test address normalization."""
    result = normalize_address("1122 Palmview Ave, El Centro, CA")

    assert "1122" in result['normalized_address']
    assert "PALMVIEW" in result['normalized_address']
    assert "EL CENTRO" in result['city']

def test_normalize_address_variations():
    """Test various address formats."""
    variations = [
        "1122 Palmview Street, El Centro, CA",
        "1122 PALMVIEW AVE, el centro, ca",
        "1122 Palmview Avenue, El Centro, California"
    ]

    for addr in variations:
        result = normalize_address(addr)
        assert "1122" in result['normalized_address']
```

### Running Unit Tests

```bash
pytest tests/unit/ -v

pytest tests/unit/test_utils.py -v

pytest tests/unit/ --cov=app.utils
```

## Integration Tests

Test API endpoints with real or mocked database.

### Example: Testing Lookup Endpoint

```python
# tests/integration/test_lookup.py
import pytest
from fastapi.testclient import TestClient
from app.main import app

@pytest.fixture
def client():
    return TestClient(app)

def test_lookup_by_address(client):
    """Test address lookup."""
    response = client.get(
        "/lookup?address=1122%20Palmview%20Ave,%20El%20Centro,%20CA"
    )

    assert response.status_code == 200
    data = response.json()
    assert "matched_address" in data
    assert data["city_name"] == "El Centro"

def test_lookup_unknown_address(client):
    """Test lookup of unknown address."""
    response = client.get(
        "/lookup?address=unknown%20street,%20unknown%20city"
    )

    assert response.status_code == 200
    data = response.json()
    assert data["data_source"] == "UNKNOWN"

def test_lookup_by_coordinates(client):
    """Test coordinate-based lookup."""
    response = client.get("/lookup?lat=32.7971&lon=-115.2645")

    assert response.status_code == 200
    data = response.json()
    assert data.get("lat") is not None
    assert data.get("lon") is not None

def test_lookup_missing_parameters(client):
    """Test with missing required parameters."""
    response = client.get("/lookup")

    assert response.status_code == 400
    data = response.json()
    assert "error" in data
```

### Running Integration Tests

```bash
pytest tests/integration/ -v

pytest tests/integration/test_lookup.py::test_lookup_by_address -v

pytest tests/integration/test_lookup.py -s  # Show output
```

## API Testing

Test API endpoints and responses.

### Example: Testing Report Submission

```python
# tests/integration/test_report.py
def test_submit_report(client):
    """Test report submission."""
    response = client.post(
        "/report",
        json={
            "address": "1122 Palmview Ave, El Centro, CA",
            "trash_day": "WED",
            "user_hash": "test_user"
        }
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["message"] == "Report submitted successfully"
    assert data["address_id"] > 0

def test_submit_report_missing_day(client):
    """Test report with missing pickup day."""
    response = client.post(
        "/report",
        json={
            "address": "1122 Palmview Ave, El Centro, CA"
        }
    )

    assert response.status_code == 422
    data = response.json()
    assert "Validation Error" in data["error"]

def test_report_consensus_update(client):
    """Test that consensus updates with reports."""
    address = "123 Main St, El Centro, CA"

    # Submit first report
    client.post("/report", json={
        "address": address,
        "trash_day": "MON"
    })

    # Submit second report
    response = client.post("/report", json={
        "address": address,
        "trash_day": "MON"
    })

    data = response.json()
    assert data["consensus"]["trash_day"] == "Monday"
    assert data["consensus"]["reports_count"] == 2
```

## Load Testing

Test API performance under load.

### Using Locust

```python
# tests/load/locustfile.py
from locust import HttpUser, task, between

class TrashAlertUser(HttpUser):
    wait_time = between(1, 3)

    @task
    def lookup(self):
        """Simulate address lookup."""
        self.client.get(
            "/lookup?address=1122%20Palmview%20Ave,%20El%20Centro,%20CA"
        )

    @task
    def submit_report(self):
        """Simulate report submission."""
        self.client.post(
            "/report",
            json={
                "address": "1122 Palmview Ave, El Centro, CA",
                "trash_day": "WED"
            }
        )

    @task
    def get_stats(self):
        """Simulate statistics request."""
        self.client.get("/stats")
```

**Run load test:**

```bash
# Install locust
pip install locust

# Run with 10 users
locust -f tests/load/locustfile.py --users 10 --spawn-rate 2 -u http://localhost:8000

# Headless mode
locust -f tests/load/locustfile.py --users 10 --spawn-rate 2 -u http://localhost:8000 --headless --run-time 5m
```

## Performance Testing

Test query performance and database efficiency.

```python
# tests/performance/test_queries.py
import pytest
import time

def test_lookup_performance(client):
    """Ensure lookup completes quickly."""
    start = time.time()

    response = client.get(
        "/lookup?address=1122%20Palmview%20Ave,%20El%20Centro,%20CA"
    )

    duration = time.time() - start

    assert response.status_code == 200
    assert duration < 0.5  # Must complete in < 500ms

def test_stats_endpoint_performance(client):
    """Stats endpoint should be fast (cached)."""
    start = time.time()

    response = client.get("/stats")

    duration = time.time() - start

    assert response.status_code == 200
    assert duration < 0.1  # Must complete in < 100ms
```

## Fixtures and Mocks

### Common Fixtures

```python
# tests/conftest.py
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base
from app.main import app
from fastapi.testclient import TestClient

@pytest.fixture
def test_db():
    """Create in-memory test database."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return engine

@pytest.fixture
def client(test_db):
    """Create test client with test database."""
    from app.database import get_db

    def override_get_db():
        Session = sessionmaker(autocommit=False, autoflush=False, bind=test_db)
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)

@pytest.fixture
def sample_address(test_db):
    """Create sample address for tests."""
    from app.models import Address
    from sqlalchemy.orm import sessionmaker

    Session = sessionmaker(bind=test_db)
    db = Session()

    address = Address(
        normalized_address="1122 PALMVIEW AVE, EL CENTRO, CA",
        house_number="1122",
        street="PALMVIEW AVE",
        city_name="El Centro",
        state="CA",
        zip_code="92243",
        lat=32.7971,
        lon=-115.2645
    )

    db.add(address)
    db.commit()
    return address
```

## Continuous Integration

### GitHub Actions Workflow

```yaml
# .github/workflows/test.yml
name: Tests

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main, develop]

jobs:
  test:
    runs-on: ubuntu-latest

    services:
      postgres:
        image: postgres:14
        env:
          POSTGRES_DB: trashalert_test
          POSTGRES_USER: test
          POSTGRES_PASSWORD: test
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt
          pip install pytest pytest-cov

      - name: Run tests
        run: pytest --cov=app --cov=api

      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          files: ./coverage.xml
```

## Test Commands Summary

```bash
# All tests
pytest

# Verbose output
pytest -v

# With coverage
pytest --cov=app --cov=api

# Specific test file
pytest tests/unit/test_utils.py

# Tests matching pattern
pytest -k "lookup"

# Stop on first failure
pytest -x

# Show print statements
pytest -s

# Parallel execution
pytest -n auto

# Generate HTML report
pytest --html=report.html
```

## Best Practices

1. **Write tests first** (TDD) or alongside code
2. **One assertion per test** (or logically grouped)
3. **Use descriptive test names** - `test_lookup_by_address_returns_schedule`
4. **Use fixtures** for test data and setup
5. **Mock external services** - APIs, databases
6. **Test edge cases** - empty strings, invalid values, etc.
7. **Keep tests independent** - no test should depend on another
8. **Use parameterization** for testing multiple scenarios

## Resources

- [Pytest Documentation](https://docs.pytest.org/)
- [FastAPI Testing](https://fastapi.tiangolo.com/advanced/testing-dependencies/)
- [SQLAlchemy Testing](https://docs.sqlalchemy.org/en/20/faq/testing.html)
- [Locust Load Testing](https://locust.io/)

