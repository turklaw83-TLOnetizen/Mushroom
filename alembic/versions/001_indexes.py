# ---- Database Indexes + Alembic Setup -----------------------------------
# Index definitions for frequently queried columns.
# Aligned with api/models.py table definitions.
#
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
    # Note: 'name', 'phase' already have index=True in the model
    op.create_index("ix_cases_status", "cases", ["status"])
    op.create_index("ix_cases_case_type", "cases", ["case_type"])
    op.create_index("ix_cases_created_at", "cases", ["created_at"])
    op.create_index("ix_cases_client_name", "cases", ["client_name"])

    # File Metadata — frequent lookups by case
    op.create_index("ix_file_metadata_created_at", "file_metadata", ["created_at"])

    # Activity Logs — critical for compliance
    op.create_index("ix_activity_logs_user_id", "activity_logs", ["user_id"])
    op.create_index("ix_activity_logs_action", "activity_logs", ["action"])

    # CRM Clients
    # Note: 'name' already has index=True in the model
    op.create_index("ix_clients_client_type", "clients", ["client_type"])

    # Users
    # Note: 'clerk_id' and 'email' already have index=True in the model
    op.create_index("ix_users_role", "users", ["role"])


def downgrade():
    for idx in [
        "ix_cases_status", "ix_cases_case_type",
        "ix_cases_created_at", "ix_cases_client_name",
        "ix_file_metadata_created_at",
        "ix_activity_logs_user_id", "ix_activity_logs_action",
        "ix_clients_client_type",
        "ix_users_role",
    ]:
        op.drop_index(idx)
