"""Durable database-backed jobs. Run `python -m api.worker` separately."""
import json
import time
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select, update

from api.auth import current_user
from api.db import JobRow, SessionLocal
from api.limits import rate_limit

router = APIRouter(prefix="/v1/jobs", tags=["jobs"])


class JobIn(BaseModel):
    kind: str = Field(pattern="^(analysis|import|radio)$")
    target_id: str = Field(default="", max_length=80)
    tic: str = Field(default="", max_length=20)


@router.post("", status_code=202)
def enqueue(body: JobIn, request: Request, user: str = Depends(current_user)):
    rate_limit(request, f"jobs:{user}", 30, 3600)
    if body.kind == "analysis" and not body.target_id:
        raise HTTPException(422, "A target is required")
    if body.kind == "import" and not body.tic:
        raise HTTPException(422, "A TIC identifier is required")
    with SessionLocal() as db:
        active = db.scalars(select(JobRow).where(JobRow.owner == user, JobRow.status.in_(("queued", "running")))).all()
        if len(active) >= 3:
            raise HTTPException(429, "Wait for your current jobs to finish")
        job = JobRow(id="job_" + uuid.uuid4().hex, owner=user, kind=body.kind,
                     payload=body.model_dump_json(), created=int(time.time()), updated=int(time.time()))
        db.add(job)
        db.commit()
        return {"id": job.id, "status": job.status}


@router.get("")
def list_jobs(user: str = Depends(current_user)):
    with SessionLocal() as db:
        rows = db.scalars(select(JobRow).where(JobRow.owner == user).order_by(JobRow.created.desc()).limit(100)).all()
        items = []
        for job in rows:
            result = json.loads(job.result) if job.result else {}
            href = ""
            if job.status == "succeeded":
                if job.kind == "analysis":
                    href = f"/lab?analysis={result.get('id', '')}"
                elif job.kind == "import":
                    href = f"/lab?target={result.get('target', {}).get('id', '')}"
                else:
                    href = f"/radio?analysis={result.get('id', '')}"
            items.append({"id": job.id, "kind": job.kind, "status": job.status, "error": job.error, "created": job.created, "href": href})
        return {"jobs": items}


@router.get("/{job_id}")
def read_job(job_id: str, user: str = Depends(current_user)):
    with SessionLocal() as db:
        job = db.get(JobRow, job_id)
        if job is None or job.owner != user:
            raise HTTPException(404, "Job not found")
        return {"id": job.id, "kind": job.kind, "status": job.status,
                "result": json.loads(job.result) if job.result else None, "error": job.error}


def run_one() -> bool:
    from api.main import AnalysisIn, ImportIn, create_analysis, import_dataset, radio_analyze
    with SessionLocal() as db:
        job = db.scalar(select(JobRow).where(JobRow.status == "queued").order_by(JobRow.created).limit(1))
        if job is None:
            return False
        acquired = db.execute(update(JobRow).where(JobRow.id == job.id, JobRow.status == "queued").values(status="running", updated=int(time.time())))
        db.commit()
        if acquired.rowcount != 1:
            return True
        job_id, kind, owner, payload = job.id, job.kind, job.owner, json.loads(job.payload)
    try:
        if kind == "analysis":
            result = create_analysis(AnalysisIn(target_id=payload["target_id"]), user=owner)
        elif kind == "import":
            result = import_dataset(ImportIn(tic=payload["tic"]), user=owner)
        else:
            result = radio_analyze(user=owner)
        status, error = "succeeded", ""
    except Exception as exc:
        result, status = None, "failed"
        error = str(exc.detail) if isinstance(exc, HTTPException) else "Analysis failed. Check worker logs and retry."
        import logging
        logging.exception("Job %s failed", job_id)
    with SessionLocal() as db:
        db.execute(update(JobRow).where(JobRow.id == job_id).values(status=status, result=json.dumps(result) if result else "", error=error, updated=int(time.time())))
        db.commit()
    return True
