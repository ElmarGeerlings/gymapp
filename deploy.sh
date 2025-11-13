#!/bin/bash

# Deploy script for Gainz app
# Usage: ./deploy.sh

echo "🚀 Deploying Gainz to Hetzner..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
SERVER="root@91.98.229.71"
APP_DIR="/srv/gainz/app"

echo -e "${YELLOW}Connecting to server...${NC}"

# SSH and run deployment commands
ssh -o StrictHostKeyChecking=no $SERVER << EOF
    echo -e "${GREEN}Connected to server${NC}"

    # Pull latest changes
    echo -e "${YELLOW}Pulling latest code...${NC}"
    sudo -u gainz bash -lc "cd $APP_DIR && git pull origin master"

    # Install/update dependencies
    echo -e "${YELLOW}Installing/updating dependencies...${NC}"
    sudo -u gainz bash -lc "cd $APP_DIR && source venv/bin/activate && pip install -r requirements.txt --quiet"

    # Run database migrations
    echo -e "${YELLOW}Running database migrations...${NC}"
    sudo -u gainz bash -lc "cd $APP_DIR && source venv/bin/activate && python manage.py migrate --noinput"

    # Collect static files
    echo -e "${YELLOW}Collecting static files...${NC}"
    sudo -u gainz bash -lc "cd $APP_DIR && source venv/bin/activate && python manage.py collectstatic --noinput"

    # Restart services
    echo -e "${YELLOW}Restarting services...${NC}"
    sudo systemctl restart gainz
    sudo systemctl reload caddy

    # Check status
    echo -e "${YELLOW}Checking service status...${NC}"
    sudo systemctl status gainz --no-pager -l
    sudo systemctl status caddy --no-pager -l

    echo -e "${GREEN}✅ Deployment complete!${NC}"
    echo -e "${GREEN}Your site: https://91.98.229.71${NC}"
EOF

echo -e "${GREEN}🎉 Local deployment script finished!${NC}"

