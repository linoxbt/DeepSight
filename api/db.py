"""SQLite persistence for local analyses and claims."""

from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import Integer, String, Text, create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
DATABASE_PATH = Path(os.environ.get("DEEPSIGHT_DB", str(DATA_DIR / "deepsight.db")))
DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
DATABASE_URL = os.environ.get("DATABASE_URL", f"sqlite:///{DATABASE_PATH}")

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False, "timeout": 30} if DATABASE_URL.startswith("sqlite") else {}, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


class Base(DeclarativeBase):
    pass


class DatasetRow(Base):
    __tablename__ = "datasets"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    tic: Mapped[str] = mapped_column(String, index=True)
    payload_json: Mapped[str] = mapped_column(Text)
    series_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(String)


class AnalysisRow(Base):
    __tablename__ = "analyses"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    target_id: Mapped[str] = mapped_column(String, index=True)
    owner: Mapped[str] = mapped_column(String, default="")
    payload_json: Mapped[str] = mapped_column(Text)
    series_sha256: Mapped[str] = mapped_column(String)
    created_at: Mapped[str] = mapped_column(String)


class ClaimRow(Base):
    __tablename__ = "claims"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    analysis_id: Mapped[str] = mapped_column(String, index=True)
    manifest_json: Mapped[str] = mapped_column(Text)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    __mapper_args__ = {"version_id_col": revision}
    owner: Mapped[str] = mapped_column(String, default="")
    chain_protocol_result: Mapped[str] = mapped_column(String, default="")
    chain_rationale: Mapped[str] = mapped_column(Text, default="")
    chain_execution: Mapped[str] = mapped_column(String, default="")
    manifest_hash: Mapped[str] = mapped_column(String, unique=True, index=True)
    status: Mapped[str] = mapped_column(String)
    protocol_result: Mapped[str] = mapped_column(String, default="")
    rationale: Mapped[str] = mapped_column(Text, default="")
    supersedes: Mapped[str] = mapped_column(String, default="")
    superseded_by: Mapped[str] = mapped_column(String, default="")
    challenge_reason: Mapped[str] = mapped_column(Text, default="")
    challenge_reason_hash: Mapped[str] = mapped_column(String, default="")
    chain_claim_id: Mapped[str] = mapped_column(String, default="")
    chain_status: Mapped[str] = mapped_column(String, default="not_submitted")
    chain_tx: Mapped[str] = mapped_column(Text, default="")
    chain_note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[str] = mapped_column(String)
    updated_at: Mapped[str] = mapped_column(String)


class RadioAnalysisRow(Base):
    __tablename__ = "radio_analyses"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    owner: Mapped[str] = mapped_column(String, default="")
    target_name: Mapped[str] = mapped_column(String, index=True)
    payload_json: Mapped[str] = mapped_column(Text)
    artifact_sha256: Mapped[str] = mapped_column(String)
    created_at: Mapped[str] = mapped_column(String)


class ClaimEventRow(Base):
    __tablename__ = "claim_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    claim_id: Mapped[str] = mapped_column(String, index=True)
    status: Mapped[str] = mapped_column(String)
    note: Mapped[str] = mapped_column(Text)
    observed_at: Mapped[str] = mapped_column(String)


def init_db() -> None:
    Base.metadata.create_all(engine)
    _ensure_claim_columns()
    with engine.begin() as connection:
        for table in ("analyses", "radio_analyses"):
            columns = {col["name"] for col in inspect(connection).get_columns(table)}
            if "owner" not in columns:
                connection.exec_driver_sql(f"ALTER TABLE {table} ADD COLUMN owner VARCHAR DEFAULT ''")


def _ensure_claim_columns() -> None:
    statements = {
        "revision": "ALTER TABLE claims ADD COLUMN revision INTEGER NOT NULL DEFAULT 1",
        "owner": "ALTER TABLE claims ADD COLUMN owner VARCHAR DEFAULT ''",
        "chain_protocol_result": "ALTER TABLE claims ADD COLUMN chain_protocol_result VARCHAR DEFAULT ''",
        "chain_rationale": "ALTER TABLE claims ADD COLUMN chain_rationale TEXT DEFAULT ''",
        "chain_execution": "ALTER TABLE claims ADD COLUMN chain_execution VARCHAR DEFAULT ''",
        "challenge_reason": "ALTER TABLE claims ADD COLUMN challenge_reason TEXT DEFAULT ''",
        "challenge_reason_hash": "ALTER TABLE claims ADD COLUMN challenge_reason_hash VARCHAR DEFAULT ''",
        "chain_claim_id": "ALTER TABLE claims ADD COLUMN chain_claim_id VARCHAR DEFAULT ''",
        "chain_status": "ALTER TABLE claims ADD COLUMN chain_status VARCHAR DEFAULT 'not_submitted'",
        "chain_tx": "ALTER TABLE claims ADD COLUMN chain_tx TEXT DEFAULT ''",
        "chain_note": "ALTER TABLE claims ADD COLUMN chain_note TEXT DEFAULT ''",
    }
    with engine.begin() as connection:
        present = {col["name"] for col in inspect(connection).get_columns("claims")}
        for name, sql in statements.items():
            if name not in present:
                connection.exec_driver_sql(sql)


class AuthChallenge(Base):
    __tablename__ = "auth_challenges"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    address: Mapped[str] = mapped_column(String)
    message: Mapped[str] = mapped_column(Text)
    expires: Mapped[int] = mapped_column(Integer)


class AuthSession(Base):
    __tablename__ = "auth_sessions"
    token_hash: Mapped[str] = mapped_column(String, primary_key=True)
    address: Mapped[str] = mapped_column(String)
    expires: Mapped[int] = mapped_column(Integer)


class JobRow(Base):
    __tablename__ = "jobs"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    owner: Mapped[str] = mapped_column(String, index=True)
    kind: Mapped[str] = mapped_column(String)
    payload: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String, default="queued", index=True)
    result: Mapped[str] = mapped_column(Text, default="")
    error: Mapped[str] = mapped_column(Text, default="")
    created: Mapped[int] = mapped_column(Integer)
    updated: Mapped[int] = mapped_column(Integer)


class ArtifactRow(Base):
    __tablename__ = "artifacts"
    digest: Mapped[str] = mapped_column(String, primary_key=True)
    content: Mapped[str] = mapped_column(Text)
    media_type: Mapped[str] = mapped_column(String, default="application/json")


class ChainIntent(Base):
    __tablename__ = "chain_intents"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    claim_id: Mapped[str] = mapped_column(String, index=True)
    actor: Mapped[str] = mapped_column(String)
    action: Mapped[str] = mapped_column(String)
    message: Mapped[str] = mapped_column(Text)
    payload: Mapped[str] = mapped_column(Text)
    expires: Mapped[int] = mapped_column(Integer)


class ChainOperation(Base):
    __tablename__ = "chain_operations"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    claim_id: Mapped[str] = mapped_column(String, index=True)
    actor: Mapped[str] = mapped_column(String)
    action: Mapped[str] = mapped_column(String)
    stage: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, index=True)
    payload: Mapped[str] = mapped_column(Text)
    authorization: Mapped[str] = mapped_column(Text)
    signature: Mapped[str] = mapped_column(Text)
    tx_hash: Mapped[str] = mapped_column(String, default="")
    error: Mapped[str] = mapped_column(Text, default="")
    updated: Mapped[int] = mapped_column(Integer)
