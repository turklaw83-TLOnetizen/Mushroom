#!/usr/bin/env bash
# ---- SSL Certificate Renewal via Certbot ---------------------------------
# Uses Cloudflare DNS-01 challenge (no port 80 needed, works behind proxy).
#
# First-time setup:
#   1. Install certbot: apt install certbot python3-certbot-dns-cloudflare
#   2. Create /root/.cloudflare-credentials with:
#        dns_cloudflare_api_token = <your-cloudflare-api-token>
#   3. chmod 600 /root/.cloudflare-credentials
#   4. Run this script with --initial to get the first certificate
#   5. Add to crontab: 0 3 1,15 * * /root/project-mushroom-cloud/deploy/ssl-renew.sh >> /var/log/ssl-renew.log 2>&1
#
# Cloudflare API token needs: Zone:DNS:Edit permission for turkclaw.net

set -euo pipefail

DOMAIN="turkclaw.net"
CREDS="/root/.cloudflare-credentials"
CERT_DIR="/root/project-mushroom-cloud/nginx/certs"
COMPOSE_FILE="/root/project-mushroom-cloud/docker-compose.prod.yml"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"; }

# First-time certificate issuance
if [[ "${1:-}" == "--initial" ]]; then
    log "Requesting initial certificate for ${DOMAIN}..."
    certbot certonly \
        --dns-cloudflare \
        --dns-cloudflare-credentials "${CREDS}" \
        -d "${DOMAIN}" \
        -d "*.${DOMAIN}" \
        --agree-tos \
        --non-interactive \
        --email "admin@${DOMAIN}" \
        --preferred-challenges dns-01

    log "Copying certificates to nginx..."
    cp /etc/letsencrypt/live/${DOMAIN}/fullchain.pem "${CERT_DIR}/fullchain.pem"
    cp /etc/letsencrypt/live/${DOMAIN}/privkey.pem "${CERT_DIR}/privkey.pem"

    log "Reloading nginx..."
    docker compose -f "${COMPOSE_FILE}" exec nginx nginx -s reload

    log "Initial certificate setup complete"
    exit 0
fi

# Renewal
log "Attempting certificate renewal..."
certbot renew --quiet --dns-cloudflare --dns-cloudflare-credentials "${CREDS}"

# Copy renewed certs to nginx volume
if [[ -f "/etc/letsencrypt/live/${DOMAIN}/fullchain.pem" ]]; then
    cp /etc/letsencrypt/live/${DOMAIN}/fullchain.pem "${CERT_DIR}/fullchain.pem"
    cp /etc/letsencrypt/live/${DOMAIN}/privkey.pem "${CERT_DIR}/privkey.pem"

    log "Reloading nginx with renewed certificate..."
    docker compose -f "${COMPOSE_FILE}" exec nginx nginx -s reload
    log "SSL renewal complete"
else
    log "No renewal needed or certificates not found"
fi
