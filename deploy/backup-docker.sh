#!/usr/bin/env bash
# ---- Project Mushroom Cloud — Docker Backup Script ----------------------
# Backs up PostgreSQL database + file data from Docker volumes.
#
# Usage:
#   ./backup-docker.sh                # Full backup (pg_dump + files)
#   ./backup-docker.sh --db-only      # PostgreSQL only
#   ./backup-docker.sh --files-only   # App data files only
#
# Install as cron job (nightly at 2 AM):
#   echo "0 2 * * * /root/project-mushroom-cloud/deploy/backup-docker.sh >> /var/log/mc-backup.log 2>&1" | crontab -
#
# Environment:
#   BACKUP_DIR     — where to store backups (default: /root/backups/mushroom-cloud)
#   RETENTION_DAYS — how many days of backups to keep (default: 30)
#   COMPOSE_FILE   — docker-compose file (default: /root/project-mushroom-cloud/docker-compose.prod.yml)

set -euo pipefail

# ---- Configuration -------------------------------------------------------

BACKUP_DIR="${BACKUP_DIR:-/root/backups/mushroom-cloud}"
RETENTION_DAYS="${RETENTION_DAYS:-30}"
COMPOSE_FILE="${COMPOSE_FILE:-/root/project-mushroom-cloud/docker-compose.prod.yml}"
PROJECT_DIR="$(dirname "${COMPOSE_FILE}")"

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
DB_CONTAINER="project-mushroom-cloud-db-1"
API_CONTAINER="project-mushroom-cloud-api-1"

# Parse args
SKIP_DB=false
SKIP_FILES=false
for arg in "$@"; do
    case "$arg" in
        --db-only)    SKIP_FILES=true ;;
        --files-only) SKIP_DB=true ;;
    esac
done

# ---- Functions -----------------------------------------------------------

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"; }

backup_database() {
    if [[ "${SKIP_DB}" == "true" ]]; then
        log "Skipping database (--files-only mode)"
        return
    fi

    local db_backup="${BACKUP_DIR}/db/mc-db-${TIMESTAMP}.sql.gz"
    mkdir -p "${BACKUP_DIR}/db"

    log "Dumping PostgreSQL database..."
    if docker exec "${DB_CONTAINER}" pg_dump -U mushroom -d mushroom_cloud --no-owner --no-acl | gzip > "${db_backup}"; then
        local size
        size=$(du -sh "${db_backup}" | cut -f1)
        log "Database backup: ${db_backup} (${size})"
    else
        log "ERROR: pg_dump failed"
        return 1
    fi
}

backup_files() {
    if [[ "${SKIP_FILES}" == "true" ]]; then
        log "Skipping files (--db-only mode)"
        return
    fi

    local files_backup="${BACKUP_DIR}/files/mc-files-${TIMESTAMP}.tar.gz"
    mkdir -p "${BACKUP_DIR}/files"

    # Get the volume mount path for appdata
    local volume_path
    volume_path=$(docker volume inspect project-mushroom-cloud_appdata --format '{{ .Mountpoint }}' 2>/dev/null || echo "")

    if [[ -z "${volume_path}" ]]; then
        log "WARNING: appdata volume not found. Trying alternative names..."
        volume_path=$(docker volume inspect mushroom-cloud_appdata --format '{{ .Mountpoint }}' 2>/dev/null || echo "")
    fi

    if [[ -n "${volume_path}" && -d "${volume_path}" ]]; then
        log "Backing up app data from ${volume_path}..."
        tar -czf "${files_backup}" -C "$(dirname "${volume_path}")" "$(basename "${volume_path}")" 2>/dev/null
        local size
        size=$(du -sh "${files_backup}" | cut -f1)
        log "Files backup: ${files_backup} (${size})"
    else
        log "WARNING: Could not locate appdata volume. Skipping file backup."
    fi
}

cleanup_old() {
    log "Cleaning backups older than ${RETENTION_DAYS} days..."
    local deleted=0

    for dir in "${BACKUP_DIR}/db" "${BACKUP_DIR}/files"; do
        if [[ -d "${dir}" ]]; then
            local count
            count=$(find "${dir}" -name "mc-*" -mtime "+${RETENTION_DAYS}" -delete -print 2>/dev/null | wc -l)
            deleted=$((deleted + count))
        fi
    done

    if [[ "${deleted}" -gt 0 ]]; then
        log "Removed ${deleted} old backup(s)"
    fi
}

# ---- Main ----------------------------------------------------------------

log "=== Mushroom Cloud Backup Starting ==="

# Verify containers are running
if ! docker ps --format '{{.Names}}' | grep -q "${DB_CONTAINER}"; then
    log "ERROR: Database container ${DB_CONTAINER} is not running"
    exit 1
fi

mkdir -p "${BACKUP_DIR}"

backup_database
backup_files
cleanup_old

log "=== Backup Complete ==="
