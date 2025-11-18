---
sidebar_position: 6
title: Production Deployment
slug: /guides/deployment
---

# Production Deployment Guide

Deploy TrashAlert to production with security, reliability, and scalability.

## Pre-Deployment Checklist

- [ ] All tests passing
- [ ] Code reviewed and approved
- [ ] Security audit completed
- [ ] Environment variables configured
- [ ] Database backups configured
- [ ] SSL/TLS certificates ready
- [ ] Monitoring and alerting set up
- [ ] Disaster recovery plan documented

## Deployment Options

### Option 1: Docker on Virtual Machine

Best for small to medium deployments.

```bash
# On deployment server
git clone https://github.com/TombStoneDash/TrashAlert.git
cd TrashAlert

# Create production environment
cp .env.example .env
# Edit .env with production settings

# Build and start
docker-compose -f docker-compose.yml up --build -d

# Verify
curl http://localhost/
```

### Option 2: Kubernetes

Best for large, scalable deployments.

```bash
# Install Kubernetes cluster (AWS EKS, GCP GKE, etc.)
# Then deploy:

kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/secret.yaml
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/database.yaml
kubectl apply -f k8s/api.yaml
kubectl apply -f k8s/ingress.yaml

# Verify
kubectl get pods -n trashalert
```

### Option 3: Heroku, Railway, or Cloud Platforms

Easiest for serverless deployment.

```bash
# Deploy to Heroku
heroku create trashalert-api
git push heroku main

# Deploy to Railway
railway link
railway up
```

## Configuration

### Environment Variables

Create `.env.production`:

```env
# Application
ENVIRONMENT=production
DEBUG=false
API_HOST=0.0.0.0
API_PORT=8000

# Database (use PostgreSQL)
DATABASE_URL=postgresql://user:password@db.example.com/trashalert

# Security
SECRET_KEY=generate_random_secure_key_here
ALLOWED_HOSTS=api.trashalert.com,www.trashalert.com

# Optional: AI services
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=claude-...

# Optional: Monitoring
SENTRY_DSN=https://...
LOG_LEVEL=INFO
```

**Generate SECRET_KEY:**

```python
import secrets
print(secrets.token_urlsafe(32))
```

### Database Setup

Use PostgreSQL in production:

```bash
# Create database on managed PostgreSQL service
# (AWS RDS, Heroku Postgres, Railway, etc.)

# Or on-premises:
sudo apt-get install postgresql postgresql-contrib
sudo -u postgres createdb trashalert
sudo -u postgres createuser trashalert
sudo -u postgres psql -c "ALTER USER trashalert WITH PASSWORD 'secure_password';"
```

**Run migrations:**

```bash
python -m alembic upgrade head
```

### SSL/TLS Certificates

Use Let's Encrypt (free):

```bash
# Install certbot
sudo apt-get install certbot python3-certbot-nginx

# Generate certificate
sudo certbot certonly --standalone -d api.trashalert.com

# Auto-renew
sudo systemctl enable certbot.timer
sudo systemctl start certbot.timer
```

Or use managed certificates from cloud provider.

## Nginx Configuration

```nginx
upstream trashalert_api {
    server 127.0.0.1:8000;
    keepalive 32;
}

server {
    listen 80;
    server_name api.trashalert.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name api.trashalert.com;

    # SSL
    ssl_certificate /etc/letsencrypt/live/api.trashalert.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api.trashalert.com/privkey.pem;

    # Security headers
    add_header Strict-Transport-Security "max-age=31536000" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-Frame-Options "DENY" always;

    # Gzip compression
    gzip on;
    gzip_types text/plain text/css application/json application/javascript;

    # Rate limiting
    limit_req_zone $binary_remote_addr zone=api:10m rate=60r/m;
    limit_req zone=api burst=100 nodelay;

    # Proxy
    location / {
        proxy_pass http://trashalert_api;
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

## Systemd Service

Run TrashAlert as a systemd service:

```ini
# /etc/systemd/system/trashalert.service
[Unit]
Description=TrashAlert API
After=network.target

[Service]
Type=notify
User=trashalert
WorkingDirectory=/home/trashalert/TrashAlert
ExecStart=/home/trashalert/TrashAlert/venv/bin/gunicorn \
    -w 4 \
    -b 127.0.0.1:8000 \
    --timeout 60 \
    app.main:app

Restart=on-failure
RestartSec=5s
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

**Enable and start:**

```bash
sudo systemctl daemon-reload
sudo systemctl enable trashalert
sudo systemctl start trashalert

# Monitor
sudo journalctl -u trashalert -f
```

## Monitoring and Logging

### Structured Logging

TrashAlert logs to JSON for easy parsing:

```json
{
  "timestamp": "2025-11-18T10:30:00Z",
  "level": "INFO",
  "message": "Lookup request: 1122 Palmview Ave",
  "endpoint": "/lookup",
  "response_time_ms": 45.2,
  "status_code": 200
}
```

View logs:

```bash
# Systemd
sudo journalctl -u trashalert -f

# Docker
docker-compose logs -f api

# File
tail -f logs/trashalert.log
```

### Application Monitoring

Integrate with Sentry for error tracking:

```python
# In app configuration
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration

sentry_sdk.init(
    dsn=os.getenv("SENTRY_DSN"),
    integrations=[FastApiIntegration()],
    traces_sample_rate=0.1
)
```

### Metrics Collection

Export Prometheus metrics:

```bash
# Endpoint: http://api.trashalert.com/metrics

# Scrape with Prometheus
curl http://localhost:8000/metrics
```

### Health Checks

Monitor application health:

```bash
# Health check endpoint
curl http://api.trashalert.com/

# Response
{"status":"healthy","service":"TrashAlert API","version":"1.0.0"}
```

## Backup and Recovery

### Database Backups

Automated daily backups:

```bash
#!/bin/bash
# backup-db.sh

BACKUP_DIR="/backups/trashalert"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p $BACKUP_DIR

# PostgreSQL dump
pg_dump -h localhost -U trashalert trashalert | \
    gzip > $BACKUP_DIR/trashalert_$DATE.sql.gz

# Upload to S3
aws s3 cp $BACKUP_DIR/trashalert_$DATE.sql.gz \
    s3://backups/trashalert/

# Keep only 30 days
find $BACKUP_DIR -mtime +30 -delete
```

Schedule with cron:

```bash
# Run daily at 2 AM
0 2 * * * /home/trashalert/backup-db.sh
```

### Disaster Recovery

Restore from backup:

```bash
# Download backup
aws s3 cp s3://backups/trashalert/trashalert_20251118_020000.sql.gz .

# Restore
gunzip < trashalert_20251118_020000.sql.gz | \
    psql -h localhost -U trashalert trashalert
```

## Scaling

### Horizontal Scaling (Multiple Servers)

```bash
# Load balance with round-robin DNS
api1.trashalert.com (10.0.1.10)
api2.trashalert.com (10.0.1.20)
api3.trashalert.com (10.0.1.30)

# Or use load balancer
# AWS ELB, Azure Load Balancer, etc.
```

### Vertical Scaling (More Resources)

Increase resources on single server:
- More CPU cores
- More RAM
- Faster storage

Monitor to decide when to scale:

```bash
# CPU usage
top

# Memory
free -h

# Disk I/O
iostat -x 1

# Network
iftop
```

## Security Hardening

### Web Application Firewall

Use AWS WAF or similar:

```bash
# Block common attacks
- SQL injection
- Cross-site scripting (XSS)
- DDoS attacks
- Rate limiting by IP
```

### HTTPS Only

Redirect HTTP to HTTPS:

```nginx
server {
    listen 80;
    return 301 https://$server_name$request_uri;
}
```

### API Key Validation

Implement optional API keys for public APIs:

```python
from fastapi.security import APIKeyHeader

api_key_header = APIKeyHeader(name="X-API-Key")

@app.get("/lookup")
async def lookup(api_key: str = Depends(api_key_header)):
    # Validate key
    pass
```

### Database Security

```bash
# Use strong passwords
# Encrypt connections
# Restrict access by IP
# Enable audit logging
# Regular backups
```

## CI/CD Pipeline

Automate deployment:

```yaml
# .github/workflows/deploy.yml
name: Deploy

on:
  push:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Run tests
        run: pytest
      - name: Check coverage
        run: pytest --cov=app

  deploy:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Build Docker image
        run: docker build -t trashalert:latest .
      - name: Push to registry
        run: docker push $REGISTRY/trashalert:latest
      - name: Deploy
        run: docker-compose -f prod-compose.yml up -d
```

## Performance Optimization

### Caching

```python
from functools import lru_cache

@lru_cache(maxsize=1000)
def get_cities():
    """Cached query results."""
    return db.query(City).all()
```

### Database Indexing

Ensure critical columns are indexed:

```sql
CREATE INDEX idx_address_city ON addresses(city_id);
CREATE INDEX idx_consensus_verified ON crowd_consensus(is_verified);
```

### Query Optimization

Use connection pooling:

```python
from sqlalchemy.pool import QueuePool

engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=20,
    max_overflow=40
)
```

## Monitoring Checklist

- [ ] Application uptime
- [ ] Response times
- [ ] Error rates
- [ ] Database performance
- [ ] Disk space usage
- [ ] Memory usage
- [ ] CPU usage
- [ ] Network bandwidth

## Rollback Plan

If deployment fails:

```bash
# Check previous version
docker images | grep trashalert

# Rollback to previous version
docker-compose down
docker pull trashalert:1.0.0
docker-compose up -d

# Or with git
git revert HEAD
git push origin main
```

## Support

- **Monitoring**: Set up alerts for key metrics
- **On-call**: Have someone available for emergencies
- **Runbooks**: Document common issues and solutions
- **Status Page**: Keep users informed

---

**Deployment is not the end! Monitor, maintain, and improve continuously.**

