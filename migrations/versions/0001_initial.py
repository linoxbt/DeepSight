"""Initial DeepSight research schema.

Revision ID: 0001
Revises:
"""
from alembic import op
from api.db import Base

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    Base.metadata.create_all(bind=op.get_bind())


def downgrade():
    raise RuntimeError("DeepSight evidence migrations are forward-only; restore a backup instead")
