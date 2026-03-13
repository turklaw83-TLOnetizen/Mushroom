#!/usr/bin/env bash
# ---- Secrets Rotation Script ---------------------------------------------
# Interactive tool for rotating production secrets. Walks you through each
# secret, generates new values, and updates the VPS .env file.
#
# Usage: ssh root@45.32.216.52 'bash -s' < deploy/rotate-secrets.sh
#    or: ssh into VPS, then: cd /root/project-mushroom-cloud && bash deploy/rotate-secrets.sh
#
# What this rotates:
#   1. DB_PASSWORD           — PostgreSQL password (requires DB ALTER + restart)
#   2. ENCRYPTION_KEY        — Fernet encryption key (requires data re-encryption!)
#   3. JWT_SECRET            — JWT signing key (invalidates all active tokens)
#   4. CLERK_SECRET_KEY      — Clerk API key (regenerate in Clerk dashboard first)
#   5. STRIPE_WEBHOOK_SECRET — Stripe endpoint secret (regenerate in Stripe dashboard first)
#   6. DB SSL certificates   — PostgreSQL TLS certs (regenerate + restart DB)
#
# Safety:
#   - Creates timestamped backup of .env before any changes
#   - Prompts for confirmation before each rotation
#   - Prints post-rotation steps (restart, re-encryption, etc.)

set -euo pipefail

ENV_FILE="${ENV_FILE:-.env}"
BACKUP_DIR="deploy/secret-backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}=== Project Mushroom Cloud — Secrets Rotation ===${NC}"
echo -e "Timestamp: ${TIMESTAMP}"
echo ""

# ---- Backup current .env ------------------------------------------------
if [ -f "$ENV_FILE" ]; then
    mkdir -p "$BACKUP_DIR"
    cp "$ENV_FILE" "${BACKUP_DIR}/env-backup-${TIMESTAMP}"
    chmod 600 "${BACKUP_DIR}/env-backup-${TIMESTAMP}"
    echo -e "${GREEN}Backed up .env to ${BACKUP_DIR}/env-backup-${TIMESTAMP}${NC}"
else
    echo -e "${RED}No .env file found at ${ENV_FILE}${NC}"
    exit 1
fi

# ---- Helper: update a key in .env ---------------------------------------
update_env() {
    local key="$1"
    local value="$2"
    if grep -q "^${key}=" "$ENV_FILE"; then
        sed -i "s|^${key}=.*|${key}=${value}|" "$ENV_FILE"
    else
        echo "${key}=${value}" >> "$ENV_FILE"
    fi
}

# ---- 1. DB_PASSWORD ------------------------------------------------------
echo ""
echo -e "${YELLOW}1. DB_PASSWORD${NC}"
echo "   Rotates the PostgreSQL password. Requires ALTER USER + container restart."
read -p "   Rotate DB_PASSWORD? (y/N): " -r
if [[ "$REPLY" =~ ^[Yy]$ ]]; then
    NEW_DB_PASS="mcloud-$(openssl rand -hex 12)"
    echo -e "   New password: ${GREEN}${NEW_DB_PASS}${NC}"

    # Update PostgreSQL password
    echo "   Updating PostgreSQL password..."
    docker compose -f docker-compose.prod.yml exec -T db \
        psql -U mushroom -d mushroom_cloud \
        -c "ALTER USER mushroom WITH PASSWORD '${NEW_DB_PASS}';" 2>/dev/null && \
        echo -e "   ${GREEN}PostgreSQL password updated${NC}" || \
        echo -e "   ${RED}Failed to update PostgreSQL — update manually${NC}"

    update_env "DB_PASSWORD" "$NEW_DB_PASS"
    echo -e "   ${GREEN}.env updated${NC}"
    echo -e "   ${YELLOW}Action needed: docker compose -f docker-compose.prod.yml up -d api worker${NC}"
fi

# ---- 2. ENCRYPTION_KEY --------------------------------------------------
echo ""
echo -e "${YELLOW}2. ENCRYPTION_KEY${NC}"
echo -e "   ${RED}DANGER: Rotating this requires re-encrypting ALL stored data.${NC}"
echo "   Only rotate if the key is compromised."
read -p "   Rotate ENCRYPTION_KEY? (y/N): " -r
if [[ "$REPLY" =~ ^[Yy]$ ]]; then
    read -p "   Are you SURE? Data will be unreadable without re-encryption. (type 'ROTATE'): " -r
    if [ "$REPLY" = "ROTATE" ]; then
        NEW_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
        echo -e "   New key: ${GREEN}${NEW_KEY}${NC}"
        echo -e "   ${RED}CRITICAL: You must re-encrypt all data before restarting.${NC}"
        echo "   Steps:"
        echo "     1. Stop the API: docker compose -f docker-compose.prod.yml stop api"
        echo "     2. Run re-encryption script with OLD and NEW keys"
        echo "     3. Update .env with new key"
        echo "     4. Restart: docker compose -f docker-compose.prod.yml up -d"
        update_env "ENCRYPTION_KEY" "$NEW_KEY"
        echo -e "   ${GREEN}.env updated (API must be restarted)${NC}"
    else
        echo "   Skipped."
    fi
fi

# ---- 3. JWT_SECRET -------------------------------------------------------
echo ""
echo -e "${YELLOW}3. JWT_SECRET${NC}"
echo "   Rotates the JWT signing key. All active tokens will be invalidated."
echo "   Users will need to re-authenticate."
read -p "   Rotate JWT_SECRET? (y/N): " -r
if [[ "$REPLY" =~ ^[Yy]$ ]]; then
    NEW_JWT=$(openssl rand -hex 32)
    echo -e "   New secret: ${GREEN}${NEW_JWT}${NC}"
    update_env "JWT_SECRET" "$NEW_JWT"
    echo -e "   ${GREEN}.env updated${NC}"
    echo -e "   ${YELLOW}Action needed: docker compose -f docker-compose.prod.yml up -d api${NC}"
fi

# ---- 4. CLERK_SECRET_KEY ------------------------------------------------
echo ""
echo -e "${YELLOW}4. CLERK_SECRET_KEY${NC}"
echo "   Must be regenerated in the Clerk Dashboard FIRST:"
echo "   https://dashboard.clerk.com → Settings → API Keys → Regenerate"
read -p "   Have you regenerated in Clerk? Paste new key (or Enter to skip): " -r
if [ -n "$REPLY" ]; then
    update_env "CLERK_SECRET_KEY" "$REPLY"
    echo -e "   ${GREEN}.env updated${NC}"
    echo -e "   ${YELLOW}Action needed: docker compose -f docker-compose.prod.yml up -d api frontend${NC}"
fi

# ---- 5. STRIPE_WEBHOOK_SECRET -------------------------------------------
echo ""
echo -e "${YELLOW}5. STRIPE_WEBHOOK_SECRET${NC}"
echo "   Must be regenerated in Stripe Dashboard FIRST:"
echo "   https://dashboard.stripe.com → Developers → Webhooks → Reveal secret"
read -p "   Have you regenerated in Stripe? Paste new secret (or Enter to skip): " -r
if [ -n "$REPLY" ]; then
    update_env "STRIPE_WEBHOOK_SECRET" "$REPLY"
    echo -e "   ${GREEN}.env updated${NC}"
    echo -e "   ${YELLOW}Action needed: docker compose -f docker-compose.prod.yml up -d api${NC}"
fi

# ---- 6. DB SSL Certificates ---------------------------------------------
echo ""
echo -e "${YELLOW}6. DB SSL Certificates${NC}"
echo "   Regenerates the self-signed TLS certs for PostgreSQL."
read -p "   Rotate DB SSL certs? (y/N): " -r
if [[ "$REPLY" =~ ^[Yy]$ ]]; then
    if [ -f deploy/db-ssl/generate-certs.sh ]; then
        bash deploy/db-ssl/generate-certs.sh
        echo -e "   ${YELLOW}Action needed: docker compose -f docker-compose.prod.yml restart db api${NC}"
    else
        echo -e "   ${RED}generate-certs.sh not found — run from project root${NC}"
    fi
fi

# ---- Summary -------------------------------------------------------------
echo ""
echo -e "${CYAN}=== Rotation Complete ===${NC}"
echo -e "Backup saved: ${BACKUP_DIR}/env-backup-${TIMESTAMP}"
echo ""
echo "Post-rotation checklist:"
echo "  [ ] Restart affected containers"
echo "  [ ] Verify app loads correctly"
echo "  [ ] Check audit logs for errors"
echo "  [ ] Test authentication flow"
echo "  [ ] Delete old .env backup after confirming (keep 30 days)"
echo ""
echo -e "${YELLOW}Recommended rotation schedule:${NC}"
echo "  DB_PASSWORD:           Every 90 days"
echo "  JWT_SECRET:            Every 90 days"
echo "  CLERK_SECRET_KEY:      Every 6 months (or if compromised)"
echo "  STRIPE_WEBHOOK_SECRET: Every 6 months (or if compromised)"
echo "  ENCRYPTION_KEY:        Only if compromised"
echo "  DB SSL Certs:          Annually"
