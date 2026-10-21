"""Keep unsigned draft claims private; preserve already submitted publications.

Revision ID: 0004
Revises: 0003
"""
import json

from alembic import op
from sqlalchemy import inspect, text

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    columns = {column["name"] for column in inspect(connection).get_columns("claims")}
    if "public" not in columns:
        op.execute("ALTER TABLE claims ADD COLUMN public BOOLEAN NOT NULL DEFAULT FALSE")
    indexes = {index["name"] for index in inspect(connection).get_indexes("claims")}
    if "ix_claims_public" not in indexes:
        op.create_index("ix_claims_public", "claims", ["public"])
    # Existing signed submissions have already intentionally published their
    # manifests. Old local-only records must no longer appear anonymously.
    connection.execute(text("UPDATE claims SET public = TRUE WHERE chain_status IS NOT NULL AND chain_status != 'not_submitted'"))
    connection.execute(text("UPDATE artifacts SET public = FALSE"))
    rows = connection.execute(text("SELECT manifest_json FROM claims WHERE public = TRUE")).all()
    for (raw,) in rows:
        document = json.loads(raw)
        refs = list(document.get("artifacts", [])) + list(document.get("cross_matches", []))
        refs.append({"sha256": document.get("analysis", {}).get("environment_sha256")})
        refs.append({"sha256": document.get("archive", {}).get("raw_source_sha256")})
        for ref in refs:
            digest = ref.get("sha256") or ref.get("query_snapshot_sha256")
            if digest:
                connection.execute(text("UPDATE artifacts SET public = TRUE WHERE digest = :digest"), {"digest": digest})


def downgrade():
    raise RuntimeError("DeepSight evidence migrations are forward-only; restore a backup instead")
