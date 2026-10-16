"""Single-process worker; database compare-and-set allows multiple workers."""
import logging
import time
from sqlalchemy import update
from api.db import init_db, SessionLocal, JobRow
from api.jobs import run_one
from api.chain_ops import execute_one


def main():
    logging.basicConfig(level=logging.INFO)
    init_db()
    while True:
        # Bound recovery: never blindly replay a blockchain write.
        with SessionLocal() as db:
            db.execute(update(JobRow).where(JobRow.status == "running", JobRow.updated < int(time.time()) - 3600).values(status="failed", error="Worker lease expired; submit a new analysis job."))
            db.commit()
        try:
            execute_one()
            run_one()
            time.sleep(2)
        except Exception:
            logging.exception("Worker iteration failed")
            time.sleep(5)


if __name__ == "__main__":
    main()
