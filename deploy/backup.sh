#!/usr/bin/env bash
# ── TLO AllRise Automated Backup Script ──
# Backs up case data to Dropbox (local sync) and optionally Backblaze B2 (cloud).
#
# Usage:
#   ./backup.sh                  # Full backup to Dropbox + B2
#   ./backup.sh --dropbox-only   # Skip B2 upload
#   ./backup.sh --b2-only        # Skip Dropbox, upload directly to B2
#
# Prerequisites:
#   - Dropbox desktop app installed and syncing
#   - b2 CLI installed (pip install b2) for B2 backups
#   - B2 credentials configured via 'b2 authorize-account'

set -euo pipefail

# ── Configuration ──────────────────────────────────────────────────
# Adjust these paths for your environment

# TLO AllRise data directory (contains cases/, phase_config.json, etc.)
TLO_DATA_DIR="${TLO_DATA_DIR:-/opt/tlo-allrise/data}"

# Dropbox backup destination
DROPBOX_BACKUP_DIR="${DROPBOX_BACKUP_DIR:-${HOME}/Dropbox/TLO-AllRise-Backups}"

# Backblaze B2 bucket name
B2_BUCKET="${B2_BUCKET:-tlo-allrise-backups}"

# How many daily backups to keep locally
RETENTION_DAYS="${RETENTION_DAYS:-30}"

# ── Derived ────────────────────────────────────────────────────────
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_NAME="tlo-backup-${TIMESTAMP}"
ARCHIVE_NAME="${BACKUP_NAME}.tar.gz"
TEMP_DIR=$(mktemp -d)
ARCHIVE_PATH="${TEMP_DIR}/${ARCHIVE_NAME}"

# Parse args
SKIP_DROPBOX=false
SKIP_B2=false
for arg in "$@"; do
    case "$arg" in
        --dropbox-only) SKIP_B2=true ;;
        --b2-only)      SKIP_DROPBOX=true ;;
    esac
done

# ── Functions ──────────────────────────────────────────────────────

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"; }

cleanup() {
    rm -rf "${TEMP_DIR}"
}
trap cleanup EXIT

check_data_dir() {
    if [[ ! -d "${TLO_DATA_DIR}" ]]; then
        log "ERROR: Data directory not found: ${TLO_DATA_DIR}"
        exit 1
    fi
}

create_archive() {
    log "Creating backup archive..."

    # Backup everything: configs, case metadata, analysis results, OCR cache
    # Source documents are included (they'll be purged separately via the app)
    tar -czf "${ARCHIVE_PATH}" \
        -C "$(dirname "${TLO_DATA_DIR}")" \
        "$(basename "${TLO_DATA_DIR}")" \
        2>/dev/null

    local size
    size=$(du -sh "${ARCHIVE_PATH}" | cut -f1)
    log "Archive created: ${ARCHIVE_NAME} (${size})"
}

sync_to_dropbox() {
    if [[ "${SKIP_DROPBOX}" == "true" ]]; then
        log "Skipping Dropbox (--b2-only mode)"
        return
    fi

    log "Syncing to Dropbox: ${DROPBOX_BACKUP_DIR}"
    mkdir -p "${DROPBOX_BACKUP_DIR}"

    # Copy archive to Dropbox folder (Dropbox desktop app syncs automatically)
    cp "${ARCHIVE_PATH}" "${DROPBOX_BACKUP_DIR}/"

    # Also sync latest un-archived data for quick file-level access
    local LATEST_DIR="${DROPBOX_BACKUP_DIR}/latest"
    mkdir -p "${LATEST_DIR}"
    rsync -a --delete \
        --exclude='*.pyc' \
        --exclude='__pycache__' \
        --exclude='.DS_Store' \
        "${TLO_DATA_DIR}/" "${LATEST_DIR}/"

    log "Dropbox sync complete"

    # Clean old archives (keep RETENTION_DAYS worth)
    if [[ -d "${DROPBOX_BACKUP_DIR}" ]]; then
        local deleted
        deleted=$(find "${DROPBOX_BACKUP_DIR}" -name "tlo-backup-*.tar.gz" \
            -mtime "+${RETENTION_DAYS}" -delete -print 2>/dev/null | wc -l)
        if [[ "${deleted}" -gt 0 ]]; then
            log "Cleaned ${deleted} old backup(s) from Dropbox (>${RETENTION_DAYS} days)"
        fi
    fi
}

upload_to_b2() {
    if [[ "${SKIP_B2}" == "true" ]]; then
        log "Skipping B2 (--dropbox-only mode)"
        return
    fi

    if ! command -v b2 &>/dev/null; then
        log "WARNING: b2 CLI not installed. Skipping B2 upload."
        log "  Install: pip install b2"
        log "  Auth:    b2 authorize-account <keyID> <applicationKey>"
        return
    fi

    log "Uploading to Backblaze B2: ${B2_BUCKET}"
    b2 upload-file "${B2_BUCKET}" "${ARCHIVE_PATH}" "backups/${ARCHIVE_NAME}"
    log "B2 upload complete"

    # Clean old B2 backups (keep RETENTION_DAYS worth)
    # List files, parse dates, delete old ones
    log "Checking B2 retention policy..."
    local cutoff_date
    cutoff_date=$(date -d "-${RETENTION_DAYS} days" +%Y%m%d 2>/dev/null || \
                  date -v-${RETENTION_DAYS}d +%Y%m%d 2>/dev/null || echo "")

    if [[ -n "${cutoff_date}" ]]; then
        b2 ls --long "${B2_BUCKET}" backups/ 2>/dev/null | while read -r line; do
            local fname
            fname=$(echo "$line" | awk '{print $NF}')
            # Extract date from filename: tlo-backup-YYYYMMDD_HHMMSS.tar.gz
            local fdate
            fdate=$(echo "$fname" | grep -oP '\d{8}' | head -1 || echo "")
            if [[ -n "${fdate}" && "${fdate}" < "${cutoff_date}" ]]; then
                local fid
                fid=$(echo "$line" | awk '{print $1}')
                b2 delete-file-version "${fname}" "${fid}" 2>/dev/null && \
                    log "Deleted old B2 backup: ${fname}"
            fi
        done
    fi
}

generate_manifest() {
    # Write a manifest file for verification
    local manifest="${DROPBOX_BACKUP_DIR}/BACKUP_MANIFEST.txt"
    if [[ "${SKIP_DROPBOX}" == "false" ]]; then
        {
            echo "TLO AllRise Backup Manifest"
            echo "=========================="
            echo "Timestamp: ${TIMESTAMP}"
            echo "Archive:   ${ARCHIVE_NAME}"
            echo "Source:    ${TLO_DATA_DIR}"
            echo ""
            echo "Case count: $(find "${TLO_DATA_DIR}/cases" -maxdepth 1 -type d 2>/dev/null | wc -l)"
            echo "Total size: $(du -sh "${TLO_DATA_DIR}" 2>/dev/null | cut -f1)"
            echo ""
            echo "Destinations:"
            echo "  Dropbox: ${DROPBOX_BACKUP_DIR}"
            [[ "${SKIP_B2}" == "false" ]] && echo "  B2:      ${B2_BUCKET}"
            echo ""
            echo "Last 5 backups:"
            ls -1t "${DROPBOX_BACKUP_DIR}"/tlo-backup-*.tar.gz 2>/dev/null | head -5
        } > "${manifest}"
    fi
}

# ── Main ───────────────────────────────────────────────────────────

log "=== TLO AllRise Backup Starting ==="
check_data_dir
create_archive
sync_to_dropbox
upload_to_b2
generate_manifest
log "=== Backup Complete ==="
