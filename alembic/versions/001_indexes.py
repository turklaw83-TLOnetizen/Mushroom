# ---- Database Indexes + Alembic Setup -----------------------------------
# Index definitions for frequently queried columns.
# Run: alembic revision --autogenerate -m "add indexes"
# Then: alembic upgrade head

"""
Add performance indexes

Revision ID: 001_indexes
"""
from alembic import op
import sqlalchemy as sa


revision = "001_indexes"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Cases — most queried table
    op.create_index("ix_cases_status", "cases", ["status"])
    op.create_index("ix_cases_case_type", "cases", ["case_type"])
    op.create_index("ix_cases_user_id", "cases", ["user_id"])
    op.create_index("ix_cases_created_at", "cases", ["created_at"])
    op.create_index("ix_cases_client_name", "cases", ["client_name"])

    # Files — frequent lookups by case
    op.create_index("ix_files_case_id", "files", ["case_id"])
    op.create_index("ix_files_uploaded_at", "files", ["uploaded_at"])

    # Events / Calendar
    op.create_index("ix_events_case_id", "events", ["case_id"])
    op.create_index("ix_events_date", "events", ["event_date"])

    # Billing
    op.create_index("ix_invoices_case_id", "invoices", ["case_id"])
    op.create_index("ix_time_entries_case_id", "time_entries", ["case_id"])

    # Analysis
    op.create_index("ix_analysis_case_id", "analysis_runs", ["case_id"])
    op.create_index("ix_analysis_status", "analysis_runs", ["status"])

    # Notifications
    op.create_index("ix_notifications_user_id", "notifications", ["user_id"])
    op.create_index("ix_notifications_read", "notifications", ["is_read"])

    # CRM
    op.create_index("ix_clients_name", "clients", ["name"])
    op.create_index("ix_clients_email", "clients", ["email"])

    # Audit log — critical for compliance
    op.create_index("ix_audit_user_id", "audit_log", ["user_id"])
    op.create_index("ix_audit_timestamp", "audit_log", ["timestamp"])
    op.create_index("ix_audit_action", "audit_log", ["action"])


def downgrade():
    for idx in [
        "ix_cases_status", "ix_cases_case_type", "ix_cases_user_id",
        "ix_cases_created_at", "ix_cases_client_name",
        "ix_files_case_id", "ix_files_uploaded_at",
        "ix_events_case_id", "ix_events_date",
        "ix_invoices_case_id", "ix_time_entries_case_id",
        "ix_analysis_case_id", "ix_analysis_status",
        "ix_notifications_user_id", "ix_notifications_read",
        "ix_clients_name", "ix_clients_email",
        "ix_audit_user_id", "ix_audit_timestamp", "ix_audit_action",
    ]:
        op.drop_index(idx)
