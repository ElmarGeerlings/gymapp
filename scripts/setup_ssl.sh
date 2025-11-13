#!/bin/bash

# SSL Setup Script for elgainz.com on Hetzner
# This script sets up Let's Encrypt SSL certificate and configures nginx

DOMAIN="elgainz.com"
NGINX_CONFIG="/etc/nginx/sites-available/${DOMAIN}.conf"
NGINX_ENABLED="/etc/nginx/sites-enabled/${DOMAIN}.conf"
STATIC_ROOT="/path/to/your/project/staticfiles"

echo "🔒 Setting up SSL for ${DOMAIN}..."

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo "❌ Please run as root (use sudo)"
    exit 1
fi

# Update system packages
echo "📦 Updating system packages..."
apt update
apt upgrade -y

# Install nginx if not installed
if ! command -v nginx &> /dev/null; then
    echo "📦 Installing nginx..."
    apt install nginx -y
fi

# Install certbot
if ! command -v certbot &> /dev/null; then
    echo "📦 Installing certbot..."
    apt install certbot python3-certbot-nginx -y
fi

# Copy nginx config (you'll need to update the static root path)
echo "📝 Setting up nginx configuration..."
if [ -f "nginx/${DOMAIN}.conf" ]; then
    # Update static root path in config
    sed "s|/path/to/your/project/staticfiles|${STATIC_ROOT}|g" "nginx/${DOMAIN}.conf" > "${NGINX_CONFIG}"
    echo "✅ Nginx config created at ${NGINX_CONFIG}"
    echo "⚠️  Please update the static root path in ${NGINX_CONFIG} if needed"
else
    echo "⚠️  nginx/${DOMAIN}.conf not found. Creating basic config..."
    cat > "${NGINX_CONFIG}" << EOF
server {
    listen 80;
    server_name ${DOMAIN} www.${DOMAIN};
    return 301 https://\$server_name\$request_uri;
}

server {
    listen 443 ssl http2;
    server_name ${DOMAIN} www.${DOMAIN};
    
    ssl_certificate /etc/letsencrypt/live/${DOMAIN}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/${DOMAIN}/privkey.pem;
    
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
    
    location /static/ {
        alias ${STATIC_ROOT}/;
    }
}
EOF
fi

# Enable the site
if [ ! -L "${NGINX_ENABLED}" ]; then
    ln -s "${NGINX_CONFIG}" "${NGINX_ENABLED}"
    echo "✅ Nginx site enabled"
fi

# Test nginx configuration
echo "🧪 Testing nginx configuration..."
nginx -t

if [ $? -ne 0 ]; then
    echo "❌ Nginx configuration test failed. Please fix errors above."
    exit 1
fi

# Restart nginx
systemctl restart nginx
echo "✅ Nginx restarted"

# Get SSL certificate
echo "🔐 Obtaining SSL certificate from Let's Encrypt..."
certbot --nginx -d ${DOMAIN} -d www.${DOMAIN} --non-interactive --agree-tos --email your-email@example.com

if [ $? -eq 0 ]; then
    echo "✅ SSL certificate installed successfully!"
    echo "🌐 Your site should now be accessible at https://${DOMAIN}"
    
    # Set up auto-renewal
    echo "🔄 Setting up automatic certificate renewal..."
    systemctl enable certbot.timer
    systemctl start certbot.timer
    
    echo "✅ SSL setup complete!"
else
    echo "❌ SSL certificate installation failed."
    echo "⚠️  Make sure:"
    echo "   1. DNS is pointing to this server (A record for ${DOMAIN} and www.${DOMAIN})"
    echo "   2. Port 80 and 443 are open in firewall"
    echo "   3. Nginx is running and accessible"
    exit 1
fi

