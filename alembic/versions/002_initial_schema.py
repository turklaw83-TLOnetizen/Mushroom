"""002 - Initial schema: create all tables.

Revision ID: 002_initial_schema
Revises: 001_indexes
Create Date: 2026-03-01
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "002_initial_schema"
down_revision = None  # First migration; 001_indexes depends on this
branch_labels = None
depends_on = None


def upgrade():
    # ---- Cases ----
    op.create_table(
        "cases",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("name", sa.String(512), nullable=False),
        sa.Column("description", sa.Text, server_default=""),
        sa.Column("case_type", sa.String(64), server_default="criminal"),
        sa.Column("case_category", sa.String(128), server_default=""),
        sa.Column("case_subcategory", sa.String(128), server_default=""),
        sa.Column("client_name", sa.String(256), server_default=""),
        sa.Column("jurisdiction", sa.String(256), server_default=""),
        sa.Column("phase", sa.String(32), server_default="active"),
        sa.Column("sub_phase", sa.String(128), server_default=""),
        sa.Column("status", sa.String(32), server_default="active"),
        sa.Column("pinned", sa.Boolean, server_default=sa.false()),
        sa.Column("purged", sa.Boolean, server_default=sa.false()),
        sa.Column("purged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("purged_file_count", sa.Integer, server_default="0"),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("assigned_to", JSONB, server_default="[]"),
        sa.Column("metadata_extra", JSONB, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("last_updated", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ---- Preparations ----
    op.create_table(
        "preparations",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("case_id", sa.String(64), sa.ForeignKey("cases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(256), server_default=""),
        sa.Column("prep_type", sa.String(64), nullable=False, server_default="trial"),
        sa.Column("state", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("last_updated", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ---- Snapshots ----
    op.create_table(
        "snapshots",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("case_id", sa.String(64), sa.ForeignKey("cases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("prep_id", sa.String(64), sa.ForeignKey("preparations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("state", JSONB, nullable=True),
        sa.Column("snapshot_metadata", JSONB, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ---- Activity Logs ----
    op.create_table(
        "activity_logs",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("case_id", sa.String(64), sa.ForeignKey("cases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("action", sa.String(128), nullable=False),
        sa.Column("description", sa.Text, server_default=""),
        sa.Column("user_id", sa.String(64), server_default=""),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ---- File Metadata ----
    op.create_table(
        "file_metadata",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("case_id", sa.String(64), sa.ForeignKey("cases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("filename", sa.String(512), nullable=False),
        sa.Column("disk_path", sa.Text, nullable=False),
        sa.Column("file_size", sa.Integer, server_default="0"),
        sa.Column("tags", JSONB, server_default="[]"),
        sa.Column("sort_order", sa.Integer, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("case_id", "filename", name="uq_case_file"),
    )

    # ---- Module Notes ----
    op.create_table(
        "module_notes",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("case_id", sa.String(64), sa.ForeignKey("cases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("prep_id", sa.String(64), sa.ForeignKey("preparations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("module_name", sa.String(128), nullable=False),
        sa.Column("content", sa.Text, server_default=""),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("case_id", "prep_id", "module_name", name="uq_module_note"),
    )

    # ---- Clients ----
    op.create_table(
        "clients",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("client_type", sa.String(64), server_default="prospective"),
        sa.Column("contact_info", JSONB, server_default="{}"),
        sa.Column("intake_data", JSONB, server_default="{}"),
        sa.Column("notes", sa.Text, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ---- Case-Client Link ----
    op.create_table(
        "case_clients",
        sa.Column("case_id", sa.String(64), sa.ForeignKey("cases.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("client_id", sa.String(64), sa.ForeignKey("clients.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("linked_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ---- Users ----
    op.create_table(
        "users",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("clerk_id", sa.String(256), unique=True, nullable=True),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("initials", sa.String(8), server_default=""),
        sa.Column("email", sa.String(256), server_default=""),
        sa.Column("role", sa.String(32), server_default="attorney"),
        sa.Column("is_active", sa.Boolean, server_default=sa.true()),
        sa.Column("pin_hash", sa.String(128), server_default=""),
        sa.Column("google_email", sa.String(256), server_default=""),
        sa.Column("google_sub", sa.String(256), server_default=""),
        sa.Column("assigned_cases", JSONB, server_default="[]"),
        sa.Column("last_login", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ---- Global Settings ----
    op.create_table(
        "global_settings",
        sa.Column("key", sa.String(256), primary_key=True),
        sa.Column("value", JSONB, nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ---- Case JSON Data ----
    op.create_table(
        "case_json_data",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("case_id", sa.String(64), sa.ForeignKey("cases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("filename", sa.String(256), nullable=False),
        sa.Column("data", JSONB, nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("case_id", "filename", name="uq_case_json"),
    )

    # ---- Prep JSON Data ----
    op.create_table(
        "prep_json_data",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("case_id", sa.String(64), sa.ForeignKey("cases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("prep_id", sa.String(64), sa.ForeignKey("preparations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("filename", sa.String(256), nullable=False),
        sa.Column("data", JSONB, nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("case_id", "prep_id", "filename", name="uq_prep_json"),
    )

    # ---- Case Text Data ----
    op.create_table(
        "case_text_data",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("case_id", sa.String(64), sa.ForeignKey("cases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("filename", sa.String(256), nullable=False),
        sa.Column("content", sa.Text, server_default=""),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("case_id", "filename", name="uq_case_text"),
    )

    # ---- Prep Text Data ----
    op.create_table(
        "prep_text_data",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("case_id", sa.String(64), sa.ForeignKey("cases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("prep_id", sa.String(64), sa.ForeignKey("preparations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("filename", sa.String(256), nullable=False),
        sa.Column("content", sa.Text, server_default=""),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("case_id", "prep_id", "filename", name="uq_prep_text"),
    )

    # ---- Tenants (Phase 22 — Multi-Tenancy) ----
    op.create_table(
        "tenants",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("slug", sa.String(128), unique=True, nullable=False),
        sa.Column("plan", sa.String(32), server_default="starter"),
        sa.Column("max_users", sa.Integer, server_default="5"),
        sa.Column("max_cases", sa.Integer, server_default="50"),
        sa.Column("max_storage_gb", sa.Float, server_default="10.0"),
        sa.Column("features", JSONB, server_default="{}"),
        sa.Column("branding", JSONB, server_default="{}"),
        sa.Column("sso_config", JSONB, server_default="{}"),
        sa.Column("is_active", sa.Boolean, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Add tenant_id to cases and users
    op.add_column("cases", sa.Column("tenant_id", sa.String(64), nullable=True))
    op.add_column("users", sa.Column("tenant_id", sa.String(64), nullable=True))


def downgrade():
    op.drop_column("users", "tenant_id")
    op.drop_column("cases", "tenant_id")
    op.drop_table("tenants")
    op.drop_table("prep_text_data")
    op.drop_table("case_text_data")
    op.drop_table("prep_json_data")
    op.drop_table("case_json_data")
    op.drop_table("global_settings")
    op.drop_table("users")
    op.drop_table("case_clients")
    op.drop_table("clients")
    op.drop_table("module_notes")
    op.drop_table("file_metadata")
    op.drop_table("activity_logs")
    op.drop_table("snapshots")
    op.drop_table("preparations")
    op.drop_table("cases")
