#!/bin/bash
# TrashAlert Production Deployment Script
# This script helps set up and deploy TrashAlert to production

set -e

echo "🚀 TrashAlert Production Deployment"
echo "===================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Functions
print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_info() {
    echo -e "${YELLOW}ℹ $1${NC}"
}

# Check prerequisites
check_prerequisites() {
    print_info "Checking prerequisites..."

    # Check for required tools
    command -v git >/dev/null 2>&1 || { print_error "git is required but not installed."; exit 1; }
    command -v node >/dev/null 2>&1 || { print_error "Node.js is required but not installed."; exit 1; }
    command -v npm >/dev/null 2>&1 || { print_error "npm is required but not installed."; exit 1; }

    print_success "All prerequisites met"
}

# Install CLI tools
install_cli_tools() {
    print_info "Installing Railway and Vercel CLI tools..."

    if ! command -v railway &> /dev/null; then
        npm install -g @railway/cli
        print_success "Railway CLI installed"
    else
        print_success "Railway CLI already installed"
    fi

    if ! command -v vercel &> /dev/null; then
        npm install -g vercel
        print_success "Vercel CLI installed"
    else
        print_success "Vercel CLI already installed"
    fi
}

# Deploy database
deploy_database() {
    print_info "Setting up Railway PostgreSQL database..."
    echo ""
    echo "Please follow these steps:"
    echo "1. Visit https://railway.app"
    echo "2. Create a new project"
    echo "3. Add PostgreSQL database"
    echo "4. Copy the DATABASE_URL"
    echo ""
    read -p "Press enter when ready to continue..."
}

# Deploy API
deploy_api() {
    print_info "Deploying API to Railway..."

    railway login

    echo ""
    print_info "Deploying application..."
    railway up

    echo ""
    print_info "Running database migrations..."
    railway run alembic upgrade head

    print_success "API deployed successfully!"

    echo ""
    API_URL=$(railway domain)
    echo "API URL: https://$API_URL"
}

# Deploy frontend
deploy_frontend() {
    print_info "Deploying Admin Dashboard to Vercel..."

    cd frontend/admin-dashboard

    # Create production environment file
    print_info "Configuring production environment..."
    read -p "Enter your Railway API URL (e.g., https://your-api.railway.app): " API_URL

    cat > .env.production <<EOF
VITE_API_BASE_URL=$API_URL
VITE_DEV_AUTH_BYPASS=false
EOF

    print_success "Environment configured"

    # Install dependencies
    print_info "Installing dependencies..."
    npm ci

    # Deploy to Vercel
    print_info "Deploying to Vercel..."
    vercel --prod

    cd ../..

    print_success "Admin Dashboard deployed successfully!"
}

# Configure GitHub Actions
configure_github_actions() {
    print_info "Configuring GitHub Actions..."
    echo ""
    echo "To enable CI/CD, add these secrets to your GitHub repository:"
    echo ""
    echo "Settings → Secrets and variables → Actions → New repository secret"
    echo ""
    echo "Required secrets:"
    echo "  - RAILWAY_TOKEN (from Railway account settings)"
    echo "  - API_URL (your Railway API URL)"
    echo "  - VERCEL_TOKEN (from Vercel account settings)"
    echo "  - VERCEL_ORG_ID (from Vercel project settings)"
    echo "  - VERCEL_PROJECT_ID (from Vercel project settings)"
    echo "  - FRONTEND_URL (your Vercel dashboard URL)"
    echo "  - SLACK_WEBHOOK_URL (optional, for notifications)"
    echo ""
    read -p "Press enter when done..."
}

# Setup monitoring
setup_monitoring() {
    print_info "Setting up monitoring..."
    echo ""
    echo "Choose a monitoring option:"
    echo "1. GitHub Actions (Free, basic monitoring)"
    echo "2. Better Stack (Recommended, advanced features)"
    echo "3. Uptime Kuma (Self-hosted)"
    echo "4. Skip for now"
    echo ""
    read -p "Enter choice (1-4): " choice

    case $choice in
        1)
            print_success "GitHub Actions monitoring already configured!"
            ;;
        2)
            echo "Visit https://betterstack.com/uptime to set up monitoring"
            echo "Use the configuration in monitoring/betterstack-config.yml as a template"
            read -p "Press enter to continue..."
            ;;
        3)
            echo "Deploy Uptime Kuma to Railway and import monitoring/uptime-kuma-config.json"
            read -p "Press enter to continue..."
            ;;
        4)
            print_info "Skipping monitoring setup"
            ;;
        *)
            print_error "Invalid choice"
            ;;
    esac
}

# Verify deployment
verify_deployment() {
    print_info "Verifying deployment..."
    echo ""

    read -p "Enter your API URL: " API_URL
    read -p "Enter your Frontend URL: " FRONTEND_URL

    echo ""
    print_info "Testing API health..."
    if curl -f -s "$API_URL/health" > /dev/null; then
        print_success "API is healthy!"
    else
        print_error "API health check failed"
    fi

    echo ""
    print_info "Testing Frontend..."
    if curl -f -s "$FRONTEND_URL" > /dev/null; then
        print_success "Frontend is accessible!"
    else
        print_error "Frontend health check failed"
    fi
}

# Main deployment flow
main() {
    echo "This script will guide you through deploying TrashAlert to production."
    echo ""

    # Check prerequisites
    check_prerequisites
    echo ""

    # Install CLI tools
    install_cli_tools
    echo ""

    # Deploy database
    deploy_database
    echo ""

    # Deploy API
    read -p "Deploy API to Railway? (y/n): " deploy_api_choice
    if [[ $deploy_api_choice == "y" ]]; then
        deploy_api
        echo ""
    fi

    # Deploy frontend
    read -p "Deploy Admin Dashboard to Vercel? (y/n): " deploy_frontend_choice
    if [[ $deploy_frontend_choice == "y" ]]; then
        deploy_frontend
        echo ""
    fi

    # Configure GitHub Actions
    read -p "Configure GitHub Actions? (y/n): " github_actions_choice
    if [[ $github_actions_choice == "y" ]]; then
        configure_github_actions
        echo ""
    fi

    # Setup monitoring
    read -p "Set up monitoring? (y/n): " monitoring_choice
    if [[ $monitoring_choice == "y" ]]; then
        setup_monitoring
        echo ""
    fi

    # Verify deployment
    read -p "Verify deployment? (y/n): " verify_choice
    if [[ $verify_choice == "y" ]]; then
        verify_deployment
        echo ""
    fi

    # Success message
    echo ""
    echo "=========================================="
    print_success "Deployment complete!"
    echo "=========================================="
    echo ""
    echo "Next steps:"
    echo "1. Configure custom domain (optional)"
    echo "2. Set up error tracking (Sentry, etc.)"
    echo "3. Configure backup strategy"
    echo "4. Review security settings"
    echo ""
    echo "For detailed documentation, see PRODUCTION_DEPLOYMENT.md"
    echo ""
}

# Run main function
main
