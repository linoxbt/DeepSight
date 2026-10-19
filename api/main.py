"""DeepSight local research API.

Astronomy stays here. GenLayer, when a contract is later configured, only
receives the manifest hash and the policy outcome.
"""

from __future__ import annotations

import json
import os
import subprocess
import hashlib
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any

import numpy as np
from fastapi import FastAPI, HTTPException, Depends, Response, Request, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import select, and_, or_, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import StaleDataError
from fastapi.responses import JSONResponse

from api.archives import ArchiveError, query_gaia, query_horizons, resolve_cross_match
from api.catalogue import CATALOGUE_VERSION, REFERENCE_CATALOGUE
from api import chain, evidence
from api.auth import router as auth_router, current_user, optional_user, require_owner, require_reviewer, origin
from api.db import AnalysisRow, AttestationRow, ClaimEventRow, ClaimRow, DatasetRow, RadioAnalysisRow, ServiceHeartbeat, SessionLocal, init_db
from api.manifest import build_manifest, canonicalize, sha256_text
from api.limits import rate_limit
from api.mast import MastError, fetch_tess_light_curve, normalize_tic
from api.policy import POLICY_CELESTIAL, RESULT_REVIEW, evaluate
from api.radio import analyze_tutorial, build_radio_manifest, search_catalog
from api.science import PIPELINE_NAME, PIPELINE_VERSION, fit_transit, fold, quality_flags, synthetic_series
from api.targets import TARGETS, get_target

@asynccontextmanager
async def _lifespan(_app: FastAPI):
    init_db()
    yield


app = FastAPI(title="DeepSight", version="0.1.0", lifespan=_lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


from api.chain_ops import router as chain_router, idle as require_chain_idle, config_for_claim
app.include_router(chain_router)
from api.jobs import router as jobs_router
app.include_router(jobs_router)
from api.images import router as images_router
app.include_router(images_router)
@app.exception_handler(StaleDataError)
async def stale_claim(_request, _error):
    return JSONResponse(status_code=409, content={"detail": "Claim changed concurrently. Refresh before retrying."})


@app.exception_handler(IntegrityError)
async def duplicate_record(_request, _error):
    return JSONResponse(status_code=409, content={"detail": "This record already exists or conflicts with another request."})


app.include_router(auth_router)
app.include_router(evidence.router)


class SearchIn(BaseModel):
    query: str = ""


class AnalysisIn(BaseModel):
    target_id: str = Field(min_length=1, max_length=80)


class ImportIn(BaseModel):
    tic: str = Field(min_length=1, max_length=20)


class ClaimIn(BaseModel):
    analysis_id: str
    acknowledged: bool = False
    submission_mode: str = Field(default="wallet", pattern="^(wallet|relay)$")


class PublishIn(BaseModel):
    acknowledged: bool = False


class TapIn(BaseModel):
    tic: str = ""
    hostname: str = ""
    ra_deg: float | None = None
    dec_deg: float | None = None


class GaiaIn(BaseModel):
    ra_deg: float
    dec_deg: float
    radius_arcsec: float = 36


class HorizonsIn(BaseModel):
    command: str = Field(min_length=1, max_length=48)


class RadioSearchIn(BaseModel):
    target: str = Field(min_length=1, max_length=40)


class ChallengeIn(BaseModel):
    reason: str = Field(min_length=20, max_length=400)


class ReviewNoteIn(BaseModel):
    note: str = Field(min_length=8, max_length=500)
    decision: str = Field(pattern="^(supports_evidence|requests_revision|inconclusive)$")
    conflict_disclosure: str = Field(min_length=4, max_length=500)


class AppealIn(BaseModel):
    tx_hash: str = Field(min_length=4, max_length=80)


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _git_commit() -> str:
    configured = os.environ.get("DEEPSIGHT_GIT_COMMIT", "") or os.environ.get("RAILWAY_GIT_COMMIT_SHA", "")
    if len(configured) in (40, 64) and all(character in "0123456789abcdefABCDEF" for character in configured):
        return configured.lower()
    try:
        revision = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=__file__ and str(__import__("pathlib").Path(__file__).resolve().parent.parent),
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
        if revision:
            return revision
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    # CLI-built Railway images omit .git. An immutable source fingerprint is
    # still verifiable against the environment artifact, unlike "unversioned".
    source = evidence.environment()["source_checksums"]
    digest = hashlib.sha256(json.dumps(source, sort_keys=True).encode()).hexdigest()
    return f"source-sha256:{digest}"


def _public_target(target: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": target["id"],
        "name": target["name"],
        "synthetic": bool(target["synthetic"]),
        "archive": target["archive"],
        "observation_id": target["observation_id"],
        "ra_deg": target["ra_deg"],
        "dec_deg": target["dec_deg"],
        "summary": target["summary"],
        "tic": target.get("tic"),
        "sector": target.get("sector"),
        "raw_sha256": target.get("raw_sha256"),
        "raw_uri": target.get("raw_uri"),
    }


def _dataset_targets(session) -> list[dict[str, Any]]:
    rows = session.scalars(select(DatasetRow).order_by(DatasetRow.created_at.desc())).all()
    return [json.loads(row.payload_json) for row in rows]


def _bin_series(time: np.ndarray, flux: np.ndarray, bins: int = 280) -> tuple[list[float], list[float]]:
    edges = np.linspace(float(time[0]), float(time[-1]) + 1e-9, bins + 1)
    centers: list[float] = []
    values: list[float] = []
    for start, stop in zip(edges[:-1], edges[1:]):
        selected = flux[(time >= start) & (time < stop)]
        if selected.size == 0:
            continue
        centers.append(round(float((start + stop) / 2.0), 5))
        values.append(round(float(np.mean(selected)), 6))
    return centers, values


def _analysis_or_404(session, analysis_id: str) -> AnalysisRow:
    row = session.get(AnalysisRow, analysis_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return row


def _claim_or_404(session, claim_id: str) -> ClaimRow:
    row = session.get(ClaimRow, claim_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Claim not found")
    return row


def _visible_claim(session, claim_id: str, viewer: str | None) -> ClaimRow:
    row = _claim_or_404(session, claim_id)
    if not row.public and row.owner != viewer:
        raise HTTPException(404, "Claim not found")
    return row


def _chain_note_default() -> str:
    if chain.configured():
        return "This record has not been submitted to GenLayer."
    return "No GenLayer contract address is configured. This record is a local protocol preview."


def _add_event(session, claim_id: str, status: str, note: str) -> None:
    session.add(ClaimEventRow(claim_id=claim_id, status=status, note=note, observed_at=_now()))


def _claim_out(row: ClaimRow) -> dict[str, Any]:
    manifest = json.loads(row.manifest_json)
    summary_metrics = {
        "period_days" if item["name"] == "period" else item["name"]: {
            "value": item["value"], "unit": item.get("unit", "")
        }
        for item in manifest.get("metrics", [])
        if item.get("name") in {"period", "depth", "snr_proxy"}
    }
    return {
        "id": row.id,
        "analysis_id": row.analysis_id,
        "owner": row.owner,
        "submission_mode": "wallet" if manifest.get("claimant_address", "").lower() == row.owner else "relay",
        "public": row.public,
        "chain_protocol_result": row.chain_protocol_result,
        "chain_rationale": row.chain_rationale,
        "chain_execution": row.chain_execution,
        "manifest_hash": row.manifest_hash,
        "claim_type": manifest["claim_type"],
        "policy_version": manifest["policy_version"],
        "scientific_status": manifest["scientific_status"],
        "target_id": manifest["target"]["id"],
        "target_name": manifest["target"].get("name", manifest["target"]["id"]),
        "archive_name": manifest.get("archive", {}).get("name", ""),
        "summary_metrics": summary_metrics,
        "status": row.status,
        "protocol_result": row.protocol_result,
        "rationale": row.rationale,
        "supersedes": row.supersedes,
        "superseded_by": row.superseded_by,
        "challenge_reason_hash": row.challenge_reason_hash or "",
        "chain_claim_id": row.chain_claim_id or "",
        "chain_contract_address": (config_for_claim(row) or {}).get("address", ""),
        "chain_status": row.chain_status or "not_submitted",
        "chain_tx": row.chain_tx or "",
        "chain_note": row.chain_note or _chain_note_default(),
        "review_resolution": row.review_resolution or "pending",
        "scientific_confirmation": False,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


init_db()


@app.get("/v1/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "scope": "api_process_only",
        "service": "deepsight",
        "pipeline": PIPELINE_NAME,
        "pipeline_version": PIPELINE_VERSION,
        "live_archive": True,
        "archive_reachability": "unverified",
        "mast_light_curve_import": True,
        "exoplanet_tap": True,
        "gaia": True,
        "jpl_horizons": True,
        "breakthrough_listen": True,
        "radio_pipeline": "radio-mad-v1",
        "genlayer_configured": chain.configured(),
        "policy": POLICY_CELESTIAL,
    }


@app.get("/v1/ready")
def readiness(response: Response) -> dict[str, Any]:
    """Dependency readiness; liveness stays separate for platform restarts."""
    now = int(time.time())
    checks = {"database": False, "worker": False, "object_store": False,
              "database_backup": False, "evidence_backup": False}
    try:
        with SessionLocal() as session:
            session.execute(text("SELECT 1"))
            checks["database"] = True
            beats = {row.name: row.updated for row in session.scalars(select(ServiceHeartbeat)).all()}
        checks["worker"] = now - beats.get("worker", 0) < 120
        for name in ("database_backup", "evidence_backup"):
            checks[name] = now - beats.get(name, 0) < 36 * 3600
    except Exception:
        pass
    try:
        store = evidence._object_store()
        if store:
            client, bucket = store
            client.head_bucket(Bucket=bucket)
            checks["object_store"] = True
        else:
            checks["object_store"] = os.environ.get("DEEPSIGHT_REQUIRE_OBJECT_STORE") != "1"
    except Exception:
        pass
    required = ["database", "worker", "object_store"]
    if os.environ.get("DEEPSIGHT_REQUIRE_OBJECT_STORE") == "1":
        required += ["database_backup", "evidence_backup"]
    ready = all(checks[key] for key in required)
    if not ready:
        response.status_code = 503
    return {"status": "ok" if ready else "degraded", "checks": checks}


@app.get("/v1/sources")
def sources() -> dict[str, Any]:
    return {
        "live_archive": True,
        "archive_reachability": "unverified",
        "sources": [
            {"id": "local-synthetic", "name": "DeepSight synthetic calibration", "connected": True},
            {"id": "mast", "name": "STScI MAST — one TESS sector light curve", "connected": None},
            {"id": "exoplanet-archive", "name": "NASA Exoplanet Archive TAP (pscomppars)", "connected": None},
            {"id": "gaia", "name": "ESA Gaia DR3 TAP", "connected": None},
            {"id": "jpl", "name": "JPL Horizons", "connected": None},
            {"id": "breakthrough-listen", "name": "Breakthrough Listen open-data catalog", "connected": None},
            {"id": "genlayer", "name": "GenLayer StudioNet", "connected": None if chain.configured() else False},
        ],
    }


@app.get("/v1/catalogue")
def catalogue() -> dict[str, Any]:
    return {
        "live_query": False,
        "catalogue": "NASA Exoplanet Archive",
        "version": CATALOGUE_VERSION,
        "note": "This table is the local fallback extract. Live cross-matches use NASA TAP when DEEPSIGHT_LIVE_TAP is left on.",
        "rows": REFERENCE_CATALOGUE,
    }


@app.get("/v1/targets")
def targets() -> dict[str, Any]:
    with SessionLocal() as session:
        imported = _dataset_targets(session)
    return {
        "live_archive": False,
        "mast_light_curve_import": True,
        "targets": [_public_target(item) for item in [*imported, *TARGETS]],
    }


@app.post("/v1/datasets/import")
def import_dataset(body: ImportIn, request: Request = None, user: str = Depends(current_user)) -> dict[str, Any]:
    if request is not None:
        rate_limit(request, f"direct-import:{user}", 3, 3600)
        rate_limit(request, "direct-import-global", 30, 3600, global_scope=True)
    try:
        tic = normalize_tic(body.tic)
    except MastError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    dataset_id = f"TIC-{tic}"
    with SessionLocal() as session:
        existing = session.get(DatasetRow, dataset_id)
        if existing is not None and json.loads(existing.payload_json).get("raw_sha256"):
            return {"cached": True, "target": json.loads(existing.payload_json)}
    try:
        curve = fetch_tess_light_curve(tic, cache_dir=_mast_cache())
    except MastError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    if curve.get("raw_path"):
        curve["raw_sha256"] = evidence.put_fits(__import__("pathlib").Path(curve["raw_path"]))
        curve["raw_uri"] = f"/v1/raw/{curve['raw_sha256']}"
    public = _public_target(curve)
    public.update(
        {
            "btjd_start": curve["btjd_start"],
            "n_kept": curve["n_kept"],
            "n_raw": curve["n_raw"],
            "exposure_seconds": curve.get("exposure_seconds"),
            "product_filename": curve.get("product_filename"),
            "data_uri": curve.get("data_uri"),
        }
    )
    record = DatasetRow(
        id=dataset_id,
        tic=tic,
        payload_json=json.dumps(public),
        series_json=json.dumps({"time_days": curve["time_days"], "flux": curve["flux"]}),
        created_at=_now(),
    )
    with SessionLocal() as session:
        existing = session.get(DatasetRow, dataset_id)
        if existing is not None:
            existing.payload_json = record.payload_json
            existing.series_json = record.series_json
        else:
            session.add(record)
        try:
            session.commit()
        except IntegrityError:
            session.rollback()
            existing = session.get(DatasetRow, dataset_id)
            if existing is None:
                raise
            return {"cached": True, "target": json.loads(existing.payload_json)}
    return {"cached": False, "target": public}


@app.post("/v1/datasets/search")
def search_datasets(body: SearchIn) -> dict[str, Any]:
    query = body.query.strip().lower()
    with SessionLocal() as session:
        available = [*_dataset_targets(session), *TARGETS]
    rows = []
    for target in available:
        haystack = " ".join(
            str(part)
            for part in (target["id"], target["name"], target["summary"], target.get("tic") or "")
        ).lower()
        if query and query not in haystack:
            continue
        rows.append(_public_target(target))
    return {
        "live_archive": False,
        "note": "Search covers local calibration targets and light curves already imported from MAST. TAP is not queried.",
        "results": rows,
    }


def _mast_cache():
    from api.db import DATA_DIR

    return DATA_DIR / "cache" / "mast"


def _load_curve(target_id: str) -> tuple[dict[str, Any], np.ndarray, np.ndarray]:
    builtin = get_target(target_id)
    if builtin is not None:
        time, flux = synthetic_series(
            period_days=builtin["injected_period_days"],
            depth=builtin["injected_depth"],
            duration_days=builtin["injected_duration_days"],
            seed=builtin["seed"],
        )
        return builtin, time, flux
    with SessionLocal() as session:
        row = session.get(DatasetRow, target_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Unknown target")
        target = json.loads(row.payload_json)
        series = json.loads(row.series_json)
    return target, np.asarray(series["time_days"], dtype=float), np.asarray(series["flux"], dtype=float)


@app.post("/v1/analyses")
def create_analysis(body: AnalysisIn, request: Request = None, user: str = Depends(current_user)) -> dict[str, Any]:
    if request is not None:
        rate_limit(request, f"direct-analysis:{user}", 3, 3600)
        rate_limit(request, "direct-analysis-global", 30, 3600, global_scope=True)
    target, time, flux = _load_curve(body.target_id)
    series = {"time_days": time.tolist(), "flux": flux.tolist()}
    series_sha = evidence.put_json(series, owner=user)
    environment_sha = evidence.put_json(evidence.environment(), owner=user)
    fit = fit_transit(time, flux)
    match = resolve_cross_match(
        target["id"],
        fit.period_days,
        tic=target.get("tic"),
        ra=target.get("ra_deg"),
        dec=target.get("dec_deg"),
    )
    flags = quality_flags(fit, synthetic=bool(target["synthetic"]), cross_match_result=match["result"])
    if not target["synthetic"]:
        flags.append(
            {
                "code": "archive_pdcsap",
                "severity": "info",
                "message": "Flux is the archive PDCSAP product with quality flag 0. DeepSight did not re-reduce the pixels.",
            }
        )
    snapshot_rows = match.get("tap_rows") if match.get("live_query") else REFERENCE_CATALOGUE
    snapshot = evidence.put_json(
            {
                "catalogue_version": match.get("catalogue_version", CATALOGUE_VERSION),
                "rows": snapshot_rows,
                "query": {"target_id": target["id"], "period_days": round(fit.period_days, 6)},
            }, owner=user
    )
    match = {**match, "query_snapshot_sha256": snapshot}
    folded = fold(time, flux, fit.period_days, fit.t0_days)
    plot_time, plot_flux = _bin_series(time, flux)
    payload = {
        "target": _public_target(target),
        "pipeline": {"name": PIPELINE_NAME, "version": PIPELINE_VERSION, "git_commit": _git_commit(), "environment_sha256": environment_sha},
        "metrics": {
            "period_days": round(fit.period_days, 6),
            "period_uncertainty_days": None if fit.bootstrap_uncertainty_days is None else round(fit.bootstrap_uncertainty_days, 6),
            "period_resolution_days": round(fit.period_uncertainty_days, 6),
            "t0_days": round(fit.t0_days, 6),
            "duration_days": round(fit.duration_days, 6),
            "depth": round(fit.depth, 6),
            "snr_proxy": round(fit.snr_proxy, 3),
            "odd_even_delta": round(fit.odd_even_delta, 4),
            "secondary_depth": round(fit.secondary_depth, 6),
            "n_in_transit": fit.n_in_transit,
            "n_samples": int(time.size),
        },
        "quality_flags": flags,
        "false_positive_tests": [
            {
                "name": "odd_even",
                "delta": round(fit.odd_even_delta, 4),
                "note": "Relative difference between odd and even transit depths.",
            },
            {
                "name": "secondary_eclipse",
                "depth": round(fit.secondary_depth, 6),
                "note": "Median dip in a box centered at phase 0.5.",
            },
        ],
        "cross_match": match,
        "series_plot": {"time_days": plot_time, "flux": plot_flux},
        "folded": folded,
        "periodogram": {"period_days": fit.periodogram_period, "power": fit.periodogram_power},
        "limitations": _limitations(target),
    }
    analysis_id = "an_" + uuid.uuid4().hex[:12]
    record = AnalysisRow(
        id=analysis_id,
        target_id=target["id"],
        owner=user,
        payload_json=json.dumps(payload),
        series_sha256=series_sha,
        created_at=_now(),
    )
    with SessionLocal() as session:
        session.add(record)
        session.commit()
    return {"id": analysis_id, "series_sha256": series_sha, **payload}


@app.get("/v1/analyses/{analysis_id}")
def read_analysis(analysis_id: str, user: str = Depends(current_user)) -> dict[str, Any]:
    with SessionLocal() as session:
        row = _analysis_or_404(session, analysis_id)
        require_owner(row, user)
        payload = json.loads(row.payload_json)
    return {"id": row.id, "series_sha256": row.series_sha256, "created_at": row.created_at, **payload}


@app.post("/v1/evidence/preflight")
def preflight(body: ClaimIn, user: str = Depends(current_user)) -> dict[str, Any]:
    with SessionLocal() as session:
        row = _analysis_or_404(session, body.analysis_id)
        require_owner(row, user)
        payload = json.loads(row.payload_json)
        manifest = build_manifest(
            target=payload["target"],
            fit=payload["metrics"],
            series_sha256=row.series_sha256,
            analysis_id=row.id,
            claimant_address=(user if body.submission_mode == "wallet" else os.environ.get("DEEPSIGHT_RELAY_ADDRESS", "")).lower(),
            researcher_address=user,
            cross_match=payload["cross_match"],
            snapshot_sha256=payload["cross_match"]["query_snapshot_sha256"],
            git_commit=payload["pipeline"]["git_commit"],
            environment_sha256=payload["pipeline"].get("environment_sha256", ""),
            diagnostics=payload["false_positive_tests"],
            quality_flags=payload["quality_flags"],
        )
    items = _checklist(manifest, payload)
    blockers = [item for item in items if item["status"] == "fail"]
    return {
        "ready": len(blockers) == 0,
        "items": items,
        "note": "Passing preflight does not confirm a planet. Synthetic provenance stays in human review.",
    }


@app.post("/v1/claims")
def create_claim(body: ClaimIn, user: str = Depends(current_user)) -> dict[str, Any]:
    if not body.acknowledged:
        raise HTTPException(
            status_code=422,
            detail="Acknowledge that protocol review is not a scientific confirmation",
        )
    if body.submission_mode == "relay" and not os.environ.get("DEEPSIGHT_RELAY_ADDRESS", ""):
        raise HTTPException(503, "Relay wallet is not configured; create a wallet-owned claim")
    with SessionLocal() as session:
        analysis = _analysis_or_404(session, body.analysis_id)
        require_owner(analysis, user)
        payload = json.loads(analysis.payload_json)
        target = payload["target"]
        manifest = build_manifest(
            target=target,
            fit=payload["metrics"],
            series_sha256=analysis.series_sha256,
            analysis_id=analysis.id,
            claimant_address=os.environ.get("DEEPSIGHT_RELAY_ADDRESS", user).lower(),
            researcher_address=user,
            cross_match=payload["cross_match"],
            snapshot_sha256=payload["cross_match"]["query_snapshot_sha256"],
            git_commit=payload["pipeline"]["git_commit"],
            environment_sha256=payload["pipeline"].get("environment_sha256", ""),
            diagnostics=payload["false_positive_tests"],
            quality_flags=payload["quality_flags"],
        )
        checklist = _checklist(manifest, payload)
        if any(item["status"] == "fail" for item in checklist):
            raise HTTPException(status_code=422, detail="Evidence preflight has blocking items")
        text = canonicalize(manifest)
        digest = sha256_text(text)
        existing = session.scalar(select(ClaimRow).where(ClaimRow.manifest_hash == digest))
        if existing is not None:
            raise HTTPException(status_code=409, detail=f"Manifest already claimed as {existing.id}")
        now = _now()
        claim = ClaimRow(
            id="clm_" + uuid.uuid4().hex[:12],
            analysis_id=analysis.id,
            manifest_json=text,
            owner=user,
            manifest_hash=digest,
            status="EVIDENCE_READY",
            created_at=now,
            updated_at=now,
        )
        session.add(claim)
        _add_event(session, claim.id, "EVIDENCE_READY", "Canonical manifest stored locally. Not submitted to GenLayer.")
        session.commit()
        session.refresh(claim)
        return {**_claim_out(claim), "manifest": manifest, "checklist": checklist}


@app.post("/v1/claims/{claim_id}/publish")
def publish_claim(claim_id: str, body: PublishIn, user: str = Depends(current_user)) -> dict[str, Any]:
    if not body.acknowledged:
        raise HTTPException(422, "Acknowledge that the manifest, evidence, and wallet address become public")
    with SessionLocal() as session:
        claim = _claim_or_404(session, claim_id)
        require_owner(claim, user)
        if claim.status in ("RETRACTED", "SUPERSEDED"):
            raise HTTPException(409, "This claim cannot be published in its current state")
        if not claim.public:
            evidence.publish_manifest(session, json.loads(claim.manifest_json))
            claim.public = True
            _add_event(session, claim.id, "PUBLISHED", "Owner explicitly published the claim and its evidence.")
            session.commit()
        return _claim_out(claim)


@app.post("/v1/claims/{claim_id}/review-request")
def review_claim(claim_id: str, user: str = Depends(current_user)) -> dict[str, Any]:
    with SessionLocal() as session:
        claim = _claim_or_404(session, claim_id)
        require_owner(claim, user)
        require_chain_idle(session, claim_id)
        if claim.chain_claim_id:
            raise HTTPException(409, "Use the finalized chain policy result for this claim")
        if claim.status != "EVIDENCE_READY":
            raise HTTPException(status_code=409, detail=f"Cannot review a claim in status {claim.status}")
        manifest = json.loads(claim.manifest_json)
        result, rationale = evaluate(claim.manifest_json, manifest["claim_type"], manifest["policy_version"], manifest["target"]["id"])
        claim.protocol_result = result
        claim.rationale = rationale
        claim.status = "NEEDS_REVIEW" if result == RESULT_REVIEW else "FINALIZED"
        claim.updated_at = _now()
        _add_event(
            session,
            claim.id,
            claim.status,
            f"Local policy preview returned {result}. This is not a GenLayer transaction.",
        )
        session.commit()
        session.refresh(claim)
        return _claim_out(claim)


@app.post("/v1/claims/{claim_id}/supersede")
def supersede_claim(claim_id: str, user: str = Depends(current_user)) -> dict[str, Any]:
    with SessionLocal() as session:
        claim = _claim_or_404(session, claim_id)
        require_owner(claim, user)
        require_chain_idle(session, claim_id)
        if claim.chain_claim_id:
            raise HTTPException(409, "Chain-linked claims require a chain supersession job")
        if claim.status not in ("FINALIZED", "NEEDS_REVIEW", "CHALLENGED"):
            raise HTTPException(status_code=409, detail=f"Cannot supersede a claim in status {claim.status}")
        manifest = json.loads(claim.manifest_json)
        manifest["supersedes"] = claim.manifest_hash
        text = canonicalize(manifest)
        digest = sha256_text(text)
        now = _now()
        replacement = ClaimRow(
            id="clm_" + uuid.uuid4().hex[:12],
            analysis_id=claim.analysis_id,
            manifest_json=text,
            owner=user,
            manifest_hash=digest,
            status="EVIDENCE_READY",
            supersedes=claim.id,
            created_at=now,
            updated_at=now,
        )
        claim.status = "SUPERSEDED"
        claim.superseded_by = replacement.id
        claim.updated_at = now
        session.add(replacement)
        _add_event(session, claim.id, "SUPERSEDED", f"Superseded by {replacement.id}")
        _add_event(session, replacement.id, "EVIDENCE_READY", f"Replacement for {claim.id}. Policy review has not been run.")
        session.commit()
        session.refresh(replacement)
        return _claim_out(replacement)


@app.get("/v1/claims")
def list_claims(limit: int = Query(50, ge=1, le=100), cursor: str = "", viewer: str | None = Depends(optional_user)) -> dict[str, Any]:
    with SessionLocal() as session:
        visibility = or_(ClaimRow.public.is_(True), ClaimRow.owner == viewer) if viewer else ClaimRow.public.is_(True)
        statement = select(ClaimRow).where(visibility)
        if cursor:
            previous = session.scalar(select(ClaimRow).where(ClaimRow.id == cursor, visibility))
            if previous is None:
                raise HTTPException(422, "Invalid claim cursor")
            statement = statement.where(or_(ClaimRow.created_at < previous.created_at,
                                            and_(ClaimRow.created_at == previous.created_at, ClaimRow.id < previous.id)))
        rows = session.scalars(statement.order_by(ClaimRow.created_at.desc(), ClaimRow.id.desc()).limit(limit + 1)).all()
        page = rows[:limit]
        return {"claims": [_claim_out(row) for row in page], "next_cursor": page[-1].id if len(rows) > limit else None}


@app.get("/v1/claims/{claim_id}")
def read_claim(claim_id: str, viewer: str | None = Depends(optional_user)) -> dict[str, Any]:
    with SessionLocal() as session:
        claim = _visible_claim(session, claim_id, viewer)
        manifest = json.loads(claim.manifest_json)
        return {**_claim_out(claim), "manifest": manifest}


@app.get("/v1/claims/{claim_id}/policy-result")
def policy_result(claim_id: str, viewer: str | None = Depends(optional_user)) -> dict[str, Any]:
    with SessionLocal() as session:
        claim = _visible_claim(session, claim_id, viewer)
        return {
            "claim_id": claim.id,
            "protocol_result": claim.protocol_result or None,
            "rationale": claim.rationale,
            "scientific_status": json.loads(claim.manifest_json)["scientific_status"],
            "scientific_confirmation": False,
            "on_chain": bool(claim.chain_claim_id),
            "chain_protocol_result": claim.chain_protocol_result or None,
            "chain_rationale": claim.chain_rationale,
        }


@app.get("/v1/claims/{claim_id}/timeline")
def timeline(claim_id: str, viewer: str | None = Depends(optional_user)) -> dict[str, Any]:
    with SessionLocal() as session:
        _visible_claim(session, claim_id, viewer)
        events = session.scalars(
            select(ClaimEventRow).where(ClaimEventRow.claim_id == claim_id).order_by(ClaimEventRow.id)
        ).all()
        return {
            "claim_id": claim_id,
            "events": [
                {"status": event.status, "note": event.note, "observed_at": event.observed_at}
                for event in events
            ],
        }


@app.get("/v1/claims/{claim_id}/finality")
def finality(claim_id: str, viewer: str | None = Depends(optional_user)) -> dict[str, Any]:
    with SessionLocal() as session:
        claim = _visible_claim(session, claim_id, viewer)
        chain_status = claim.chain_status or "not_submitted"
        return {
            "claim_id": claim.id,
            "submitted": chain_status not in ("", "not_submitted"),
            "finalized_on_chain": chain_status == "FINALIZED" and claim.chain_execution == "SUCCESS",
            "local_status": claim.status,
            "chain_status": chain_status,
            "reason": claim.chain_note or _chain_note_default(),
        }


@app.get("/v1/discoveries")
def discoveries() -> dict[str, Any]:
    with SessionLocal() as session:
        rows = session.scalars(select(ClaimRow).where(
            ClaimRow.public.is_(True),
            ClaimRow.chain_protocol_result == "EVIDENCE_SUFFICIENT",
            ClaimRow.status == "FINALIZED", ClaimRow.chain_claim_id != "",
            ClaimRow.chain_status == "FINALIZED", ClaimRow.chain_execution == "SUCCESS",
        ).order_by(ClaimRow.created_at.desc()).limit(100)).all()
        published = []
        for row in rows:
            if (row.chain_protocol_result != "EVIDENCE_SUFFICIENT"
                    or row.status != "FINALIZED"
                    or not row.chain_claim_id
                    or row.chain_status != "FINALIZED"
                    or row.chain_execution != "SUCCESS"):
                continue
            item = _claim_out(row)
            item["headline"] = (
                f"Protocol evidence sufficient. Scientific status: {item['scientific_status']}."
            )
            published.append(item)
        return {
            "note": "Only finalized on-chain evidence decisions appear here. They do not confirm a planet or signal.",
            "discoveries": published,
        }


@app.post("/v1/archives/tap")
def archive_tap(body: TapIn, request: Request) -> dict[str, Any]:
    rate_limit(request, "archives", 30)
    from api.archives import fetch_planets

    try:
        rows = fetch_planets(
            tic=body.tic or None,
            hostname=body.hostname or None,
            ra_deg=body.ra_deg,
            dec_deg=body.dec_deg,
        )
    except ArchiveError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    return {
        "live_query": True,
        "catalogue": "NASA Exoplanet Archive",
        "table": "pscomppars",
        "rows": rows,
        "note": "These are published planet parameters. A row is not a new confirmation.",
    }


@app.post("/v1/archives/gaia")
def archive_gaia(body: GaiaIn, request: Request) -> dict[str, Any]:
    rate_limit(request, "archives", 30)
    try:
        return query_gaia(body.ra_deg, body.dec_deg, body.radius_arcsec)
    except ArchiveError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@app.post("/v1/archives/horizons")
def archive_horizons(body: HorizonsIn, request: Request) -> dict[str, Any]:
    rate_limit(request, "archives", 30)
    try:
        return query_horizons(body.command)
    except ArchiveError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@app.post("/v1/radio/catalog")
def radio_catalog(body: RadioSearchIn, request: Request) -> dict[str, Any]:
    rate_limit(request, "radio-catalog", 20)
    try:
        return search_catalog(body.target)
    except ArchiveError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@app.post("/v1/radio/analyze")
def radio_analyze(request: Request = None, user: str = Depends(current_user)) -> dict[str, Any]:
    if request is not None:
        rate_limit(request, f"direct-radio:{user}", 3, 3600)
        rate_limit(request, "direct-radio-global", 30, 3600, global_scope=True)
    try:
        result = analyze_tutorial(_radio_cache())
    except ArchiveError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    result["environment_sha256"] = evidence.put_json(evidence.environment(), owner=user)
    result["report_sha256"] = evidence.put_json(result, owner=user)
    analysis_id = "rad_" + uuid.uuid4().hex[:12]
    record = RadioAnalysisRow(
        id=analysis_id,
        target_name=result["target_name"],
        owner=user,
        payload_json=json.dumps(result),
        artifact_sha256=result["artifact_sha256"],
        created_at=_now(),
    )
    with SessionLocal() as session:
        session.add(record)
        session.commit()
    return {"id": analysis_id, **result}


@app.get("/v1/radio/analyses/{analysis_id}")
def read_radio_analysis(analysis_id: str, user: str = Depends(current_user)):
    with SessionLocal() as session:
        row = session.get(RadioAnalysisRow, analysis_id)
        if row is None:
            raise HTTPException(404, "Radio analysis not found")
        require_owner(row, user)
        return {"id": row.id, **json.loads(row.payload_json)}


@app.post("/v1/radio/claims")
def create_radio_claim(body: ClaimIn, user: str = Depends(current_user)) -> dict[str, Any]:
    if not body.acknowledged:
        raise HTTPException(
            status_code=422,
            detail="Acknowledge that protocol review is not a scientific confirmation",
        )
    if body.submission_mode == "relay" and not os.environ.get("DEEPSIGHT_RELAY_ADDRESS", ""):
        raise HTTPException(503, "Relay wallet is not configured; create a wallet-owned claim")
    with SessionLocal() as session:
        row = session.get(RadioAnalysisRow, body.analysis_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Radio analysis not found")
        require_owner(row, user)
        result = json.loads(row.payload_json)
        built = build_radio_manifest(result, analysis_id=row.id, git_commit=_git_commit(), claimant_address=(user if body.submission_mode == "wallet" else os.environ.get("DEEPSIGHT_RELAY_ADDRESS", "")).lower(), researcher_address=user)
        text = built["text"]
        digest = built["sha256"]
        existing = session.scalar(select(ClaimRow).where(ClaimRow.manifest_hash == digest))
        if existing is not None:
            raise HTTPException(status_code=409, detail=f"Manifest already claimed as {existing.id}")
        now = _now()
        claim = ClaimRow(
            id="clm_" + uuid.uuid4().hex[:12],
            analysis_id=row.id,
            manifest_json=text,
            owner=user,
            manifest_hash=digest,
            status="EVIDENCE_READY",
            created_at=now,
            updated_at=now,
        )
        session.add(claim)
        _add_event(
            session,
            claim.id,
            "EVIDENCE_READY",
            "Radio manifest stored locally. Off-target comparison is unavailable, so policy review should stay in human review.",
        )
        session.commit()
        session.refresh(claim)
        return {**_claim_out(claim), "manifest": built["document"]}


@app.get("/v1/reviews")
def review_queue() -> dict[str, Any]:
    with SessionLocal() as session:
        rows = session.scalars(select(ClaimRow).where(
            ClaimRow.public.is_(True),
            ClaimRow.status == "NEEDS_REVIEW",
            or_(ClaimRow.review_resolution == "", ClaimRow.review_resolution.is_(None)),
        ).order_by(ClaimRow.updated_at.desc()).limit(100)).all()
        queued = [_claim_out(row) for row in rows]
    return {
        "note": "Two independent matching attestations resolve the review. They do not confirm a celestial object or signal.",
        "claims": queued,
    }


@app.post("/v1/claims/{claim_id}/review-note")
def review_note(claim_id: str, body: ReviewNoteIn, user: str = Depends(current_user)) -> dict[str, Any]:
    require_reviewer(user)
    with SessionLocal() as session:
        if session.bind.dialect.name == "sqlite":
            session.execute(text("BEGIN IMMEDIATE"))
        claim = session.scalar(select(ClaimRow).where(ClaimRow.id == claim_id).with_for_update())
        if claim is None:
            raise HTTPException(404, "Claim not found")
        if claim.status != "NEEDS_REVIEW":
            raise HTTPException(status_code=409, detail="A review note is only attached to NEEDS_REVIEW claims")
        if claim.owner == user:
            raise HTTPException(status_code=403, detail="A claimant cannot attest to their own evidence")
        if claim.review_resolution:
            raise HTTPException(status_code=409, detail="This review has already been resolved")
        session.add(AttestationRow(
            id="att_" + uuid.uuid4().hex[:16], claim_id=claim.id, manifest_hash=claim.manifest_hash,
            reviewer=user, decision=body.decision, note=body.note.strip(),
            conflict_disclosure=body.conflict_disclosure.strip(), created_at=_now(),
        ))
        _add_event(session, claim.id, "HUMAN_REVIEW", f"Reviewer {user}: {body.decision}. {body.note.strip()}")
        session.flush()
        decisions = session.scalars(select(AttestationRow.decision).where(AttestationRow.claim_id == claim.id)).all()
        if decisions.count(body.decision) >= 2 and body.decision != "inconclusive":
            claim.review_resolution = body.decision
            _add_event(session, claim.id, "REVIEW_RESOLVED", f"Two independent reviewers recorded {body.decision}.")
        session.commit()
        session.refresh(claim)
        return _claim_out(claim)


@app.get("/v1/research/attestations")
def attestations(claim_id: str, viewer: str | None = Depends(optional_user)) -> dict[str, Any]:
    with SessionLocal() as session:
        _visible_claim(session, claim_id, viewer)
        rows = session.scalars(select(AttestationRow).where(AttestationRow.claim_id == claim_id).order_by(AttestationRow.created_at)).all()
        return {"claim_id": claim_id, "attestations": [
            {"id": row.id, "manifest_hash": row.manifest_hash, "reviewer": row.reviewer,
             "decision": row.decision, "note": row.note, "conflict_disclosure": row.conflict_disclosure,
             "created_at": row.created_at} for row in rows
        ]}


@app.post("/v1/claims/{claim_id}/challenge")
def challenge_claim(claim_id: str, body: ChallengeIn, user: str = Depends(current_user)) -> dict[str, Any]:
    reason = body.reason.strip()
    reason_hash = sha256_text(reason)
    with SessionLocal() as session:
        claim = _claim_or_404(session, claim_id)
        if claim.status not in ("FINALIZED", "NEEDS_REVIEW"):
            raise HTTPException(status_code=409, detail=f"Cannot challenge a claim in status {claim.status}")
        chain_note = "Challenge stored locally. No chain claim id is attached."
        require_chain_idle(session, claim_id)
        if claim.chain_claim_id:
            raise HTTPException(428, "Chain challenges require a signed claim-specific intent")
        claim.status = "CHALLENGED"
        claim.challenge_reason = reason
        claim.challenge_reason_hash = reason_hash
        claim.chain_note = chain_note
        claim.updated_at = _now()
        _add_event(session, claim.id, "CHALLENGED", f"{chain_note} Reason hash {reason_hash}.")
        session.commit()
        session.refresh(claim)
        return _claim_out(claim)


@app.post("/v1/claims/{claim_id}/retract")
def retract_claim(claim_id: str, user: str = Depends(current_user)) -> dict[str, Any]:
    with SessionLocal() as session:
        claim = _claim_or_404(session, claim_id)
        require_owner(claim, user)
        if claim.status in ("RETRACTED", "SUPERSEDED"):
            raise HTTPException(status_code=409, detail=f"Cannot retract a claim in status {claim.status}")
        note = "Retracted in the local registry."
        require_chain_idle(session, claim_id)
        if claim.chain_claim_id:
            raise HTTPException(428, "Chain retractions require a signed claim-specific intent")
        claim.status = "RETRACTED"
        claim.updated_at = _now()
        _add_event(session, claim.id, "RETRACTED", note)
        session.commit()
        session.refresh(claim)
        return _claim_out(claim)


@app.post("/v1/claims/{claim_id}/submit")
def submit_claim(claim_id: str, user: str = Depends(current_user)) -> dict[str, Any]:
    with SessionLocal() as session:
        claim = _claim_or_404(session, claim_id)
        require_owner(claim, user)
        if claim.status not in ("EVIDENCE_READY", "FINALIZED", "NEEDS_REVIEW"):
            raise HTTPException(409, f"Cannot submit a claim in status {claim.status}")
    if not chain.configured():
        raise HTTPException(503, "No GenLayer contract address is configured")
    raise HTTPException(428, "Sign a claim-specific intent before authorizing a chain operation")


@app.post("/v1/claims/{claim_id}/appeal")
def appeal_claim(claim_id: str, body: AppealIn, user: str = Depends(current_user)):
    with SessionLocal() as session:
        claim = _claim_or_404(session, claim_id)
        require_owner(claim, user)
    raise HTTPException(409, "A finalized transaction cannot be appealed. Pre-finality appeals are not supported by this app yet.")


def _radio_cache():
    from api.db import DATA_DIR

    return DATA_DIR / "cache" / "radio"


def _append_tx(current: str, kind: str, tx_hash: str) -> str:
    try:
        payload = json.loads(current) if current else {}
    except json.JSONDecodeError:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    payload[kind] = tx_hash
    return json.dumps(payload)


def _limitations(target: dict[str, Any]) -> list[str]:
    shared = [
        "Not a scientific confirmation",
        "The signal-to-noise figure is a white-noise proxy, not a CDPP",
    ]
    if target["synthetic"]:
        return ["Synthetic calibration series", "Not an archive observation", *shared]
    return [
        f"TESS SPOC PDCSAP flux from sector {target.get('sector', '?')}, one sector only",
        "Quality-flagged cadences were removed",
        *shared,
    ]


def _checklist(manifest: dict[str, Any], payload: dict[str, Any]) -> list[dict[str, str]]:
    metrics = {item["name"]: item for item in manifest["metrics"]}
    archive_name = manifest["archive"]["name"]
    items = [
        _item("reproducibility", "Reproducible environment", bool(manifest["analysis"].get("environment_sha256")), "Rerun legacy analyses to capture exact inputs and environment"),
        _item("target", "Target identifier", True, manifest["target"]["id"]),
        _item("coordinates", "ICRS coordinates", True, f"{manifest['target']['ra_deg']}°, {manifest['target']['dec_deg']}°"),
        _item("observation", "Observation id", True, manifest["archive"]["observation_ids"][0]),
        _item("period", "Period with uncertainty", isinstance(metrics.get("period", {}).get("uncertainty"), (int, float)) and metrics["period"]["uncertainty"] > 0, "Conditional white-noise bootstrap in days; rerun or inspect boundary periods if unavailable"),
        _item("depth", "Transit depth", "depth" in metrics, "relative flux"),
        _item("snr", "Signal-to-noise proxy", "snr_proxy" in metrics, "white-noise proxy, not CDPP"),
        _item("artifact", "Light-curve checksum", len(manifest["artifacts"][0]["sha256"]) == 64, manifest["artifacts"][0]["sha256"][:12] + "…"),
        _item("raw_source", "Pinned raw MAST product", payload["target"]["synthetic"] or bool(manifest["archive"].get("raw_source_sha256")),
              "Synthetic calibration or the exact downloaded FITS product is preserved"),
        _item("cross", "Catalogue snapshot", bool(manifest["cross_matches"][0]["query_snapshot_sha256"]), payload["cross_match"]["result"]),
        _item("false_positives", "Odd-even and secondary tests", {item.get("name") for item in payload.get("false_positive_tests", [])} >= {"odd_even", "secondary_eclipse"}, "documented"),
        _item("quality", "Quality warnings", not any(flag.get("severity") == "warning" for flag in payload.get("quality_flags", [])), "Warnings require human review", warn_on_fail=True),
        _item("limitations", "Limitations recorded", len(manifest["limitations"]) > 0, "included in the manifest"),
        _item(
            "science",
            "Scientific status does not claim a new confirmation",
            manifest["scientific_status"] in {"unconfirmed_candidate", "known_object"},
            manifest["scientific_status"],
        ),
        _item(
            "archive",
            "Archive is on the celestial allowlist",
            archive_name in {"MAST", "NASA Exoplanet Archive", "Gaia", "JPL Horizons"},
            archive_name,
            warn_on_fail=True,
        ),
    ]
    return items


def _item(code: str, label: str, ok: bool, detail: str, warn_on_fail: bool = False) -> dict[str, str]:
    if ok:
        status = "pass"
    elif warn_on_fail:
        status = "warn"
    else:
        status = "fail"
    return {"id": code, "label": label, "status": status, "detail": detail}


@app.get("/v1/claims/{claim_id}/manifest")
def download_manifest(claim_id: str, viewer: str | None = Depends(optional_user)):
    with SessionLocal() as session:
        claim = _visible_claim(session, claim_id, viewer)
        return Response(claim.manifest_json, media_type="application/json", headers={
            "ETag": f'"{claim.manifest_hash}"',
            "Content-Disposition": f'attachment; filename="{claim.id}-manifest.json"',
        })


@app.get("/v1/claims/{claim_id}/bundle")
def download_bundle(claim_id: str, viewer: str | None = Depends(optional_user)):
    with SessionLocal() as session:
        claim = _visible_claim(session, claim_id, viewer)
        manifest = json.loads(claim.manifest_json)
        artifacts = {}
        refs = list(manifest.get("artifacts", [])) + list(manifest.get("cross_matches", []))
        env_hash = manifest.get("analysis", {}).get("environment_sha256")
        if env_hash:
            refs.append({"sha256": env_hash})
        for ref in refs:
            digest = ref.get("sha256") or ref.get("query_snapshot_sha256")
            if digest:
                artifacts[digest] = evidence.read(digest)
        bundle = {"manifest": claim.manifest_json, "manifest_sha256": claim.manifest_hash, "artifacts": artifacts}
        return Response(canonicalize(bundle), media_type="application/json", headers={
            "Content-Disposition": f'attachment; filename="{claim.id}-bundle.json"',
        })
