"""Add ingestion_jobs.stage for granular progress feedback (UI only, not authoritative)."""

import sqlalchemy as sa

from alembic import op

revision = "0002_ingestion_stage"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("ingestion_jobs", sa.Column("stage", sa.String(length=30), nullable=True))


def downgrade() -> None:
    op.drop_column("ingestion_jobs", "stage")
