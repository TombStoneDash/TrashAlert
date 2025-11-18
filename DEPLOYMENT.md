# TrashAlert Production Deployment Guide

Complete guide for deploying TrashAlert API to production using Docker Compose with automatic HTTPS.

## 🎯 Overview

This deployment includes:
- **FastAPI application** running with Uvicorn (4 workers)
- **Nginx reverse proxy** with gzip compression and caching
- **Automatic HTTPS** via Let's Encrypt (Certbot)
- **Auto-renewal** of SSL certificates
- **Systemd service** for automatic restart and boot

## 📋 Prerequisites

Before deploying, ensure you have:

- [ ] A server running Linux (Ubuntu 20.04+ or Debian 11+ recommended)
- [ ] Docker Engine 24.0+ installed
- [ ] Docker Compose V2 installed
- [ ] A registered domain name pointing to your server's IP address
- [ ] Ports 80 and 443 open in your firewall
- [ ] At least 1GB RAM and 10GB disk space
- [ ] SSH access to your server

## 🚀 Quick Start

### 1. Clone Repository

```bash
# Clone to /opt/trashalert (recommended) or your preferred location
sudo mkdir -p /opt/trashalert
sudo chown $USER:$USER /opt/trashalert
cd /opt/trashalert

# Clone the repository
git clone https://github.com/yourusername/trashalert.git .
```

### 2. Configure Environment

```bash
# Copy the example environment file
cp .env.production.example .env.production

# Edit with your domain and email
nano .env.production
```

**Required configuration:**
```env
DOMAIN_NAME=trashalert.yourdomain.com
LETSENCRYPT_EMAIL=admin@yourdomain.com
```

### 3. Initialize Database

Make sure your SQLite database is in the `data/` directory:

```bash
# If you need to initialize the database
python init_db.py
```

### 4. Set Up SSL Certificates

```bash
# Run the SSL setup script
./scripts/setup-ssl.sh
```

This script will:
- Create necessary directories
- Start a temporary nginx server
- Request SSL certificate from Let's Encrypt
- Configure nginx with SSL
- Restart all services

### 5. Start Services

```bash
# Start the entire stack
docker compose up -d

# Check status
docker compose ps

# View logs
docker compose logs -f
```

### 6. Set Up Systemd Service (Optional but Recommended)

```bash
# Copy systemd service file
sudo cp trashalert.service /etc/systemd/system/

# Update WorkingDirectory in the service file to match your installation path
sudo nano /etc/systemd/system/trashalert.service

# Reload systemd
sudo systemctl daemon-reload

# Enable service to start on boot
sudo systemctl enable trashalert.service

# Start the service
sudo systemctl start trashalert.service

# Check status
sudo systemctl status trashalert.service
```

## 🔍 Verification

### Test Your Deployment

1. **Health Check**
   ```bash
   curl https://trashalert.yourdomain.com/health
   ```

   Expected response:
   ```json
   {
     "status": "ok",
     "database": "connected",
     "total_addresses": 12345,
     "total_cities": 10
   }
   ```

2. **API Documentation**

   Visit: `https://trashalert.yourdomain.com/docs`

3. **Test Lookup**
   ```bash
   curl "https://trashalert.yourdomain.com/lookup?address=1122%20Palmview%20Ave,%20El%20Centro,%20CA"
   ```

4. **Check SSL Certificate**
   ```bash
   curl -vI https://trashalert.yourdomain.com 2>&1 | grep -i "subject:"
   ```

## 📊 Monitoring

### View Logs

```bash
# All services
docker compose logs -f

# API only
docker compose logs -f api

# Nginx only
docker compose logs -f nginx

# Certbot only
docker compose logs -f certbot
```

### Check Container Status

```bash
# List running containers
docker compose ps

# Check resource usage
docker stats
```

### Systemd Service

```bash
# Status
sudo systemctl status trashalert

# Logs
sudo journalctl -u trashalert -f

# Restart
sudo systemctl restart trashalert
```

## 🔧 Management

### Update Application

```bash
# Pull latest changes
git pull

# Rebuild and restart
docker compose up -d --build

# Or via systemd
sudo systemctl restart trashalert
```

### Restart Services

```bash
# Restart all services
docker compose restart

# Restart specific service
docker compose restart api
docker compose restart nginx
```

### Stop Services

```bash
# Stop all services
docker compose down

# Or via systemd
sudo systemctl stop trashalert
```

### View SSL Certificate Info

```bash
# Check certificate expiry
docker compose exec certbot certbot certificates

# Manual renewal test
docker compose exec certbot certbot renew --dry-run
```

## 🔒 Security Considerations

### Firewall Configuration

```bash
# Allow HTTP and HTTPS
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# Enable firewall
sudo ufw enable
```

### CORS Configuration

By default, the API allows all origins. For production, edit `api/main.py`:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://trashalert.yourdomain.com"],  # Your specific domain
    allow_credentials=True,
    allow_methods=["GET"],
    allow_headers=["*"],
)
```

### Rate Limiting

Nginx is configured with rate limiting:
- API endpoints: 10 requests/second (burst: 10)
- General endpoints: 30 requests/second (burst: 20)

Adjust in `nginx.conf` if needed.

## 📈 Performance Tuning

### Adjust Worker Processes

Edit `.env.production`:

```env
# Recommended: (2 x CPU cores) + 1
UVICORN_WORKERS=4
```

### Nginx Cache

Cache settings in `nginx/conf.d/trashalert.conf`:
- GET requests: cached for 5 minutes
- 404 responses: cached for 1 minute
- Cache size: 100MB

### Database Optimization

For SQLite in production:
- Ensure database is on SSD storage
- Regular VACUUM operations
- Consider connection pooling for high traffic

## 🐛 Troubleshooting

### SSL Certificate Issues

```bash
# Check certificate status
docker compose exec certbot certbot certificates

# Force renewal
docker compose exec certbot certbot renew --force-renewal

# Check nginx SSL config
docker compose exec nginx nginx -t
```

### API Not Responding

```bash
# Check API health
docker compose exec api curl http://localhost:8000/health

# Check API logs
docker compose logs api --tail=100

# Restart API
docker compose restart api
```

### Database Connection Issues

```bash
# Check if database file exists
ls -lh data/trashalert.db

# Check permissions
docker compose exec api ls -lh /app/data/

# Check database stats via API
curl https://trashalert.yourdomain.com/health
```

### Nginx Issues

```bash
# Test nginx config
docker compose exec nginx nginx -t

# Reload nginx
docker compose exec nginx nginx -s reload

# Check nginx logs
docker compose logs nginx --tail=100
```

### High Memory Usage

```bash
# Check container stats
docker stats

# Reduce workers in .env.production
UVICORN_WORKERS=2

# Restart services
docker compose up -d --force-recreate
```

## 🔄 Backup and Restore

### Backup Database

```bash
# Create backup
cp data/trashalert.db data/trashalert.db.backup.$(date +%Y%m%d)

# Or use sqlite3
sqlite3 data/trashalert.db ".backup data/trashalert.db.backup"
```

### Backup SSL Certificates

```bash
# Backup certificates
tar -czf certbot-backup-$(date +%Y%m%d).tar.gz certbot/
```

### Restore

```bash
# Restore database
cp data/trashalert.db.backup.20240101 data/trashalert.db

# Restart services
docker compose restart api
```

## 📁 Directory Structure

```
/opt/trashalert/
├── api/                    # API source code
├── app/                    # Legacy app code
├── data/                   # SQLite database
│   └── trashalert.db
├── nginx/                  # Nginx configuration
│   └── conf.d/
│       └── trashalert.conf
├── certbot/               # SSL certificates (auto-created)
│   ├── conf/
│   └── www/
├── scripts/               # Deployment scripts
│   └── setup-ssl.sh
├── Dockerfile             # Application container
├── docker-compose.yml     # Service orchestration
├── nginx.conf            # Main nginx config
├── trashalert.service    # Systemd service
├── .env.production       # Production environment (create from .env.production.example)
└── DEPLOYMENT.md         # This file
```

## 🆘 Support

For issues or questions:
1. Check the logs: `docker compose logs -f`
2. Review this guide's troubleshooting section
3. Open an issue on GitHub
4. Check Docker and nginx documentation

## 📝 Maintenance Checklist

### Daily
- [ ] Monitor logs for errors: `docker compose logs --tail=100`
- [ ] Check service health: `curl https://yourdomain.com/health`

### Weekly
- [ ] Review disk space: `df -h`
- [ ] Check SSL certificate expiry: `docker compose exec certbot certbot certificates`
- [ ] Review nginx logs for unusual traffic

### Monthly
- [ ] Update Docker images: `docker compose pull && docker compose up -d`
- [ ] Backup database: `cp data/trashalert.db data/trashalert.db.backup.$(date +%Y%m%d)`
- [ ] Review and rotate logs
- [ ] Update system packages: `sudo apt update && sudo apt upgrade`

## 🎉 Success Criteria

Your deployment is successful when:
- ✅ API responds at `https://trashalert.yourdomain.com/health`
- ✅ SSL certificate is valid (green lock in browser)
- ✅ API documentation accessible at `https://trashalert.yourdomain.com/docs`
- ✅ Lookup queries return results
- ✅ All containers are running: `docker compose ps`
- ✅ Systemd service is active: `systemctl status trashalert`
- ✅ Auto-renewal is working: `docker compose logs certbot`

---

**Need help?** Open an issue or check the main [README.md](README.md) for more information.
