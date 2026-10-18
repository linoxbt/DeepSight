"""Record worker and backup freshness for readiness diagnostics.

Revision ID: 0005
Revises: 0004
"""
from alembic import op
from api.db import ServiceHeartbeat

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade():
    ServiceHeartbeat.__table__.create(bind=op.get_bind(), checkfirst=True)


def downgrade():
    raise RuntimeError("DeepSight evidence migrations are forward-only; restore a backup instead")
