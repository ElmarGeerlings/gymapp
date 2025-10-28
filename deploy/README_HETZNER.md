# Hetzner Deployment Guide

## Overview
This directory contains configuration files for deploying the Gainz Django application on Hetzner Cloud.

## Files
- `systemd/gainz.service` - Gunicorn service for Django app
- `systemd/gainz-rq.service` - RQ worker service for background tasks
- `caddy/Caddyfile` - Caddy web server configuration

## Deployment Steps

### 1. Copy service files to systemd
```bash
sudo cp deploy/systemd/gainz.service /etc/systemd/system/
sudo cp deploy/systemd/gainz-rq.service /etc/systemd/system/
```

### 2. Copy Caddy configuration
```bash
sudo cp deploy/caddy/Caddyfile /etc/caddy/Caddyfile
```

### 3. Enable and start services
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now gainz gainz-rq
sudo systemctl reload caddy
```

### 4. Create admin user
```bash
sudo -u gainz bash -lc 'cd /srv/gainz/app && . venv/bin/activate && python manage.py createsuperuser'
```

### 5. Verify deployment
```bash
sudo systemctl status gainz gainz-rq caddy
curl -I https://91.98.229.71
```

## Configuration Notes

- **Domain**: Currently configured for IP address `91.98.229.71`
- **SSL**: Caddy automatically handles HTTPS certificates
- **Static files**: Served directly by Caddy from `/srv/gainz/staticfiles`
- **Media files**: Served by Caddy from `/srv/gainz/mediafiles`
- **Django app**: Runs via Gunicorn with Unix socket

## Security
- Services run as `gainz` user (not root)
- Environment variables loaded from `/srv/gainz/gainz.env`
- File permissions set to restrict access

## Monitoring
Check logs with:
```bash
sudo journalctl -u gainz -f
sudo journalctl -u gainz-rq -f
sudo journalctl -u caddy -f
```