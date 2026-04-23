"""Add indexes for query performance.

Revision ID: 0002_add_indexes
Revises: 0001_init
"""

from alembic import op

revision = "0002_add_indexes"
down_revision = "0001_init"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("ix_sessions_patient_id", "sessions", ["patient_id"])
    op.create_index("ix_gaps_session_id", "gaps", ["session_id"])


def downgrade() -> None:
    op.drop_index("ix_gaps_session_id", table_name="gaps")
    op.drop_index("ix_sessions_patient_id", table_name="sessions")
