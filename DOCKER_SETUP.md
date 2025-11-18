# TrashAlert - Docker Setup Guide

Complete Dockerized environment for TrashAlert with API, Worker, Redis, PostgreSQL, and Nginx.

## 📦 What's Included

### Services
- **API**: FastAPI application (Python 3.11)
- **Worker**: Background task processor
- **PostgreSQL**: Primary database (PostgreSQL 16)
- **Redis**: Cache and task queue (Redis 7)
- **Nginx**: Reverse proxy and load balancer
- **Certbot**: Automatic SSL certificate management

### Features
✅ Multi-stage Docker builds for fast deploys
✅ Health checks for all services
✅ Local development vs production modes
✅ Automatic database initialization
✅ Volume persistence for data and logs
✅ Non-root user for security
✅ BuildKit caching for faster builds

## 🚀 Quick Start

### 1. Prerequisites
- Docker Engine 20.10+ or Docker Desktop
- Docker Compose 2.0+
- 4GB+ RAM available

### 2. Environment Setup

**For Local Development:**
```bash
# Copy the example environment file
cp .env.example .env

# Edit .env and adjust settings as needed
nano .env
```

**For Production:**
```bash
# Copy the production example
cp .env.production.example .env

# IMPORTANT: Update all passwords and credentials!
nano .env
```

### 3. Start the Stack

**Development Mode:**
```bash
# Start all services
docker compose -f docker-compose.yaml up -d

# View logs
docker compose -f docker-compose.yaml logs -f

# Stop services
docker compose -f docker-compose.yaml down
```

**Production Mode:**
```bash
# Build and start all services
docker compose -f docker-compose.yaml up -d --build

# View logs
docker compose -f docker-compose.yaml logs -f api worker

# Stop services (keeps data)
docker compose -f docker-compose.yaml down

# Stop and remove volumes (WARNING: deletes all data!)
docker compose -f docker-compose.yaml down -v
```

## 📋 Service Details

### API Service
- **Port**: 8000 (internal only, proxied via Nginx)
- **Health Check**: `GET /health`
- **Workers**: Configurable via `UVICORN_WORKERS` env var
- **Dockerfile**: `Dockerfile.api`

### Worker Service
- **Purpose**: Background tasks and data pipeline processing
- **Command**: Customizable via docker-compose override
- **Dockerfile**: `Dockerfile.worker`

### PostgreSQL
- **Port**: 5432 (exposed only in development)
- **Database**: `trashalert` (configurable)
- **User**: `trashalert` (configurable)
- **Persistent**: Volume `postgres-data`

### Redis
- **Port**: 6379 (exposed only in development)
- **Max Memory**: 256MB (configurable)
- **Eviction Policy**: `allkeys-lru`
- **Persistent**: Volume `redis-data` with AOF

### Nginx
- **Ports**: 80 (HTTP), 443 (HTTPS)
- **Caching**: Enabled via volume `nginx-cache`
- **SSL**: Automatic via Let's Encrypt (Certbot)

## 🔧 Configuration

### Environment Variables

#### Application
```bash
ENVIRONMENT=development          # development, staging, production
LOG_LEVEL=info                   # debug, info, warning, error, critical
```

#### PostgreSQL
```bash
POSTGRES_DB=trashalert
POSTGRES_USER=trashalert
POSTGRES_PASSWORD=your_secure_password
POSTGRES_PORT=5432
```

#### Redis
```bash
REDIS_PASSWORD=your_secure_password
REDIS_PORT=6379
REDIS_MAXMEMORY=256mb
```

#### API/Uvicorn
```bash
UVICORN_WORKERS=4                # (2 × CPU cores) + 1
```

#### Nginx
```bash
HTTP_PORT=80
HTTPS_PORT=443
NGINX_WORKER_PROCESSES=auto
NGINX_WORKER_CONNECTIONS=1024
```

### Development Mode Features

Enable code hot-reloading by setting:
```bash
DEV_CODE_MOUNT=./app
```

This mounts your local `./app` directory into the containers, allowing changes without rebuilds.

## 🏗️ Building Images

### Build Specific Services
```bash
# Build API only
docker compose -f docker-compose.yaml build api

# Build worker only
docker compose -f docker-compose.yaml build worker

# Build all services
docker compose -f docker-compose.yaml build
```

### Build with No Cache
```bash
docker compose -f docker-compose.yaml build --no-cache
```

### Tag for Registry
```bash
# Set image tag in .env
IMAGE_TAG=v1.0.0

# Build with tag
docker compose -f docker-compose.yaml build

# Push to registry
docker push trashalert-api:v1.0.0
docker push trashalert-worker:v1.0.0
```

## 🔍 Troubleshooting

### View Service Status
```bash
docker compose -f docker-compose.yaml ps
```

### View Logs
```bash
# All services
docker compose -f docker-compose.yaml logs -f

# Specific service
docker compose -f docker-compose.yaml logs -f api

# Last 100 lines
docker compose -f docker-compose.yaml logs --tail=100 api
```

### Restart Service
```bash
docker compose -f docker-compose.yaml restart api
```

### Execute Commands in Container
```bash
# Open shell in API container
docker compose -f docker-compose.yaml exec api bash

# Run Python script
docker compose -f docker-compose.yaml exec api python init_db.py

# Run database migrations
docker compose -f docker-compose.yaml exec api alembic upgrade head
```

### Database Access
```bash
# Connect to PostgreSQL
docker compose -f docker-compose.yaml exec postgres psql -U trashalert -d trashalert

# Connect to Redis
docker compose -f docker-compose.yaml exec redis redis-cli -a your_password
```

### Health Checks
```bash
# Check API health
curl http://localhost/health

# Check all container health
docker compose -f docker-compose.yaml ps
```

### Common Issues

**1. Port Already in Use**
```bash
# Change ports in .env
HTTP_PORT=8080
HTTPS_PORT=8443
```

**2. Permission Denied**
```bash
# Fix data directory permissions
sudo chown -R 1000:1000 data logs
```

**3. Database Connection Failed**
```bash
# Wait for postgres to be ready
docker compose -f docker-compose.yaml logs postgres

# Check if postgres is healthy
docker compose -f docker-compose.yaml ps postgres
```

**4. Out of Disk Space**
```bash
# Clean up unused Docker resources
docker system prune -a --volumes

# Remove old images
docker image prune -a
```

## 🧪 Testing

### Run Tests in Container
```bash
# Run all tests
docker compose -f docker-compose.yaml exec api pytest

# Run with coverage
docker compose -f docker-compose.yaml exec api pytest --cov=app

# Run specific test file
docker compose -f docker-compose.yaml exec api pytest tests/test_main.py
```

## 🚢 Production Deployment

### Pre-Deployment Checklist
- [ ] Update all passwords in `.env`
- [ ] Set `ENVIRONMENT=production`
- [ ] Configure domain name for SSL
- [ ] Set appropriate `UVICORN_WORKERS` based on CPU
- [ ] Review and adjust `REDIS_MAXMEMORY`
- [ ] Set `DEV_CODE_MOUNT=` (empty)
- [ ] Configure backup strategy for volumes

### SSL Certificate Setup
```bash
# Initial certificate request
docker compose -f docker-compose.yaml exec certbot certbot certonly \
  --webroot \
  --webroot-path=/var/www/certbot \
  --email your@email.com \
  --agree-tos \
  --no-eff-email \
  -d yourdomain.com

# Auto-renewal is configured via certbot service
```

### Scaling Services
```bash
# Scale worker service to 3 instances
docker compose -f docker-compose.yaml up -d --scale worker=3

# Scale API (requires load balancer configuration)
docker compose -f docker-compose.yaml up -d --scale api=2
```

### Monitoring
```bash
# Resource usage
docker stats

# Container logs with timestamps
docker compose -f docker-compose.yaml logs -f --timestamps

# Follow specific service
docker compose -f docker-compose.yaml logs -f api
```

## 📊 Data Persistence

### Backup Volumes
```bash
# Backup PostgreSQL
docker compose -f docker-compose.yaml exec postgres pg_dump -U trashalert trashalert > backup.sql

# Backup Redis
docker compose -f docker-compose.yaml exec redis redis-cli -a your_password BGSAVE

# Copy volume data
docker run --rm -v trashalert_postgres-data:/data -v $(pwd):/backup alpine tar czf /backup/postgres-backup.tar.gz -C /data .
```

### Restore Volumes
```bash
# Restore PostgreSQL
docker compose -f docker-compose.yaml exec -T postgres psql -U trashalert trashalert < backup.sql

# Restore volume data
docker run --rm -v trashalert_postgres-data:/data -v $(pwd):/backup alpine tar xzf /backup/postgres-backup.tar.gz -C /data
```

## 🔐 Security Best Practices

1. **Change Default Passwords**: Never use default passwords in production
2. **Use Secrets**: Consider Docker secrets or external secret management
3. **Limit Port Exposure**: Don't expose database ports in production
4. **Regular Updates**: Keep base images and dependencies updated
5. **Non-Root User**: All services run as non-root (UID 1000)
6. **Network Isolation**: Services communicate via internal network only

## 📚 Additional Resources

- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [FastAPI Deployment](https://fastapi.tiangolo.com/deployment/)
- [PostgreSQL Docker](https://hub.docker.com/_/postgres)
- [Redis Docker](https://hub.docker.com/_/redis)
- [Nginx Docker](https://hub.docker.com/_/nginx)

## 🤝 Support

For issues or questions:
1. Check logs: `docker compose logs -f`
2. Verify health: `docker compose ps`
3. Review configuration: `docker compose config`
4. Consult this guide's troubleshooting section

---

**Built with ❤️ for TrashAlert**
