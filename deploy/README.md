# Project Mushroom Cloud — Deployment Guide

## Quick Start (Local Development)
```bash
cd /path/to/project-mushroom-cloud
# Start all services (PostgreSQL + FastAPI + Next.js)
docker compose up
# Or run individually:
# Backend: pip install -r requirements.txt && uvicorn api.main:app --reload --port 8000
# Frontend: cd frontend && npm install && npm run dev
```

## Production Deployment

### 1. Systemd Services (Linux — without Docker)

Copy service files and enable them:
```bash
# FastAPI backend
sudo cp deploy/mushroom-api.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now mushroom-api
sudo systemctl status mushroom-api

# Next.js frontend
sudo cp deploy/mushroom-frontend.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now mushroom-frontend
sudo systemctl status mushroom-frontend
```

### 2. Docker Compose (Production)
```bash
# Set environment variables in .env or export them
export DB_PASSWORD=your_secure_password
export CLERK_SECRET_KEY=your_clerk_key
export NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=your_clerk_pub_key
export CORS_ORIGINS=https://yourdomain.com

docker compose -f docker-compose.prod.yml up -d
```

### 3. Secure Access (HTTPS)
Choose **one** of these approaches:

- **Cloudflare Tunnel** (recommended for zero-config HTTPS): See `cloudflare-tunnel-setup.sh`
- **Tailscale** (recommended for private access between machines): See `tailscale-setup.sh`
- Both can be combined: Cloudflare for external HTTPS, Tailscale for private mesh.

### 4. Automated Backups
Configure and run `backup.sh`:
```bash
# Edit deploy/backup.sh to set your Dropbox and B2 paths
chmod +x deploy/backup.sh
# Test manually first
./deploy/backup.sh
# Then add to cron (daily at 2 AM)
sudo cp deploy/mushroom-backup.timer /etc/systemd/system/
sudo cp deploy/mushroom-backup.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now mushroom-backup.timer
```

### 5. Health Check
The API exposes a health check at `/api/v1/health` that reports:
- Database connectivity and latency
- LLM provider availability (API keys configured)
- Disk space on data partition
- Data directory write status
