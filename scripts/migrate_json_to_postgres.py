#!/usr/bin/env python3
# ---- JSON → PostgreSQL Migration Script ----------------------------------
# Migrates all existing case data from the JSON file-system backend
# to PostgreSQL. Run once after setting up the database.
#
# Usage:
#   python scripts/migrate_json_to_postgres.py
#
# Requires DATABASE_URL in .env or environment.

import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add project root to path
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv(_PROJECT_ROOT / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("migrate")


def migrate():
    """Run the full JSON → PostgreSQL migration."""
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        logger.error("DATABASE_URL not set. Add it to .env or environment.")
        sys.exit(1)

    data_dir = str(_PROJECT_ROOT / "data")
    if not os.path.exists(data_dir):
        logger.error("Data directory not found: %s", data_dir)
        sys.exit(1)

    # Convert async URL to sync
    sync_url = database_url.replace("postgresql+asyncpg://", "postgresql://")

    # Create all tables
    from sqlalchemy import create_engine
    from api.models import Base

    engine = create_engine(sync_url, echo=False)
    Base.metadata.create_all(engine)
    logger.info("Database tables created/verified")

    # Initialize backends
    from core.storage.json_backend import JSONStorageBackend
    from core.storage.postgres_backend import PostgresStorageBackend

    json_backend = JSONStorageBackend(data_dir)
    pg_backend = PostgresStorageBackend(database_url, data_dir)

    # ---- Migrate Global Data ---------------------------------------------
    logger.info("=== Migrating global data ===")

    # Phase config
    phase_config = json_backend.load_global_json("phase_config.json")
    if phase_config:
        pg_backend.save_global_json("phase_config.json", phase_config)
        logger.info("  Migrated phase_config.json")

    # Prospective clients
    clients = json_backend.load_prospective_clients()
    if clients:
        pg_backend.save_prospective_clients(clients)
        logger.info("  Migrated %d prospective clients", len(clients))

    # Any other global JSON files
    data_path = Path(data_dir)
    for f in data_path.glob("*.json"):
        if f.name != "prospective_clients.json" and f.name != "phase_config.json":
            data = json_backend.load_global_json(f.name)
            if data is not None:
                pg_backend.save_global_json(f.name, data)
                logger.info("  Migrated global: %s", f.name)

    # ---- Migrate Cases ---------------------------------------------------
    logger.info("=== Migrating cases ===")

    all_cases = json_backend.list_cases(include_archived=True)
    logger.info("Found %d cases to migrate", len(all_cases))

    for case_meta in all_cases:
        case_id = case_meta.get("id", "")
        if not case_id:
            continue

        try:
            _migrate_case(json_backend, pg_backend, case_id, case_meta)
        except Exception:
            logger.exception("FAILED to migrate case: %s", case_id)
            continue

    # ---- Migrate Users ---------------------------------------------------
    logger.info("=== Migrating users ===")
    _migrate_users(data_dir, sync_url)

    logger.info("=== Migration complete! ===")


def _migrate_case(json_be, pg_be, case_id: str, case_meta: dict):
    """Migrate a single case and all its sub-data."""
    case_name = case_meta.get("name", case_id)
    logger.info("  Case: %s (%s)", case_name, case_id)

    # Create case in Postgres
    if pg_be.case_exists(case_id):
        logger.info("    Already exists, updating metadata")
        pg_be.update_case_metadata(case_id, case_meta)
    else:
        pg_be.create_case(case_id, case_meta)

    # Legacy state
    legacy_state = json_be.load_state(case_id)
    if legacy_state:
        pg_be.save_state(case_id, legacy_state)
        logger.info("    Migrated legacy state")

    # Activity log
    activity = json_be.get_activity_log(case_id, limit=2000)
    for entry in reversed(activity):  # Insert oldest first
        pg_be.append_activity(case_id, entry)
    if activity:
        logger.info("    Migrated %d activity entries", len(activity))

    # File tags & order
    tags = json_be.get_file_tags(case_id)
    if tags:
        pg_be.save_file_tags(case_id, tags)
    order = json_be.get_file_order(case_id)
    if order:
        pg_be.save_file_order(case_id, order)

    # Case-level JSON files
    _CASE_JSON_FILES = [
        "directives.json", "journal.json", "contact_log.json",
        "manual_entities.json", "ocr_reviews.json", "custom_file_tags.json",
        "fee_agreement.json", "litigation_holds.json", "supervision_log.json",
        "trust_ledger.json",
    ]
    for fname in _CASE_JSON_FILES:
        data = json_be.load_json(case_id, fname)
        if data is not None:
            pg_be.save_json(case_id, fname, data)

    # Case-level text files
    for fname in ["notes.txt", "case_notes.txt"]:
        text = json_be.load_text(case_id, fname)
        if text:
            pg_be.save_text(case_id, fname, text)

    # File metadata (from disk scan — files stay on disk, just record metadata)
    files = json_be.get_case_files(case_id)
    if files:
        for fp in files:
            filename = os.path.basename(fp)
            try:
                size = os.path.getsize(fp)
            except OSError:
                size = 0
            # Record metadata WITHOUT writing to disk (Fix #3)
            pg_be.record_file_metadata(case_id, filename, fp, size)
        logger.info("    Recorded metadata for %d files", len(files))

    # Preparations
    preps = json_be.list_preparations(case_id)
    if preps:
        pg_be.save_preparations_index(case_id, preps)
        logger.info("    Migrated %d preparations", len(preps))

        for prep in preps:
            prep_id = prep.get("id", "")
            if not prep_id:
                continue

            # Prep state
            state = json_be.load_prep_state(case_id, prep_id)
            if state:
                pg_be.save_prep_state(case_id, prep_id, state)

            # Prep JSON files
            _PREP_JSON_FILES = [
                "chat_history.json", "evidence_tags.json", "annotations.json",
                "witness_prep.json", "deadlines.json", "checklist.json",
                "cost_history.json",
            ]
            for fname in _PREP_JSON_FILES:
                data = json_be.load_prep_json(case_id, prep_id, fname)
                if data is not None:
                    pg_be.save_prep_json(case_id, prep_id, fname, data)

            # Prep text files
            notes = json_be.load_prep_text(case_id, prep_id, "notes.txt")
            if notes:
                pg_be.save_prep_text(case_id, prep_id, "notes.txt", notes)

            # Module notes
            _MODULE_NAMES = [
                "case_theory", "timeline_analysis", "witness_analysis",
                "evidence_matrix", "jury_considerations", "defense_strategy",
                "motion_strategy", "case_weaknesses", "opening_statement",
                "closing_argument", "cross_examination", "legal_research",
                "deposition_analysis", "expert_analysis",
            ]
            for mod in _MODULE_NAMES:
                text = json_be.load_module_notes(case_id, prep_id, mod)
                if text:
                    pg_be.save_module_notes(case_id, prep_id, mod, text)

            # Snapshots
            snapshots = json_be.list_snapshots(case_id, prep_id)
            for snap in snapshots:
                snap_id = snap.get("id", "")
                if not snap_id:
                    continue
                snap_state = json_be.load_snapshot(case_id, prep_id, snap_id)
                if snap_state:
                    pg_be.save_snapshot(case_id, prep_id, snap_id, snap_state, snap)


def _migrate_users(data_dir: str, sync_url: str):
    """Migrate user profiles from JSON to the users table."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session as SyncSession
    from api.models import User

    profiles_path = Path(data_dir) / "users" / "profiles.json"
    if not profiles_path.exists():
        logger.info("  No user profiles found")
        return

    try:
        with open(profiles_path, "r", encoding="utf-8") as f:
            profiles = json.load(f)
    except (json.JSONDecodeError, OSError):
        logger.warning("  Could not read profiles.json")
        return

    engine = create_engine(sync_url)
    with SyncSession(engine) as session:
        for p in profiles:
            uid = p.get("id", "")
            if not uid:
                continue

            existing = session.get(User, uid)
            if existing:
                logger.info("  User %s already exists, skipping", uid)
                continue

            session.add(User(
                id=uid,
                name=p.get("name", ""),
                initials=p.get("initials", ""),
                email=p.get("email", ""),
                role=p.get("role", "attorney"),
                is_active=p.get("active", True),
                pin_hash=p.get("pin_hash", ""),
                google_email=p.get("google_email", ""),
                google_sub=p.get("google_sub", ""),
                assigned_cases=p.get("assigned_cases", []),
            ))
            logger.info("  Migrated user: %s (%s)", p.get("name", ""), uid)

        session.commit()


if __name__ == "__main__":
    migrate()
