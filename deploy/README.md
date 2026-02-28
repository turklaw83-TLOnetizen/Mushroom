# TLO AllRise — Deployment Guide

## Quick Start (Local Development)
```bash
cd /path/to/tlo-allrise-rebuild
pip install -r requirements.txt
streamlit run app.py
```

## Production Deployment

### 1. Systemd Service (Linux)
Copy `tlo-allrise.service` to `/etc/systemd/system/` and enable:
```bash
sudo cp deploy/tlo-allrise.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now tlo-allrise
sudo systemctl status tlo-allrise
```

### 2. Secure Access (HTTPS)
Choose **one** of these approaches:

- **Cloudflare Tunnel** (recommended for zero-config HTTPS): See `cloudflare-tunnel-setup.sh`
- **Tailscale** (recommended for private access between machines): See `tailscale-setup.sh`
- Both can be combined: Cloudflare for external HTTPS, Tailscale for private mesh.

### 3. Automated Backups
Configure and run `backup.sh`:
```bash
# Edit deploy/backup.sh to set your Dropbox and B2 paths
chmod +x deploy/backup.sh
# Test manually first
./deploy/backup.sh
# Then add to cron (daily at 2 AM)
sudo cp deploy/tlo-allrise-backup.timer /etc/systemd/system/
sudo cp deploy/tlo-allrise-backup.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now tlo-allrise-backup.timer
```

### 4. Windows Deployment
See `windows-task-scheduler.xml` for Task Scheduler import, or run:
```powershell
python -m streamlit run app.py --server.port 8501
```
