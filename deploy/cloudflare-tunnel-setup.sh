#!/usr/bin/env bash
# ── Cloudflare Tunnel Setup for TLO AllRise ──
# Provides free HTTPS without opening ports or managing certificates.
#
# Prerequisites:
#   - Cloudflare account (free tier works)
#   - Domain pointed to Cloudflare DNS
#
# This script installs cloudflared and creates a tunnel.

set -euo pipefail

TUNNEL_NAME="${TUNNEL_NAME:-tlo-allrise}"
DOMAIN="${DOMAIN:-allrise.yourdomain.com}"
LOCAL_PORT="${LOCAL_PORT:-8501}"

echo "=== TLO AllRise — Cloudflare Tunnel Setup ==="

# 1. Install cloudflared
if ! command -v cloudflared &>/dev/null; then
    echo "Installing cloudflared..."
    if [[ "$(uname -s)" == "Linux" ]]; then
        curl -fsSL https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 \
            -o /usr/local/bin/cloudflared
        chmod +x /usr/local/bin/cloudflared
    elif [[ "$(uname -s)" == "Darwin" ]]; then
        brew install cloudflare/cloudflare/cloudflared
    else
        echo "Please install cloudflared manually: https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/"
        exit 1
    fi
fi

echo "cloudflared version: $(cloudflared --version)"

# 2. Authenticate (opens browser)
echo ""
echo "Step 1: Authenticate with Cloudflare (browser will open)..."
cloudflared tunnel login

# 3. Create tunnel
echo ""
echo "Step 2: Creating tunnel '${TUNNEL_NAME}'..."
cloudflared tunnel create "${TUNNEL_NAME}"

# 4. Get tunnel ID
TUNNEL_ID=$(cloudflared tunnel info "${TUNNEL_NAME}" 2>/dev/null | head -1 | awk '{print $1}')
echo "Tunnel ID: ${TUNNEL_ID}"

# 5. Create config file
CONFIG_DIR="${HOME}/.cloudflared"
mkdir -p "${CONFIG_DIR}"
cat > "${CONFIG_DIR}/config.yml" <<EOF
tunnel: ${TUNNEL_ID}
credentials-file: ${CONFIG_DIR}/${TUNNEL_ID}.json

ingress:
  - hostname: ${DOMAIN}
    service: http://localhost:${LOCAL_PORT}
    originRequest:
      noTLSVerify: true
  - service: http_status:404
EOF

echo "Config written to ${CONFIG_DIR}/config.yml"

# 6. Create DNS route
echo ""
echo "Step 3: Creating DNS route..."
cloudflared tunnel route dns "${TUNNEL_NAME}" "${DOMAIN}"

# 7. Install as service
echo ""
echo "Step 4: Installing cloudflared as system service..."
if [[ "$(uname -s)" == "Linux" ]]; then
    sudo cloudflared service install
    sudo systemctl enable --now cloudflared
    echo "Cloudflared service installed and started."
else
    echo "On macOS, run: sudo cloudflared service install"
fi

echo ""
echo "=== Setup Complete ==="
echo "Your app will be available at: https://${DOMAIN}"
echo ""
echo "To test manually: cloudflared tunnel run ${TUNNEL_NAME}"
echo "To check status:  cloudflared tunnel info ${TUNNEL_NAME}"
