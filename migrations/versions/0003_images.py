"""Persist private image notebook uploads.

Revision ID: 0003
Revises: 0002
"""
from alembic import op
from api.db import ImageRow

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    ImageRow.__table__.create(bind=op.get_bind(), checkfirst=True)


def downgrade():
    raise RuntimeError("DeepSight evidence migrations are forward-only; restore a backup instead")
