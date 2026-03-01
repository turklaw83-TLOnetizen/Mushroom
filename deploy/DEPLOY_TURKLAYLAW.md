# Deploying Project Mushroom Cloud for Turklay Law

**Target**: `app.turklaylaw.com`
**Authorized user**: daniel@turklaylaw.com (Google OAuth + SMS MFA)

---

## Prerequisites

You need:
- A Linux VPS (Ubuntu 22.04+ recommended) with Docker + Docker Compose
  - **Recommended**: 4 vCPUs, 8 GB RAM, 100 GB SSD
  - Providers: DigitalOcean, Hetzner, Linode, or AWS Lightsail (~$24-48/mo)
- DNS access to turklaylaw.com (to create an A record for `app.turklaylaw.com`)
- A Clerk account (free tier is fine for single user)
- An Anthropic API key (for Claude analysis engine)

---

## Step 1: Create a Clerk Application

1. Go to **https://dashboard.clerk.com** and sign up / sign in
2. Click **"Create application"**
   - Name: `Mushroom Cloud` (or `Turklay Law`)
   - Select **Google** as the social login provider (uncheck email/password if you want Google-only)
3. You're now in the Clerk Dashboard for your app

### Configure Authentication

4. **API Keys** (left sidebar):
   - Copy the **Publishable key** (`pk_live_...`) — you'll need this for `.env`
   - Copy the **Secret key** (`sk_live_...`) — you'll need this for `.env`
   - The **JWKS URL** is shown under "Advanced" or can be constructed:
     `https://<your-instance>.clerk.accounts.dev/.well-known/jwks.json`
     (your instance ID is in the URL when viewing the dashboard)

5. **User & Authentication > Email, Phone, Username** (left sidebar):
   - Enable **Email address** (required)
   - Enable **Phone number** (for MFA)
   - Disable **Username** (not needed)

6. **User & Authentication > Social Connections**:
   - Enable **Google** (should already be enabled from step 2)
   - Under Google settings, select "Use Clerk development credentials" for testing,
     or add your own Google OAuth credentials for production branding

7. **User & Authentication > Multi-factor**:
   - Enable **SMS code**
   - This allows users to add their phone number for 2FA after signing in

8. **User & Authentication > Restrictions**:
   - Set Sign-up mode to **"Restricted"**
   - Under **Allowlist**, add: `daniel@turklaylaw.com`
   - This ensures NO ONE else can create an account

9. **Create your user account**:
   - Go to **Users** in the left sidebar
   - Click **"Create user"** (or sign in via your app's sign-in page once deployed)
   - Email: `daniel@turklaylaw.com`
   - After creation, go to the user's profile and:
     - Set the **role** in public metadata: `{"role": "admin"}`
     - Add phone number: `+16158385903` for MFA

---

## Step 2: Provision Your Server

### Option A: DigitalOcean (recommended for simplicity)

```bash
# Create a droplet via DigitalOcean dashboard or CLI:
# - Ubuntu 22.04 LTS
# - 4 GB RAM / 2 vCPUs (s-2vcpu-4gb) — $24/mo
# - Choose a datacenter region near you (e.g., NYC1, SFO3)
# - Add your SSH key

# Once created, SSH in:
ssh root@YOUR_SERVER_IP
```

### Install Docker

```bash
# Update system
apt update && apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com | sh

# Install Docker Compose plugin
apt install docker-compose-plugin -y

# Verify
docker --version
docker compose version
```

---

## Step 3: DNS Setup

In your DNS provider (wherever turklaylaw.com is registered):

1. Create an **A record**:
   - Name: `app`
   - Value: `YOUR_SERVER_IP`
   - TTL: 300 (5 minutes, can increase later)

2. Wait for propagation (usually 1-5 minutes):
   ```bash
   dig app.turklaylaw.com
   ```

---

## Step 4: Deploy the Application

### Clone and configure

```bash
# On your server:
cd /opt
git clone YOUR_REPO_URL mushroom-cloud
cd mushroom-cloud

# Switch to the deployment branch
git checkout claude/quizzical-panini
```

### Create the .env file

```bash
cp .env.production .env
```

Now edit `.env` and fill in all `FILL_ME` values:

```bash
nano .env
```

Fill in:
- `DB_PASSWORD` — generate with: `openssl rand -base64 32`
- `CLERK_SECRET_KEY` — from Clerk Dashboard (Step 1.4)
- `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` — from Clerk Dashboard (Step 1.4)
- `CLERK_JWKS_URL` — from Clerk Dashboard (Step 1.4)
- `JWT_SECRET` — generate with: `openssl rand -base64 48`
- `ANTHROPIC_API_KEY` — your Claude API key
- `GRAFANA_ADMIN_PASSWORD` — generate with: `openssl rand -base64 16`

### SSL Certificates

**Option A: Cloudflare Tunnel (recommended — zero-config HTTPS)**

If turklaylaw.com uses Cloudflare DNS:
```bash
# Install cloudflared
curl -L --output cloudflared.deb https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb
dpkg -i cloudflared.deb

# Authenticate
cloudflared tunnel login

# Create tunnel
cloudflared tunnel create mushroom-cloud

# Configure tunnel
cat > ~/.cloudflared/config.yml << 'EOF'
tunnel: YOUR_TUNNEL_ID
credentials-file: /root/.cloudflared/YOUR_TUNNEL_ID.json

ingress:
  - hostname: app.turklaylaw.com
    service: http://localhost:80
  - service: http_status:404
EOF

# Route DNS
cloudflared tunnel route dns mushroom-cloud app.turklaylaw.com

# Start as service
cloudflared service install
systemctl start cloudflared
```

With Cloudflare Tunnel, nginx doesn't need TLS certs — Cloudflare handles HTTPS.
Update nginx.conf to listen on port 80 only (remove the 443 server block),
or use the tunnel to point directly at port 80.

**Option B: Let's Encrypt (if not using Cloudflare)**

```bash
# Install certbot
apt install certbot -y

# Get certificate (stop nginx first)
certbot certonly --standalone -d app.turklaylaw.com --agree-tos -m daniel@turklaylaw.com

# Copy certs where nginx expects them
mkdir -p nginx/certs
cp /etc/letsencrypt/live/app.turklaylaw.com/fullchain.pem nginx/certs/
cp /etc/letsencrypt/live/app.turklaylaw.com/privkey.pem nginx/certs/

# Set up auto-renewal (certbot adds a cron/timer automatically)
certbot renew --dry-run
```

### Launch

```bash
# Build and start all services
docker compose -f docker-compose.prod.yml up -d --build

# Watch logs
docker compose -f docker-compose.prod.yml logs -f

# Check health
curl http://localhost:8000/api/v1/health
```

---

## Step 5: Verify Deployment

1. Open **https://app.turklaylaw.com** in your browser
2. You should see the Clerk sign-in page
3. Click **"Continue with Google"**
4. Sign in with `daniel@turklaylaw.com`
5. If MFA is configured, you'll be prompted for your phone verification
6. You should land on the case dashboard

### Verify API health

```bash
curl https://app.turklaylaw.com/api/v1/health
```

Expected:
```json
{
  "status": "healthy",
  "service": "Project Mushroom Cloud API",
  "database": "connected",
  "llm": "configured",
  "data_dir": "ok"
}
```

---

## Step 6: Set Your Admin Role

After first sign-in, your Clerk user exists but may not have the admin role set.

**In the Clerk Dashboard**:
1. Go to **Users** → click your user (daniel@turklaylaw.com)
2. Scroll to **Public metadata**
3. Set: `{"role": "admin"}`
4. Save

This gives you full admin access to all API endpoints.

---

## Post-Deployment

### Monitoring (optional)

```bash
# Start monitoring stack (Prometheus + Grafana + Jaeger)
docker compose -f docker-compose.monitoring.yml up -d

# Grafana: https://app.turklaylaw.com:3001 (or tunnel a separate subdomain)
# Default login: admin / (your GRAFANA_ADMIN_PASSWORD)
```

### Backups

```bash
# Edit backup script with your B2 credentials (if using Backblaze)
nano deploy/backup.sh

# Manual backup
chmod +x deploy/backup.sh
./deploy/backup.sh

# Automated daily backups via systemd timer
cp deploy/mushroom-backup.service /etc/systemd/system/
cp deploy/mushroom-backup.timer /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now mushroom-backup.timer
```

### Adding Users Later

When you want to add more attorneys or staff:
1. Clerk Dashboard → **Restrictions** → **Allowlist** → add their email
2. Clerk Dashboard → **Users** → **Create user** (or let them sign up via Google)
3. Set their role in Public metadata: `{"role": "attorney"}` or `{"role": "paralegal"}`

### Updating the Application

```bash
cd /opt/mushroom-cloud
git pull
docker compose -f docker-compose.prod.yml up -d --build
```

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| "Missing authorization header" | Clerk keys not set or mismatched |
| "Invalid or expired token" | Check CLERK_JWKS_URL matches your Clerk instance |
| Database connection error | Check DB_PASSWORD matches in .env and docker-compose |
| 502 Bad Gateway | API container not healthy — check `docker compose logs api` |
| CORS error in browser | Verify CORS_ORIGINS includes your exact domain with https:// |
| "JWT_SECRET required" | Set JWT_SECRET in .env (needed for ENVIRONMENT=production) |
| Sign-up page appears | Sign-up is disabled; if Clerk still shows it, set Restrictions in Dashboard |

---

## Security Checklist

- [x] Public sign-up disabled (code + Clerk restrictions)
- [x] Email allowlist: daniel@turklaylaw.com only
- [x] Google OAuth (no password-based auth)
- [x] SMS MFA enabled (6158385903)
- [x] HTTPS via Cloudflare Tunnel or Let's Encrypt
- [x] nginx rate limiting (30 req/s burst 20)
- [x] Application-level rate limiting (120 req/min)
- [x] Security headers (HSTS, X-Frame-Options, etc.)
- [x] Non-root Docker containers
- [x] Database not exposed to internet (internal network only)
- [x] JWT_SECRET enforced in production
- [x] CORS locked to explicit origin
