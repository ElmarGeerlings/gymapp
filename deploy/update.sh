#!/bin/bash

# Deployment script for Hetzner server
# Run this on your Hetzner server to update the website

set -e  # Exit on error

echo "🚀 Updating Gainz app on Hetzner..."

# Navigate to project directory
cd /srv/gainz/app

# Activate virtual environment
source venv/bin/activate

# Pull latest changes from git
echo "📥 Pulling latest changes from git..."
git pull origin master

# Install/update dependencies
echo "📦 Installing/updating dependencies..."
pip install -r requirements.txt --quiet

# Run database migrations
echo "🗄️  Running database migrations..."
python manage.py migrate --noinput

# Collect static files
echo "📁 Collecting static files..."
python manage.py collectstatic --noinput

# Restart Gunicorn service
echo "🔄 Restarting Gunicorn service..."
sudo systemctl restart gainz

# Check service status
echo "✅ Checking service status..."
sudo systemctl status gainz --no-pager -l

echo "✨ Deployment complete! Your site should be updated."

