"""Single-process worker; database compare-and-set allows multiple workers."""
import logging
import time
from sqlalchemy import update
from api.db import init_db, SessionLocal, JobRow
from api.jobs import run_one
from api.chain_ops import execute_one
from api.backup import configured as backup_configured, snapshot as backup_snapshot


def main():
    logging.basicConfig(level=logging.INFO)
    init_db()
    next_backup_check = 0.0
    while True:
        # Bound recovery: never blindly replay a blockchain write.
        with SessionLocal() as db:
            db.execute(update(JobRow).where(JobRow.status == "running", JobRow.updated < int(time.time()) - 3600).values(status="failed", error="Worker lease expired; submit a new analysis job."))
            db.commit()
        try:
            execute_one()
            run_one()
            if time.monotonic() >= next_backup_check and backup_configured():
                try:
                    logging.info("Evidence recovery snapshot: %s", backup_snapshot())
                    next_backup_check = time.monotonic() + 86400
                except Exception:
                    logging.exception("Evidence recovery snapshot failed")
                    next_backup_check = time.monotonic() + 3600
            time.sleep(2)
        except Exception:
            logging.exception("Worker iteration failed")
            time.sleep(5)


if __name__ == "__main__":
    main()
