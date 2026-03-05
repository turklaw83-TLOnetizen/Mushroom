"""
Add extended case fields — docket number, charges, court, jurisdiction details

Revision ID: 002_case_fields
"""
from alembic import op
import sqlalchemy as sa

revision = "002_case_fields"
down_revision = "001_initial"
branch_labels = None
depends_on = None

_NEW_COLUMNS = [
    ("docket_number", sa.String(128)),
    ("charges", sa.Text),
    ("court_name", sa.String(256)),
    ("date_of_incident", sa.String(32)),
    ("opposing_counsel", sa.String(256)),
    ("jurisdiction_type", sa.String(16)),
    ("county", sa.String(128)),
    ("district", sa.String(128)),
]


def upgrade():
    for col_name, col_type in _NEW_COLUMNS:
        op.add_column("cases", sa.Column(col_name, col_type, server_default="", nullable=True))


def downgrade():
    for col_name, _ in _NEW_COLUMNS:
        op.drop_column("cases", col_name)
