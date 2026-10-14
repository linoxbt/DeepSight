"""SQLite persistence for local analyses and claims."""

from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import Integer, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
DATABASE_PATH = Path(os.environ.get("DEEPSIGHT_DB", str(DATA_DIR / "deepsight.db")))
DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
DATABASE_URL = f"sqlite:///{DATABASE_PATH}"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False}, future=True)
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
    payload_json: Mapped[str] = mapped_column(Text)
    series_sha256: Mapped[str] = mapped_column(String)
    created_at: Mapped[str] = mapped_column(String)


class ClaimRow(Base):
    __tablename__ = "claims"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    analysis_id: Mapped[str] = mapped_column(String, index=True)
    manifest_json: Mapped[str] = mapped_column(Text)
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


def _ensure_claim_columns() -> None:
    statements = {
        "challenge_reason": "ALTER TABLE claims ADD COLUMN challenge_reason TEXT DEFAULT ''",
        "challenge_reason_hash": "ALTER TABLE claims ADD COLUMN challenge_reason_hash VARCHAR DEFAULT ''",
        "chain_claim_id": "ALTER TABLE claims ADD COLUMN chain_claim_id VARCHAR DEFAULT ''",
        "chain_status": "ALTER TABLE claims ADD COLUMN chain_status VARCHAR DEFAULT 'not_submitted'",
        "chain_tx": "ALTER TABLE claims ADD COLUMN chain_tx TEXT DEFAULT ''",
        "chain_note": "ALTER TABLE claims ADD COLUMN chain_note TEXT DEFAULT ''",
    }
    with engine.begin() as connection:
        present = {row[1] for row in connection.exec_driver_sql("PRAGMA table_info(claims)")}
        for name, sql in statements.items():
            if name not in present:
                connection.exec_driver_sql(sql)
