#!/bin/bash
# TrashAlert Quick Deployment Script
# This script performs initial deployment setup

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}TrashAlert Production Deployment${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Check if running as root
if [ "$EUID" -eq 0 ]; then
    echo -e "${YELLOW}Warning: Running as root. Consider using a regular user with docker permissions.${NC}"
fi

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo -e "${RED}Error: Docker is not installed${NC}"
    echo "Please install Docker: https://docs.docker.com/engine/install/"
    exit 1
fi

# Check if Docker Compose is installed
if ! docker compose version &> /dev/null; then
    echo -e "${RED}Error: Docker Compose V2 is not installed${NC}"
    echo "Please install Docker Compose V2: https://docs.docker.com/compose/install/"
    exit 1
fi

echo -e "${GREEN}✓ Docker and Docker Compose are installed${NC}"

# Check for .env.production
if [ ! -f .env.production ]; then
    echo -e "${YELLOW}Creating .env.production from example...${NC}"
    cp .env.production.example .env.production
    echo -e "${RED}Please edit .env.production with your domain and email:${NC}"
    echo -e "  nano .env.production"
    echo -e ""
    echo -e "${YELLOW}Required fields:${NC}"
    echo -e "  - DOMAIN_NAME"
    echo -e "  - LETSENCRYPT_EMAIL"
    exit 1
fi

# Load environment
source .env.production

# Validate required environment variables
if [ -z "$DOMAIN_NAME" ]; then
    echo -e "${RED}Error: DOMAIN_NAME not set in .env.production${NC}"
    exit 1
fi

if [ -z "$LETSENCRYPT_EMAIL" ]; then
    echo -e "${RED}Error: LETSENCRYPT_EMAIL not set in .env.production${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Environment configuration loaded${NC}"
echo -e "  Domain: ${YELLOW}$DOMAIN_NAME${NC}"
echo -e "  Email: ${YELLOW}$LETSENCRYPT_EMAIL${NC}"
echo ""

# Check database
if [ ! -f data/trashalert.db ]; then
    echo -e "${YELLOW}Warning: Database not found at data/trashalert.db${NC}"
    echo -e "Make sure to initialize the database before starting"
fi

# Create required directories
echo -e "${GREEN}Creating required directories...${NC}"
mkdir -p data
mkdir -p certbot/conf
mkdir -p certbot/www
mkdir -p nginx/conf.d

echo -e "${GREEN}✓ Directories created${NC}"

# Substitute environment variables in nginx config
echo -e "${GREEN}Configuring nginx...${NC}"
if [ -f nginx/conf.d/trashalert.conf ]; then
    envsubst '${DOMAIN_NAME}' < nginx/conf.d/trashalert.conf > nginx/conf.d/trashalert.conf.tmp
    mv nginx/conf.d/trashalert.conf.tmp nginx/conf.d/trashalert.conf
fi

echo -e "${GREEN}✓ Nginx configured${NC}"

# Ask user if they want to set up SSL now
echo ""
read -p "Do you want to set up SSL certificates now? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${GREEN}Running SSL setup...${NC}"
    ./scripts/setup-ssl.sh
else
    echo -e "${YELLOW}Skipping SSL setup${NC}"
    echo -e "${YELLOW}You can run it later with: ./scripts/setup-ssl.sh${NC}"
    echo ""
    echo -e "${GREEN}Starting services without SSL...${NC}"

    # Create temporary HTTP-only nginx config
    cat > nginx/conf.d/trashalert-http.conf << EOF
server {
    listen 80;
    listen [::]:80;
    server_name $DOMAIN_NAME;

    location / {
        proxy_pass http://api:8000;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOF

    # Remove SSL config if exists
    rm -f nginx/conf.d/trashalert.conf

    docker compose up -d
fi

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Deployment Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "Check status: ${YELLOW}docker compose ps${NC}"
echo -e "View logs: ${YELLOW}docker compose logs -f${NC}"
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo -e "Your API is available at: ${YELLOW}https://$DOMAIN_NAME${NC}"
else
    echo -e "Your API is available at: ${YELLOW}http://$DOMAIN_NAME${NC}"
fi
echo -e "API docs: ${YELLOW}https://$DOMAIN_NAME/docs${NC}"
echo -e "Health check: ${YELLOW}https://$DOMAIN_NAME/health${NC}"
echo ""
