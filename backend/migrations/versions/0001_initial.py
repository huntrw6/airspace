"""Initial standalone AirSpace schema.

Revision ID: 0001
Revises: None
"""

from alembic import op

from airspace.database import Base
import airspace.models  # noqa: F401

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # create_all is intentional for the baseline: it is idempotent for early 0.1 databases that
    # predate Alembic, while Alembic records this revision for all subsequent explicit migrations.
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    Base.metadata.drop_all(bind=op.get_bind())
