---
sidebar_position: 1
title: Local Setup Guide
slug: /guides/setup
---

# Local Development Setup

Get TrashAlert running on your local machine in less than 10 minutes.

## Prerequisites

- Python 3.9+
- Git
- pip (Python package manager)
- PostgreSQL 12+ OR SQLite (default)

**Optional:**
- Docker & Docker Compose
- Make

## Quick Start (5 minutes)

### 1. Clone the Repository

```bash
git clone https://github.com/TombStoneDash/TrashAlert.git
cd TrashAlert
```

### 2. Install Dependencies

```bash
# Create virtual environment
python -m venv venv

# Activate it
# On Linux/Mac:
source venv/bin/activate

# On Windows:
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Set Up Environment

```bash
# Copy example environment file
cp .env.example .env

# Edit .env if needed (defaults work for local development)
nano .env
```

### 4. Initialize Database

```bash
# Create and populate database
python -m alembic upgrade head

# Or for quick start with sample data:
python scripts/init_db.py
```

### 5. Start the API Server

```bash
# Start development server
uvicorn app.main:app --reload --port 8000

# Server available at http://localhost:8000
```

### 6. Test the API

In another terminal:

```bash
# Health check
curl http://localhost:8000/

# Lookup address
curl "http://localhost:8000/lookup?address=1122%20Palmview%20Ave,%20El%20Centro,%20CA"

# Submit report
curl -X POST http://localhost:8000/report \
  -H "Content-Type: application/json" \
  -d '{
    "address": "1122 Palmview Ave, El Centro, CA",
    "trash_day": "WED"
  }'
```

## Detailed Setup

### Python Virtual Environment

**Why use a virtual environment?**
- Isolates project dependencies
- Prevents conflicts with system Python
- Makes development cleaner

**Create and activate:**

```bash
# Create
python -m venv venv

# Activate
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows

# Verify
which python              # Should show venv path
```

**Deactivate when done:**
```bash
deactivate
```

### Install Python Dependencies

```bash
# Upgrade pip first
pip install --upgrade pip

# Install all dependencies
pip install -r requirements.txt

# Verify installation
python -c "import fastapi; print(fastapi.__version__)"
```

**Key dependencies:**
- FastAPI - Web framework
- SQLAlchemy - ORM
- Pydantic - Data validation
- Alembic - Database migrations
- Psycopg2 - PostgreSQL adapter

### Database Setup

#### Option 1: SQLite (Default, Easiest)

SQLite works out of the box. No additional setup needed.

```bash
# Database file will be created automatically
python -m alembic upgrade head
```

**Good for:**
- Local development
- Testing
- Small deployments

#### Option 2: PostgreSQL

PostgreSQL provides better performance and features.

**Install PostgreSQL:**
```bash
# macOS
brew install postgresql

# Ubuntu/Debian
sudo apt-get install postgresql postgresql-contrib

# Windows
# Download from https://www.postgresql.org/download/windows/
```

**Create database and user:**
```bash
# Connect to PostgreSQL
psql postgres

# Create database
CREATE DATABASE trashalert;

# Create user
CREATE USER trashalert WITH PASSWORD 'your_secure_password';

# Grant permissions
ALTER ROLE trashalert SET client_encoding TO 'utf8';
ALTER ROLE trashalert SET default_transaction_isolation TO 'read committed';
ALTER ROLE trashalert SET default_transaction_deferrable TO on;
ALTER ROLE trashalert SET timezone TO 'UTC';
GRANT ALL PRIVILEGES ON DATABASE trashalert TO trashalert;

# Exit
\q
```

**Configure .env:**
```bash
DATABASE_URL=postgresql://trashalert:password@localhost:5432/trashalert
```

**Run migrations:**
```bash
python -m alembic upgrade head
```

### Environment Configuration

Create `.env` file from template:

```bash
cp .env.example .env
```

**Key variables:**

```env
# Database
DATABASE_URL=sqlite:///./data/trashalert.db
# or for PostgreSQL:
# DATABASE_URL=postgresql://user:pass@localhost/trashalert

# API
API_HOST=0.0.0.0
API_PORT=8000
API_RELOAD=true

# Environment
ENVIRONMENT=development
DEBUG=true

# Optional: OpenAI for address interpretation
OPENAI_API_KEY=your_key_here
ANTHROPIC_API_KEY=your_key_here
```

### Running the Server

**Development Mode (with auto-reload):**

```bash
# Using uvicorn directly
uvicorn app.main:app --reload

# Using Python
python -m uvicorn app.main:app --reload

# With custom port
uvicorn app.main:app --reload --port 8001
```

**Production Mode:**

```bash
# Using gunicorn (better for production)
gunicorn -w 4 -b 0.0.0.0:8000 app.main:app
```

**Access the API:**
- API: http://localhost:8000
- Documentation: http://localhost:8000/docs
- Alternative docs: http://localhost:8000/redoc

## Docker Setup (Alternative)

If you prefer Docker:

```bash
# Build and start all services
docker-compose up --build

# In another terminal, initialize database
docker-compose exec api python scripts/init_db.py

# Test the API
curl http://localhost/lookup?address=test
```

**Services:**
- API: http://localhost
- PostgreSQL: localhost:5432

## Frontend Setup (Optional)

The admin dashboard requires Node.js:

```bash
# Install Node.js from https://nodejs.org/

# Navigate to frontend
cd frontend/admin-dashboard

# Install dependencies
npm install

# Start development server
npm start

# Access at http://localhost:3000
```

## Verification

### Check Installation

```bash
# Python version
python --version

# FastAPI
python -c "import fastapi; print(fastapi.__version__)"

# Database connection
python -c "from app.database import SessionLocal; SessionLocal()"
```

### Test API Endpoints

```bash
# Health check
curl http://localhost:8000/

# Should return:
# {"status":"healthy","service":"TrashAlert API","version":"1.0.0"}

# Get statistics
curl http://localhost:8000/stats
```

## Common Issues

### "ModuleNotFoundError: No module named 'fastapi'"

**Solution:** Virtual environment not activated
```bash
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows
```

### "ERROR: Database connection failed"

**For SQLite:**
```bash
# Ensure data directory exists
mkdir -p data

# Run migrations
python -m alembic upgrade head
```

**For PostgreSQL:**
```bash
# Check connection
psql -U trashalert -d trashalert -h localhost

# If connection fails:
# 1. Verify PostgreSQL is running
# 2. Check DATABASE_URL in .env
# 3. Verify user/password
```

### "Address already in use :8000"

**Solution:** Use different port
```bash
uvicorn app.main:app --reload --port 8001
```

### Port Already in Use

```bash
# Find what's using the port (macOS/Linux)
lsof -i :8000

# Kill the process
kill -9 <PID>

# On Windows
netstat -ano | findstr :8000
taskkill /PID <PID> /F
```

## Next Steps

1. **Read the [Quick Start](/docs/guides/quickstart)** - 5-minute tutorial
2. **Explore the [API](/docs/api/overview)** - Learn endpoints
3. **Run the [Tests](/docs/guides/testing)** - Verify everything works
4. **Check the [Contributing Guide](/docs/guides/contributing)** - Help improve TrashAlert

## Getting Help

- **Docs**: Check [/docs](/docs/)
- **Issues**: [GitHub Issues](https://github.com/TombStoneDash/TrashAlert/issues)
- **Email**: support@trashalert.com

## Development Tools

### Useful Commands

```bash
# Run tests
pytest

# Format code
black app tests

# Lint
flake8 app tests

# Type checking
mypy app

# Database shell
psql trashalert  # PostgreSQL
sqlite3 data/trashalert.db  # SQLite
```

### IDE Setup

**Visual Studio Code:**
```bash
# Install extensions
# - Python (Microsoft)
# - Pylance
# - SQLTools
# - Thunder Client (for API testing)
```

**PyCharm:**
- Professional edition recommended
- Built-in database tools
- Better Python support

## Useful Resources

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [SQLAlchemy Documentation](https://docs.sqlalchemy.org/)
- [Pydantic Documentation](https://pydantic-settings.readthedocs.io/)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)

