"""Single-process worker; database compare-and-set allows multiple workers."""
import logging
import threading
import time
from sqlalchemy import update
from api.db import init_db, SessionLocal, JobRow, ServiceHeartbeat
from api.jobs import run_one
from api.chain_ops import execute_one
from api.backup import configured as backup_configured, snapshot as backup_snapshot, database_snapshot


def main():
    logging.basicConfig(level=logging.INFO)
    init_db()
    def pulse():
        while True:
            try:
                with SessionLocal() as db:
                    db.merge(ServiceHeartbeat(name="worker", updated=int(time.time()), detail="running"))
                    db.commit()
            except Exception:
                logging.exception("Worker heartbeat failed")
            time.sleep(20)
    threading.Thread(target=pulse, daemon=True).start()
    next_evidence_backup = 0.0
    next_database_backup = 0.0
    while True:
        # Bound recovery: never blindly replay a blockchain write.
        with SessionLocal() as db:
            db.execute(update(JobRow).where(JobRow.status == "running", JobRow.updated < int(time.time()) - 3600).values(status="failed", error="Worker lease expired; submit a new analysis job."))
            db.commit()
        try:
            execute_one()
            run_one()
            if backup_configured() and time.monotonic() >= next_database_backup:
                try:
                    database = database_snapshot()
                    with SessionLocal() as db:
                        db.merge(ServiceHeartbeat(name="database_backup", updated=int(time.time()), detail=database["sha256"]))
                        db.commit()
                    logging.info("Database recovery snapshot: date=%s bytes=%s sha256=%s", database["date"], database["bytes"], database["sha256"])
                    next_database_backup = time.monotonic() + 86400
                except Exception:
                    logging.exception("Database recovery snapshot failed")
                    next_database_backup = time.monotonic() + 3600
            # Artifacts are immutable and written before their database rows.
            # Copying them after the database snapshot covers references in it.
            if backup_configured() and time.monotonic() >= next_evidence_backup:
                try:
                    evidence_copy = backup_snapshot()
                    with SessionLocal() as db:
                        db.merge(ServiceHeartbeat(name="evidence_backup", updated=int(time.time()), detail=evidence_copy["date"]))
                        db.commit()
                    logging.info("Evidence recovery snapshot: %s", evidence_copy)
                    next_evidence_backup = time.monotonic() + 86400
                except Exception:
                    logging.exception("Evidence recovery snapshot failed")
                    next_evidence_backup = time.monotonic() + 3600
            time.sleep(2)
        except Exception:
            logging.exception("Worker iteration failed")
            time.sleep(5)


if __name__ == "__main__":
    main()
