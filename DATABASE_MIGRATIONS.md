# Database Migrations Guide

This document explains how to work with database migrations in the TrashAlert project.

## Overview

TrashAlert uses **Alembic** for database migrations and supports both **SQLite** (for local development) and **PostgreSQL** (for production).

## Database Configuration

### Environment Variables

Set the `DATABASE_URL` environment variable to configure your database:

```bash
# SQLite (default for local development)
DATABASE_URL=sqlite:///./trashalert.db

# PostgreSQL (for production)
DATABASE_URL=postgresql://user:password@localhost:5432/trashalert
```

### Configuration Files

- **`.env.example`** - Local development configuration with SQLite
- **`.env.production.example`** - Production configuration with PostgreSQL

## Quick Start

### Initialize Database

To set up the database and add sample data:

```bash
python init_db.py
```

This will:
1. Run all pending migrations
2. Create database tables
3. Add sample address data (if database is empty)

### Using Makefile Commands

The project includes convenient Makefile targets for database operations:

```bash
# Run migrations (upgrade to latest version)
make migrate

# Rollback last migration
make downgrade

# Reset database (WARNING: deletes all data)
make reset-db
```

## Working with Migrations

### Creating New Migrations

When you modify models in `app/models.py`, create a new migration:

```bash
# Auto-generate migration from model changes
alembic revision --autogenerate -m "Description of changes"

# Review the generated migration file in alembic/versions/
# Then apply it
make migrate
```

### Applying Migrations

```bash
# Upgrade to latest version
alembic upgrade head

# Or use the Makefile
make migrate
```

### Rolling Back Migrations

```bash
# Rollback one migration
alembic downgrade -1

# Or use the Makefile
make downgrade

# Rollback to specific version
alembic downgrade <revision_id>

# Rollback all migrations
alembic downgrade base
```

### Viewing Migration History

```bash
# Show current version
alembic current

# Show migration history
alembic history

# Show pending migrations
alembic heads
```

## Database Engines

### SQLite (Local Development)

**Pros:**
- No setup required
- Fast for development
- Single file database

**Cons:**
- Limited concurrency
- Not suitable for production

**Configuration:**
```bash
DATABASE_URL=sqlite:///./trashalert.db
```

### PostgreSQL (Production)

**Pros:**
- Production-ready
- Better concurrency
- Advanced features (JSON, full-text search, etc.)

**Cons:**
- Requires PostgreSQL server
- More complex setup

**Configuration:**
```bash
DATABASE_URL=postgresql://user:password@host:port/database
```

**Docker Setup:**
```bash
# Start PostgreSQL with Docker
docker run -d \
  --name trashalert-db \
  -e POSTGRES_USER=trashalert_user \
  -e POSTGRES_PASSWORD=secure_password \
  -e POSTGRES_DB=trashalert \
  -p 5432:5432 \
  postgres:15

# Set environment variable
export DATABASE_URL=postgresql://trashalert_user:secure_password@localhost:5432/trashalert

# Run migrations
make migrate
```

## Testing Migrations

### Test with SQLite

```bash
# Clean database
rm -f trashalert.db

# Run migrations
make migrate

# Run tests
python -m pytest tests/test_database_schema.py -v
```

### Test with PostgreSQL

```bash
# Start PostgreSQL container (see Docker setup above)

# Set DATABASE_URL
export DATABASE_URL=postgresql://trashalert_user:secure_password@localhost:5432/trashalert

# Run migrations
make migrate

# Run tests
DATABASE_URL=$DATABASE_URL python -m pytest tests/ -v
```

## Migration File Structure

```
alembic/
├── versions/          # Migration files
│   └── cf3d5b32a1e3_initial_migration_with_all_tables.py
├── env.py            # Alembic environment configuration
├── script.py.mako    # Template for new migrations
└── README            # Alembic README

alembic.ini           # Alembic configuration file
```

## Troubleshooting

### Migration Conflicts

If you get migration conflicts:

```bash
# Check current state
alembic current

# Check migration history
alembic history

# Manually resolve by editing migration files
# Then upgrade
make migrate
```

### Database Connection Issues

```bash
# Verify DATABASE_URL
echo $DATABASE_URL

# Test database connection with Python
python -c "from app.database import engine; print(engine.url)"
```

### Reset Everything

If you need to start fresh:

```bash
# For SQLite
rm -f trashalert.db
alembic upgrade head

# For PostgreSQL
# Drop and recreate database, then:
make migrate
```

## Best Practices

1. **Always review auto-generated migrations** before applying them
2. **Test migrations** on a copy of production data before deploying
3. **Never edit applied migrations** - create a new migration instead
4. **Backup production database** before running migrations
5. **Use transactions** for data migrations when possible
6. **Version control** all migration files

## Additional Resources

- [Alembic Documentation](https://alembic.sqlalchemy.org/)
- [SQLAlchemy Documentation](https://docs.sqlalchemy.org/)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
