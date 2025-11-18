---
sidebar_position: 3
title: Docker Deployment
slug: /guides/docker
---

# Docker Deployment Guide

Deploy TrashAlert using Docker and Docker Compose for consistent, reproducible environments.

## Prerequisites

- Docker 20.10+
- Docker Compose 1.29+
- Git

**Install Docker:**
- [Docker Desktop](https://www.docker.com/products/docker-desktop) (macOS, Windows)
- [Docker Engine](https://docs.docker.com/engine/install/) (Linux)

## Quick Start

```bash
# Clone repository
git clone https://github.com/TombStoneDash/TrashAlert.git
cd TrashAlert

# Build and start all services
docker-compose up --build

# In another terminal, initialize database
docker-compose exec api python scripts/init_db.py

# Test the API
curl http://localhost/lookup?address=test
```

The API is available at **http://localhost**

## Docker Compose Setup

**docker-compose.yml** includes:

### API Service

```yaml
api:
  build: .
  ports:
    - "8000:8000"
  volumes:
    - ./data:/app/data
    - ./logs:/app/logs
  environment:
    - DATABASE_URL=sqlite:///./data/trashalert.db
```

### PostgreSQL Service (Optional)

```yaml
db:
  image: postgres:14
  environment:
    POSTGRES_DB: trashalert
    POSTGRES_USER: trashalert
    POSTGRES_PASSWORD: password
  volumes:
    - postgres_data:/var/lib/postgresql/data
  ports:
    - "5432:5432"
```

### Nginx Reverse Proxy

```yaml
nginx:
  image: nginx:latest
  ports:
    - "80:80"
    - "443:443"
  volumes:
    - ./nginx.conf:/etc/nginx/nginx.conf
    - ./ssl:/etc/nginx/ssl
```

## Common Commands

### Start Services

```bash
# Build and start in background
docker-compose up --build -d

# View logs
docker-compose logs -f api

# View specific service logs
docker-compose logs -f db
```

### Stop Services

```bash
# Stop and remove containers
docker-compose down

# Stop but keep data
docker-compose stop

# Remove everything including volumes
docker-compose down -v
```

### Database Management

```bash
# Initialize database
docker-compose exec api python scripts/init_db.py

# Connect to PostgreSQL
docker-compose exec db psql -U trashalert -d trashalert

# Backup database
docker-compose exec db pg_dump -U trashalert trashalert > backup.sql

# Restore database
docker-compose exec -T db psql -U trashalert trashalert < backup.sql
```

### Debugging

```bash
# Execute command in container
docker-compose exec api bash

# Check container status
docker-compose ps

# View resource usage
docker stats

# Inspect container
docker inspect trashalert-api-1
```

## Building the Docker Image

### Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Create data directory
RUN mkdir -p data logs

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000')"

# Run application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Build Custom Image

```bash
# Build image
docker build -t trashalert:latest .

# Run container
docker run -p 8000:8000 trashalert:latest

# Build with specific Python version
docker build --build-arg PYTHON_VERSION=3.11 -t trashalert:py311 .
```

## Production Deployment

### Environment Variables

Create `.env.production`:

```env
# API
ENVIRONMENT=production
DEBUG=false
API_HOST=0.0.0.0
API_PORT=8000

# Database (use PostgreSQL in production)
DATABASE_URL=postgresql://trashalert:secure_password@db:5432/trashalert

# Security
SECRET_KEY=your_secret_key_here
ALLOWED_HOSTS=api.trashalert.com

# Optional services
OPENAI_API_KEY=sk-...
SENTRY_DSN=https://...
```

### Docker Compose for Production

```yaml
version: '3.8'

services:
  db:
    image: postgres:14
    environment:
      POSTGRES_DB: trashalert
      POSTGRES_USER: trashalert
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    restart: unless-stopped
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U trashalert"]
      interval: 10s
      timeout: 5s
      retries: 5

  api:
    build:
      context: .
      dockerfile: Dockerfile
    environment:
      DATABASE_URL: postgresql://trashalert:${DB_PASSWORD}@db:5432/trashalert
      ENVIRONMENT: production
      DEBUG: "false"
    depends_on:
      db:
        condition: service_healthy
    restart: unless-stopped
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/"]
      interval: 30s
      timeout: 10s
      retries: 3

  nginx:
    image: nginx:latest
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - ./ssl:/etc/nginx/ssl:ro
      - ./certbot:/etc/letsencrypt:ro
    depends_on:
      - api
    restart: unless-stopped

volumes:
  postgres_data:
```

### Nginx Configuration

```nginx
upstream api {
    server api:8000;
}

server {
    listen 80;
    server_name api.trashalert.com;

    # Redirect to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name api.trashalert.com;

    # SSL configuration
    ssl_certificate /etc/nginx/ssl/cert.pem;
    ssl_certificate_key /etc/nginx/ssl/key.pem;

    # Security headers
    add_header Strict-Transport-Security "max-age=31536000" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-Frame-Options "DENY" always;

    # Compression
    gzip on;
    gzip_types text/plain text/css application/json application/javascript;

    # Rate limiting
    limit_req_zone $binary_remote_addr zone=api:10m rate=60r/m;
    limit_req zone=api burst=100 nodelay;

    # Proxy to API
    location / {
        proxy_pass http://api;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }
}
```

## Using Docker Registry

### Push to Docker Hub

```bash
# Log in
docker login

# Tag image
docker tag trashalert:latest username/trashalert:latest

# Push
docker push username/trashalert:latest

# Pull on production server
docker pull username/trashalert:latest
```

### Private Registry

```bash
# Tag for private registry
docker tag trashalert:latest registry.example.com/trashalert:latest

# Push
docker push registry.example.com/trashalert:latest

# Use in docker-compose
services:
  api:
    image: registry.example.com/trashalert:latest
    auth:
      username: username
      password: password
```

## Scaling

### Horizontal Scaling

Run multiple API containers:

```yaml
services:
  api:
    build: .
    deploy:
      replicas: 3
    depends_on:
      - db
```

### Load Balancing

```bash
# Using Docker Swarm
docker swarm init
docker stack deploy -c docker-compose.yml trashalert

# Using Kubernetes
kubectl apply -f k8s/deployment.yaml
```

## Monitoring

### Container Logs

```bash
# Follow logs
docker-compose logs -f

# Specific service
docker-compose logs -f api

# Last 100 lines
docker-compose logs --tail=100 api
```

### Resource Monitoring

```bash
# Real-time stats
docker stats

# Inspect container
docker inspect trashalert-api-1
```

### Prometheus Metrics

Add to API:

```python
from prometheus_client import Counter, Histogram

request_count = Counter(
    'api_requests_total',
    'Total API requests',
    ['method', 'endpoint', 'status']
)

request_duration = Histogram(
    'api_request_duration_seconds',
    'API request duration'
)
```

## Backup and Recovery

### Database Backup

```bash
# Backup PostgreSQL
docker-compose exec db pg_dump -U trashalert trashalert > backup.sql

# Backup with compression
docker-compose exec db pg_dump -U trashalert trashalert | gzip > backup.sql.gz

# Upload to S3
aws s3 cp backup.sql.gz s3://bucket/backups/
```

### Restore from Backup

```bash
# Restore from file
docker-compose exec -T db psql -U trashalert trashalert < backup.sql

# Restore from S3
aws s3 cp s3://bucket/backups/backup.sql.gz - | gunzip | \
  docker-compose exec -T db psql -U trashalert trashalert
```

## Troubleshooting

### Container Won't Start

```bash
# Check logs
docker-compose logs api

# Check image
docker images | grep trashalert

# Rebuild
docker-compose up --build
```

### Database Connection Error

```bash
# Check database is running
docker-compose ps db

# Test connection
docker-compose exec db psql -U trashalert -c "SELECT 1"

# Check environment variables
docker-compose config | grep DATABASE_URL
```

### Port Already in Use

```bash
# Change port in docker-compose.yml
services:
  api:
    ports:
      - "8001:8000"  # Changed

# Or kill existing process
lsof -i :8000
kill -9 <PID>
```

### Out of Disk Space

```bash
# Clean up unused images
docker image prune -a

# Clean up volumes
docker volume prune

# Remove old containers
docker container prune
```

## Security Best Practices

1. **Use environment files**
   ```bash
   docker-compose --env-file .env.production up
   ```

2. **Don't store secrets in images**
   - Use Docker secrets
   - Use external secret management

3. **Run as non-root**
   ```dockerfile
   RUN useradd -m appuser
   USER appuser
   ```

4. **Update base images regularly**
   ```bash
   docker pull python:3.11-slim
   docker-compose build --no-cache
   ```

5. **Use health checks**
   ```yaml
   healthcheck:
     test: ["CMD", "curl", "-f", "http://localhost:8000/"]
     interval: 30s
   ```

## Next Steps

- **[Full Setup Guide](/docs/guides/setup)** - Learn about all configuration options
- **[Deployment](/docs/guides/deployment)** - Deploy to production
- **[API Documentation](/docs/api/overview)** - Learn the API

