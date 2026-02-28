#!/usr/bin/env bash
# ── Tailscale Setup for TLO AllRise ──
# Provides a private encrypted mesh network between your machines.
# Access TLO AllRise from anywhere via Tailscale IP, no port forwarding needed.
#
# Use case: Two machines (home + office) synced via Dropbox, both accessible
# via Tailscale from any device on your tailnet.

set -euo pipefail

echo "=== TLO AllRise — Tailscale Setup ==="

# 1. Install Tailscale
if ! command -v tailscale &>/dev/null; then
    echo "Installing Tailscale..."
    if [[ "$(uname -s)" == "Linux" ]]; then
        curl -fsSL https://tailscale.com/install.sh | sh
    elif [[ "$(uname -s)" == "Darwin" ]]; then
        echo "Install Tailscale from the Mac App Store or: brew install tailscale"
        exit 1
    else
        echo "Download Tailscale from: https://tailscale.com/download"
        exit 1
    fi
fi

echo "Tailscale version: $(tailscale version 2>/dev/null || echo 'not running')"

# 2. Start and authenticate
echo ""
echo "Step 1: Starting Tailscale (browser will open for auth)..."
sudo tailscale up

# 3. Show current IP
echo ""
TAILSCALE_IP=$(tailscale ip -4 2>/dev/null || echo "unknown")
echo "Your Tailscale IP: ${TAILSCALE_IP}"

# 4. Enable HTTPS (optional - requires Tailscale Funnel or MagicDNS)
echo ""
echo "Step 2: Enabling MagicDNS and HTTPS certificates..."
echo "Go to https://login.tailscale.com/admin/dns to enable MagicDNS."
echo ""

# 5. Serve TLO AllRise via Tailscale
echo "Step 3: To serve TLO AllRise via Tailscale HTTPS:"
echo ""
echo "  # Serve locally on tailnet (private, only your devices):"
echo "  tailscale serve https / http://localhost:8501"
echo ""
echo "  # Or expose publicly via Tailscale Funnel (public HTTPS):"
echo "  tailscale funnel https / http://localhost:8501"
echo ""

# 6. Summary
HOSTNAME=$(tailscale status --self --json 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin).get('Self',{}).get('DNSName','').rstrip('.'))" 2>/dev/null || echo "your-machine")
echo "=== Setup Complete ==="
echo ""
echo "Access TLO AllRise from any device on your tailnet:"
echo "  http://${TAILSCALE_IP}:8501"
echo "  https://${HOSTNAME} (after 'tailscale serve')"
echo ""
echo "Windows: Download Tailscale from https://tailscale.com/download/windows"
echo "Phone:   Install Tailscale from your app store"
