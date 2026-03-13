#!/usr/bin/env bash
# ---- Generate Self-Signed SSL Certificates for PostgreSQL ----------------
# Run this ONCE on the VPS before starting containers with SSL.
#
# Usage: cd deploy/db-ssl && bash generate-certs.sh
#
# Produces:
#   server.key  — private key (600 permissions, owned by postgres UID 70)
#   server.crt  — self-signed certificate (valid 10 years)
#
# These are for encrypting traffic between the API container and the DB
# container on the Docker internal network. Self-signed is fine because
# both containers are on the same host — no CA trust chain needed.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "Generating PostgreSQL SSL certificates..."

# Generate private key
openssl genrsa -out server.key 4096

# Generate self-signed certificate (10 year validity)
openssl req -new -x509 \
    -key server.key \
    -out server.crt \
    -days 3650 \
    -subj "/CN=mushroom-cloud-db/O=Project Mushroom Cloud/C=US"

# PostgreSQL requires key to be readable only by owner
# In the postgres:16-alpine container, postgres runs as UID 70
chmod 600 server.key
chmod 644 server.crt
chown 70:70 server.key server.crt 2>/dev/null || true

echo "SSL certificates generated:"
echo "  server.key  ($(wc -c < server.key) bytes)"
echo "  server.crt  ($(wc -c < server.crt) bytes)"
echo ""
echo "Certificate details:"
openssl x509 -in server.crt -noout -subject -dates
echo ""
echo "Done. Restart containers: docker compose -f docker-compose.prod.yml up -d"
