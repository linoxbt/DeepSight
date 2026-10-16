"""Track independent human-review resolution.

Revision ID: 0002
Revises: 0001
"""
from alembic import op
from sqlalchemy import inspect

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    if "review_resolution" not in {column["name"] for column in inspect(op.get_bind()).get_columns("claims")}:
        op.execute("ALTER TABLE claims ADD COLUMN review_resolution VARCHAR DEFAULT ''")


def downgrade():
    raise RuntimeError("DeepSight evidence migrations are forward-only; restore a backup instead")
