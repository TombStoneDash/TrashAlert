#!/bin/bash
# TrashAlert SSL Certificate Setup Script
# This script initializes Let's Encrypt SSL certificates using Certbot

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Load environment variables
if [ ! -f .env.production ]; then
    echo -e "${RED}Error: .env.production file not found${NC}"
    echo "Please copy .env.production.example to .env.production and configure it"
    exit 1
fi

source .env.production

# Check required variables
if [ -z "$DOMAIN_NAME" ]; then
    echo -e "${RED}Error: DOMAIN_NAME not set in .env.production${NC}"
    exit 1
fi

if [ -z "$LETSENCRYPT_EMAIL" ]; then
    echo -e "${RED}Error: LETSENCRYPT_EMAIL not set in .env.production${NC}"
    exit 1
fi

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}TrashAlert SSL Certificate Setup${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "Domain: ${YELLOW}$DOMAIN_NAME${NC}"
echo -e "Email: ${YELLOW}$LETSENCRYPT_EMAIL${NC}"
echo ""

# Create required directories
echo -e "${GREEN}Creating SSL directories...${NC}"
mkdir -p certbot/conf
mkdir -p certbot/www

# Check if certificate already exists
if [ -d "certbot/conf/live/$DOMAIN_NAME" ]; then
    echo -e "${YELLOW}Certificate already exists for $DOMAIN_NAME${NC}"
    read -p "Do you want to renew it? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${GREEN}Skipping certificate renewal${NC}"
        exit 0
    fi
    RENEW_FLAG="--force-renewal"
else
    RENEW_FLAG=""
fi

# Create temporary nginx config for ACME challenge
echo -e "${GREEN}Creating temporary nginx configuration...${NC}"
cat > nginx/conf.d/temp-acme.conf << EOF
server {
    listen 80;
    listen [::]:80;
    server_name $DOMAIN_NAME;

    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    location / {
        return 200 'TrashAlert SSL setup in progress...';
        add_header Content-Type text/plain;
    }
}
EOF

# Start nginx temporarily for ACME challenge
echo -e "${GREEN}Starting nginx for ACME challenge...${NC}"
docker compose up -d nginx

# Wait for nginx to be ready
echo -e "${GREEN}Waiting for nginx to be ready...${NC}"
sleep 5

# Request certificate
echo -e "${GREEN}Requesting SSL certificate...${NC}"
docker compose run --rm certbot certonly \
    --webroot \
    --webroot-path=/var/www/certbot \
    --email "$LETSENCRYPT_EMAIL" \
    --agree-tos \
    --no-eff-email \
    $RENEW_FLAG \
    -d "$DOMAIN_NAME"

# Check if certificate was created
if [ ! -d "certbot/conf/live/$DOMAIN_NAME" ]; then
    echo -e "${RED}Error: Certificate creation failed${NC}"
    docker compose down
    exit 1
fi

echo -e "${GREEN}Certificate created successfully!${NC}"

# Remove temporary nginx config
echo -e "${GREEN}Removing temporary configuration...${NC}"
rm -f nginx/conf.d/temp-acme.conf

# Replace DOMAIN_NAME placeholder in nginx config
echo -e "${GREEN}Configuring nginx with SSL...${NC}"
envsubst '${DOMAIN_NAME}' < nginx/conf.d/trashalert.conf > nginx/conf.d/trashalert.conf.tmp
mv nginx/conf.d/trashalert.conf.tmp nginx/conf.d/trashalert.conf

# Restart stack with SSL
echo -e "${GREEN}Restarting services with SSL...${NC}"
docker compose down
docker compose up -d

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}SSL Setup Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "Your site is now available at: ${YELLOW}https://$DOMAIN_NAME${NC}"
echo ""
echo -e "Certificate will auto-renew every 12 hours via the certbot service"
echo ""
