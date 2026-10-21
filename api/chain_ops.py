"""Signed relay intents and durable transaction outbox.

A researcher signs each operation; the configured relay pays and is the on-chain
claimant. The signed intent binds the researcher's identity to the exact manifest.
An uncertain broadcast is never automatically repeated.
"""
import json
import logging
import os
import secrets
import time
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import delete, select, update

from api import chain, evidence
from api.auth import current_user, optional_user, require_operator, require_owner, origin
from api.db import ChainIntent, ChainOperation, ClaimRow, ClaimEventRow, SessionLocal
from api.manifest import canonicalize, sha256_text
from api.signatures import valid_message_signature

router = APIRouter(prefix="/v1", tags=["chain"])
ACTIVE = ("queued", "broadcasting", "submitted", "reconciling", "unknown")
LEGACY_CONTRACT = "0x6B6dC06981Aa6903434dBab601D8b61c5fD57ff8"
V2_CONTRACT = "0x0E564b1d1767863FA3B73c6d07e3af73508CbB92"
V3_CONTRACT = "0xadE6737f44b65b3Faeb7C0aCedd3b0fD23844a0a"
V4_CONTRACT = "0x5cfaE959BbFF6Be9e4A1F477abDCc61fAfD5eeb1"


def config_for_claim(claim):
    cfg = chain.load_config()
    if not cfg:
        return None
    policy = json.loads(claim.manifest_json).get("policy_version", "")
    if policy in ("celestial-v1", "signal-v1"):
        return {**cfg, "address": os.environ.get("DEEPSIGHT_LEGACY_CONTRACT_ADDRESS", LEGACY_CONTRACT)}
    if policy in ("celestial-v2", "signal-v2"):
        return {**cfg, "address": os.environ.get("DEEPSIGHT_V2_CONTRACT_ADDRESS", V2_CONTRACT)}
    if policy in ("celestial-v3", "signal-v3"):
        return {**cfg, "address": os.environ.get("DEEPSIGHT_V3_CONTRACT_ADDRESS", V3_CONTRACT)}
    if policy in ("celestial-v4", "signal-v4"):
        return {**cfg, "address": os.environ.get("DEEPSIGHT_V4_CONTRACT_ADDRESS", V4_CONTRACT)}
    if policy in ("celestial-v5", "signal-v5"):
        record = Path(__file__).resolve().parent.parent / "deployments" / "studionet-v5.json"
        if not record.exists():
            return None
        deployed = json.loads(record.read_text())
        if (deployed.get("finalized_execution") != "SUCCESS" or deployed.get("code_matches_source") is not True
                or not deployed.get("contract_address")):
            return None
        return {**cfg, "address": str(deployed["contract_address"])}
    return cfg


class IntentIn(BaseModel):
    action: str = Field(pattern="^(submit|challenge|retract|supersede)$")
    reason: str = Field(default="", max_length=400)
    tx_hash: str = Field(default="", max_length=80)


class AuthorizationIn(BaseModel):
    intent_id: str = Field(min_length=48, max_length=48)
    signature: str = Field(pattern=r"^(?:0x)?(?:[0-9a-fA-F]{2}){1,2048}$")


class ReconcileIn(BaseModel):
    decision: str = Field(pattern="^(attach_hash|confirmed_not_broadcast)$")
    tx_hash: str = Field(default="", pattern=r"^(?:0x[0-9a-fA-F]{64})?$")
    evidence: str = Field(min_length=20, max_length=1000)


class WalletActionIn(BaseModel):
    action: str = Field(pattern="^(submit|review|challenge|retract|supersede)$")
    reason: str = Field(default="", max_length=400)
    publish_acknowledged: bool = False


class WalletTransactionIn(WalletActionIn):
    tx_hash: str = Field(pattern=r"^0x[0-9a-fA-F]{64}$")


def claim_for(db, claim_id):
    row = db.get(ClaimRow, claim_id)
    if row is None:
        raise HTTPException(404, "Claim not found")
    return row


def eligible(claim, action, actor):
    if action != "challenge":
        require_owner(claim, actor)
    allowed = {
        "submit": ("EVIDENCE_READY", "FINALIZED", "NEEDS_REVIEW"),
        "challenge": ("FINALIZED", "NEEDS_REVIEW"),
        "retract": ("EVIDENCE_READY", "FINALIZED", "NEEDS_REVIEW", "CHALLENGED"),
        "supersede": ("FINALIZED", "NEEDS_REVIEW", "CHALLENGED"),
    }
    if claim.status not in allowed[action]:
        raise HTTPException(409, f"Cannot {action} a claim in status {claim.status}")
    if action == "submit" and claim.chain_claim_id:
        raise HTTPException(409, "Claim is already registered")
    if action != "submit" and not claim.chain_claim_id:
        raise HTTPException(409, "This claim has not been registered on chain")
    if action == "challenge" and claim.challenge_reason_hash:
        raise HTTPException(409, "This claim already has an objection")


def idle(db, claim_id):
    active = db.scalar(select(ChainOperation).where(ChainOperation.claim_id == claim_id, ChainOperation.status.in_(ACTIVE)))
    if active:
        raise HTTPException(409, "A chain operation is already pending or needs reconciliation")


def event(db, claim, status, note):
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    claim.updated_at = now
    db.add(ClaimEventRow(claim_id=claim.id, status=status, note=note, observed_at=now))


@router.get("/chain/config")
def config():
    cfg = chain.load_config()
    return {"configured": cfg is not None, "contract_address": cfg["address"] if cfg else None,
            "relay_enabled": os.environ.get("DEEPSIGHT_RELAY_ENABLED") == "1",
            "signing_mode": "wallet_or_signed_intent_relay", "network": "GenLayer StudioNet",
            "note": "New wallet-owned claims send transactions from the connected wallet. Earlier relay claims use signed intents."}


def _wallet_stage(claim, action, user, reason):
    manifest = json.loads(claim.manifest_json)
    if (manifest.get("claimant_address", "").lower() != claim.owner
            or manifest.get("researcher_address", "").lower() != claim.owner):
        raise HTTPException(409, "This claim is relay-owned; use its signed relay action")
    if action != "challenge" and claim.owner != user:
        raise HTTPException(403, "Only the wallet claimant may send this transaction")
    if action == "review":
        require_owner(claim, user)
        if not claim.chain_claim_id or claim.status != "EVIDENCE_READY":
            raise HTTPException(409, "Register this claim before requesting on-chain review")
        return "review"
    eligible(claim, action, user)
    if action == "challenge" and len(reason.strip()) < 20:
        raise HTTPException(422, "Provide a challenge reason of at least 20 characters")
    return "register" if action == "submit" else action


def _publish_for_wallet(db, claim, action, user, payload, acknowledged):
    manifest = json.loads(claim.manifest_json)
    if action in ("submit", "supersede") and not acknowledged:
        raise HTTPException(422, "Acknowledge that this action publishes the manifest and evidence before your wallet is prompted")
    if action == "submit":
        if sha256_text(claim.manifest_json) != claim.manifest_hash or len(claim.manifest_json) > 8000:
            raise HTTPException(422, "Manifest checksum or contract length check failed")
        env = manifest.get("analysis", {}).get("environment_sha256")
        if not env:
            raise HTTPException(422, "Rebuild evidence with a reproducible environment")
        evidence.read(env)
        if manifest.get("archive", {}).get("name") == "MAST":
            evidence.read_fits(manifest["archive"]["raw_source_sha256"])
        for match in manifest.get("cross_matches", []):
            evidence.read(match["query_snapshot_sha256"])
        for item in manifest.get("artifacts", []):
            if not str(item.get("uri", "")).startswith("/v1/artifacts/"):
                raise HTTPException(422, "Regenerate evidence with retrievable artifacts")
            evidence.read(item["sha256"])
        evidence.publish_manifest(db, manifest)
        claim.public = True
    elif action == "supersede":
        manifest["supersedes"] = claim.manifest_hash
        replacement_text = canonicalize(manifest)
        replacement_hash = sha256_text(replacement_text)
        replacement = db.scalar(select(ClaimRow).where(ClaimRow.manifest_hash == replacement_hash))
        if replacement and (replacement.owner != user or replacement.supersedes != claim.id or replacement.status != "PENDING_CHAIN"):
            raise HTTPException(409, "A different replacement uses this manifest hash")
        replacement_id = replacement.id if replacement else "clm_" + secrets.token_hex(6)
        if replacement is None:
            db.add(ClaimRow(id=replacement_id, analysis_id=claim.analysis_id, owner=user,
                            manifest_json=replacement_text, manifest_hash=replacement_hash,
                            status="PENDING_CHAIN", public=True, supersedes=claim.id,
                            created_at=claim.updated_at, updated_at=claim.updated_at))
        evidence.publish_manifest(db, manifest)
        payload.update(replacement_id=replacement_id, replacement_hash=replacement_hash)
        claim.public = True


@router.post("/claims/{claim_id}/wallet/prepare")
def prepare_wallet(claim_id: str, body: WalletActionIn, user: str = Depends(current_user)):
    with SessionLocal() as db:
        claim = claim_for(db, claim_id)
        cfg = config_for_claim(claim)
        if not cfg:
            raise HTTPException(503, "GenLayer contract is not configured")
        stage = _wallet_stage(claim, body.action, user, body.reason)
        idle(db, claim_id)
        payload = {"contract": cfg["address"], "manifest_hash": claim.manifest_hash,
                   "reason": body.reason.strip(), "action": body.action}
        _publish_for_wallet(db, claim, body.action, user, payload, body.publish_acknowledged)
        command = _command(type("Pending", (), {"stage": stage})(), claim, payload)
        db.commit()
        return {"contract": cfg["address"], "method": command["method"], "args": command["args"],
                "stage": stage, "manifest_hash": claim.manifest_hash,
                "note": "Your wallet will send and pay for this GenLayer StudioNet transaction. The manifest and evidence are public."}


@router.post("/claims/{claim_id}/wallet/transaction", status_code=202)
def attach_wallet_transaction(claim_id: str, body: WalletTransactionIn, user: str = Depends(current_user)):
    with SessionLocal() as db:
        claim = claim_for(db, claim_id)
        cfg = config_for_claim(claim)
        if not cfg:
            raise HTTPException(503, "GenLayer contract is not configured")
        existing = db.scalar(select(ChainOperation).where(ChainOperation.tx_hash == body.tx_hash))
        if existing:
            if existing.claim_id == claim_id and existing.actor == user and existing.action == body.action:
                return {"id": existing.id, "status": existing.status}
            raise HTTPException(409, "Transaction is already attached to another operation")
        stage = _wallet_stage(claim, body.action, user, body.reason)
        idle(db, claim_id)
        if not claim.public:
            raise HTTPException(409, "Prepare and publish the evidence before sending a transaction")
        inspected = chain.invoke({"action": "inspect", "tx_hash": body.tx_hash}, cfg)
        if not inspected.get("ok"):
            raise HTTPException(422, "Transaction is not visible on GenLayer yet; retry attaching this hash")
        if inspected.get("from", "").lower() != user or inspected.get("to", "").lower() != cfg["address"].lower():
            raise HTTPException(403, "Transaction sender or contract does not match this claim")
        payload = {"contract": cfg["address"], "manifest_hash": claim.manifest_hash,
                   "reason": body.reason.strip(), "action": body.action}
        if body.action == "supersede":
            _publish_for_wallet(db, claim, body.action, user, payload, body.publish_acknowledged)
        expected = _command(type("Pending", (), {"stage": stage})(), claim, payload)
        decoded = inspected.get("decoded")
        call = decoded.get("callData") if isinstance(decoded, dict) else None
        if (not isinstance(call, dict) or call.get("method") != expected["method"]
                or call.get("args", []) != expected["args"]):
            raise HTTPException(403, "Transaction method or arguments do not match this claim")
        changed = db.execute(update(ClaimRow).where(
            ClaimRow.id == claim.id, ClaimRow.revision == claim.revision,
            ClaimRow.chain_status == claim.chain_status, ClaimRow.status == claim.status,
        ).values(chain_status="SUBMITTED", revision=ClaimRow.revision + 1))
        if changed.rowcount != 1:
            db.rollback()
            raise HTTPException(409, "Another claim transaction was attached; refresh before retrying")
        db.refresh(claim)
        op = ChainOperation(id="op_" + secrets.token_hex(16), claim_id=claim_id, actor=user,
                            action=body.action, stage=stage, status="submitted", payload=canonicalize(payload),
                            authorization="wallet_transaction", signature="", tx_hash=body.tx_hash,
                            updated=int(time.time()))
        db.add(op)
        txs = json.loads(claim.chain_tx or "{}")
        txs[stage] = body.tx_hash
        claim.chain_tx = json.dumps(txs)
        claim.chain_status = "SUBMITTED"
        claim.chain_execution = "UNKNOWN"
        event(db, claim, "SUBMITTED", f"Wallet {stage} transaction {body.tx_hash}")
        db.commit()
        return {"id": op.id, "status": op.status}


@router.post("/claims/{claim_id}/intent")
def prepare(claim_id: str, body: IntentIn, user: str = Depends(current_user)):
    if os.environ.get("DEEPSIGHT_RELAY_ENABLED") != "1":
        raise HTTPException(503, "The chain relay is not configured and enabled")
    relay_address = os.environ.get("DEEPSIGHT_RELAY_ADDRESS", "").lower()
    if len(relay_address) != 42 or not relay_address.startswith("0x") or any(c not in "0123456789abcdef" for c in relay_address[2:]):
        raise HTTPException(503, "Set DEEPSIGHT_RELAY_ADDRESS to the submitting relay wallet address")
    with SessionLocal() as db:
        claim = claim_for(db, claim_id)
        cfg = config_for_claim(claim)
        if cfg is None:
            raise HTTPException(503, "The chain relay is not configured and enabled")
        eligible(claim, body.action, user)
        idle(db, claim_id)
        payload = body.model_dump()
        payload["contract"] = cfg["address"]
        payload["manifest_hash"] = claim.manifest_hash
        if body.action == "submit":
            manifest = json.loads(claim.manifest_json)
            if manifest.get("claimant_address") != relay_address or manifest.get("researcher_address") != user:
                raise HTTPException(409, "Manifest does not bind this relay and researcher; create new evidence")
            if sha256_text(claim.manifest_json) != claim.manifest_hash:
                raise HTTPException(409, "Manifest checksum verification failed")
            if len(claim.manifest_json) > 8000:
                raise HTTPException(422, "Manifest exceeds the contract's 8000 character limit")
            env = manifest.get("analysis", {}).get("environment_sha256")
            if not env:
                raise HTTPException(422, "Regenerate evidence to retain the reproducible environment")
            evidence.read(env)
            raw_digest = manifest.get("archive", {}).get("raw_source_sha256")
            if manifest.get("archive", {}).get("name") == "MAST":
                if not raw_digest:
                    raise HTTPException(422, "Regenerate evidence with the pinned raw MAST product")
                evidence.read_fits(raw_digest)
            for match in manifest.get("cross_matches", []):
                evidence.read(match["query_snapshot_sha256"])
            # Legacy local references must be regenerated before publication.
            for item in manifest.get("artifacts", []):
                if not str(item.get("uri", "")).startswith("/v1/artifacts/"):
                    raise HTTPException(422, "Regenerate evidence with retrievable artifacts before submission")
                evidence.read(item["sha256"])
        if body.action == "challenge" and len(body.reason.strip()) < 20:
            raise HTTPException(422, "Provide a challenge reason of at least 20 characters")
        if body.action == "supersede":
            manifest = json.loads(claim.manifest_json)
            if manifest.get("claimant_address") != relay_address or manifest.get("researcher_address") != user:
                raise HTTPException(409, "Manifest does not bind this relay and researcher")
            manifest["supersedes"] = claim.manifest_hash
            payload["replacement"] = canonicalize(manifest)
            payload["replacement_hash"] = sha256_text(payload["replacement"])
            pending = db.scalar(select(ClaimRow).where(ClaimRow.manifest_hash == payload["replacement_hash"]))
            if pending and (pending.supersedes != claim.id or pending.owner != user or pending.status != "PENDING_CHAIN"):
                raise HTTPException(409, "A different replacement already uses this manifest hash")
            payload["replacement_id"] = pending.id if pending else "clm_" + secrets.token_hex(6)
        nonce, now = secrets.token_hex(24), int(time.time())
        message = (f"DeepSight chain authorization\nOrigin: {origin()}\nNetwork: GenLayer StudioNet\n"
                   f"Contract: {cfg['address']}\nResearcher: {user}\nClaim: {claim.id}\n"
                   f"Manifest SHA256: {claim.manifest_hash}\nAction: {body.action}\n"
                   f"Payload: {canonicalize(payload)}\nNonce: {nonce}\nExpires: {now + 300}\n"
                   "I authorize the DeepSight server relay to execute this operation and review any registered replacement. I understand that submission publishes the manifest, evidence, and my wallet address. The relay is the on-chain claimant and pays network fees.")
        db.add(ChainIntent(id=nonce, claim_id=claim.id, actor=user, action=body.action, payload=canonicalize(payload), message=message, expires=now+300))
        db.commit()
        return {"id": nonce, "message": message}


@router.post("/claims/{claim_id}/authorize", status_code=202)
def authorize(claim_id: str, body: AuthorizationIn, user: str = Depends(current_user)):
    with SessionLocal() as db:
        intent = db.get(ChainIntent, body.intent_id)
        if not intent or intent.claim_id != claim_id or intent.actor != user or intent.expires <= int(time.time()):
            raise HTTPException(401, "Authorization expired, invalid, or already used")
        claim = claim_for(db, claim_id)
        eligible(claim, intent.action, user)
        idle(db, claim_id)
        cfg = config_for_claim(claim)
        payload = json.loads(intent.payload)
        if not cfg or os.environ.get("DEEPSIGHT_RELAY_ENABLED") != "1" or cfg["address"] != payload["contract"] or payload["manifest_hash"] != claim.manifest_hash:
            raise HTTPException(409, "Configuration or claim changed; sign a new authorization")
        if not valid_message_signature(user, intent.message, body.signature):
            raise HTTPException(403, "Operation signature belongs to another wallet")
        # Compare-and-set on the claim also serializes different intents.
        previous_status = claim.chain_status
        changed = db.execute(update(ClaimRow).where(ClaimRow.id == claim.id, ClaimRow.chain_status == claim.chain_status, ClaimRow.revision == claim.revision, ClaimRow.status == claim.status).values(chain_status="QUEUED", revision=ClaimRow.revision + 1))
        if changed.rowcount != 1 or previous_status == "QUEUED":
            db.rollback()
            raise HTTPException(409, "Another operation was queued")
        consumed = db.execute(delete(ChainIntent).where(ChainIntent.id == intent.id))
        if consumed.rowcount != 1:
            raise HTTPException(409, "Authorization already used")
        if intent.action == "supersede":
            replacement = db.get(ClaimRow, payload["replacement_id"])
            if replacement:
                if (replacement.status != "PENDING_CHAIN" or replacement.owner != user
                        or replacement.supersedes != claim.id or replacement.manifest_hash != payload["replacement_hash"]):
                    raise HTTPException(409, "Pending replacement changed; sign a new authorization")
                replacement.chain_status = "QUEUED"
                replacement.public = True
            else:
                now = claim.updated_at
                db.add(ClaimRow(id=payload["replacement_id"], analysis_id=claim.analysis_id, owner=user,
                                manifest_json=payload["replacement"], manifest_hash=payload["replacement_hash"],
                                status="PENDING_CHAIN", chain_status="QUEUED", public=True, supersedes=claim.id,
                                created_at=now, updated_at=now))
            evidence.publish_manifest(db, json.loads(payload["replacement"]))
        if intent.action == "submit":
            evidence.publish_manifest(db, json.loads(claim.manifest_json))
        claim.public = True
        operation = ChainOperation(id="op_"+secrets.token_hex(16), claim_id=claim_id, actor=user,
                                   action=intent.action, stage="register" if intent.action == "submit" else intent.action,
                                   status="queued", payload=intent.payload, authorization=intent.message,
                                   signature=body.signature, updated=int(time.time()))
        db.add(operation)
        event(db, claim, "QUEUED", f"Signed {intent.action} authorization by {user}.")
        db.commit()
        return {"id": operation.id, "status": "queued"}


@router.get("/claims/{claim_id}/operations")
def operations(claim_id: str, viewer: str | None = Depends(optional_user)):
    with SessionLocal() as db:
        claim = claim_for(db, claim_id)
        if not claim.public and claim.owner != viewer:
            raise HTTPException(404, "Claim not found")
        rows = db.scalars(select(ChainOperation).where(ChainOperation.claim_id == claim_id).order_by(ChainOperation.updated)).all()
        return {"operations": [{"id": r.id, "action": r.action, "stage": r.stage, "status": r.status,
                                "tx_hash": r.tx_hash, "error": r.error, "actor": r.actor} for r in rows]}


@router.post("/chain/operations/{operation_id}/reconcile")
def reconcile_operation(operation_id: str, body: ReconcileIn, user: str = Depends(current_user)):
    require_operator(user)
    if (body.decision == "attach_hash") != bool(body.tx_hash):
        raise HTTPException(422, "A transaction hash is required only when attaching a broadcast")
    with SessionLocal() as db:
        op = db.scalar(select(ChainOperation).where(ChainOperation.id == operation_id, ChainOperation.status == "unknown").with_for_update())
        if op is None:
            raise HTTPException(409, "Operation is not awaiting reconciliation")
        claim = claim_for(db, op.claim_id)
        if body.decision == "attach_hash":
            cfg = config_for_claim(claim)
            if cfg is None:
                raise HTTPException(503, "Contract configuration is unavailable")
            receipt = chain.invoke({"action": "receipt", "tx_hash": body.tx_hash}, cfg)
            if not receipt.get("ok") or receipt.get("status") not in ("ACCEPTED", "FINALIZED", "PENDING"):
                raise HTTPException(422, "The supplied transaction is not visible to the configured network")
            op.tx_hash = body.tx_hash
            op.status = "submitted"
            txs = json.loads(claim.chain_tx or "{}")
            txs[op.stage] = body.tx_hash
            claim.chain_tx = json.dumps(txs)
            claim.chain_status = "SUBMITTED"
        else:
            # A human must first establish from the relay nonce and explorer
            # that this attempt was never broadcast. The old signed intent is
            # reused, so the retry cannot change the authorized operation.
            op.status = "queued"
            op.tx_hash = ""
            claim.chain_status = "QUEUED"
        op.error = ""
        op.updated = int(time.time())
        event(db, claim, "RECONCILED", f"Operator {user}: {body.decision}. Evidence: {body.evidence.strip()}")
        db.commit()
        return {"id": op.id, "status": op.status}


def execute_one():
    """One bounded outbox iteration. It never replays an uncertain broadcast."""
    with SessionLocal() as db:
        # A process may die after sending and before recording a hash.
        db.execute(update(ChainOperation).where(ChainOperation.status == "broadcasting", ChainOperation.updated < int(time.time())-180).values(status="unknown", error="Broadcast outcome unknown; reconcile with the network before retrying."))
        db.execute(update(ChainOperation).where(ChainOperation.status == "reconciling", ChainOperation.updated < int(time.time())-180).values(status="submitted"))
        db.commit()
        selectable = ("queued", "submitted") if os.environ.get("DEEPSIGHT_RELAY_ENABLED") == "1" else ("submitted",)
        op = db.scalar(select(ChainOperation).where(
            ChainOperation.status.in_(selectable), ChainOperation.updated <= int(time.time())
        ).order_by(ChainOperation.updated).limit(1))
        if op is None:
            return False
        claim = claim_for(db, op.claim_id)
        payload = json.loads(op.payload)
        cfg = config_for_claim(claim)
        if not cfg or cfg["address"] != payload["contract"]:
            op.error = "Relay configuration differs from the signed contract; operation is paused."
            op.updated = int(time.time()) + 60
            db.commit()
            return True
        if op.status == "queued":
            if os.environ.get("DEEPSIGHT_RELAY_ENABLED") != "1":
                return False
            changed = db.execute(update(ChainOperation).where(ChainOperation.id == op.id, ChainOperation.status == "queued").values(status="broadcasting", updated=int(time.time())))
            db.commit()
            if changed.rowcount != 1:
                return True
            try:
                result = chain.invoke(_command(op, claim, payload), cfg)
                if not result.get("ok") or not result.get("hash"):
                    # Even an RPC failure can occur after a broadcast. Preserve uncertainty.
                    detail = str(result.get("error", "")).lower()
                    if "rate limit" in detail:
                        cause = "StudioNet RPC rate limit"
                    elif "insufficient funds" in detail:
                        cause = "relay account has insufficient funds"
                    else:
                        cause = "RPC or adapter failure"
                    op.status, op.error = "unknown", f"No transaction hash returned ({cause}). Operator reconciliation required."
                    logging.warning("GenLayer broadcast produced no hash: %s", cause)
                else:
                    op.tx_hash, op.status = result["hash"], "submitted"
                    txs = json.loads(claim.chain_tx or "{}")
                    txs[op.stage] = op.tx_hash
                    claim.chain_tx = json.dumps(txs)
                    claim.chain_status = "SUBMITTED"
                    claim.chain_execution = "UNKNOWN"
                    event(db, claim, "SUBMITTED", f"{op.stage} transaction {op.tx_hash}")
            except Exception:
                op.status, op.error = "unknown", "Broadcast interrupted. Operator reconciliation required."
        else:
            acquired = db.execute(update(ChainOperation).where(ChainOperation.id == op.id, ChainOperation.status == "submitted").values(status="reconciling", updated=int(time.time())))
            db.commit()
            if acquired.rowcount != 1:
                return True
            try:
                receipt = chain.invoke({"action": "receipt", "tx_hash": op.tx_hash}, cfg)
                if not receipt.get("ok"):
                    raise RuntimeError("Receipt unavailable")
                claim.chain_status = receipt.get("status", "UNKNOWN")
                claim.chain_execution = receipt.get("execution", "UNKNOWN")
                if claim.chain_status == "FINALIZED":
                    if claim.chain_execution == "FAILED":
                        op.status, op.error = "failed", "Finalized transaction execution failed"
                        event(db, claim, "FAILED_TRANSACTION", op.error)
                    elif claim.chain_execution == "SUCCESS":
                        _finish(db, op, claim, cfg, payload)
                elif claim.chain_status in ("CANCELED", "UNDETERMINED"):
                    op.status, op.error = "failed", f"Transaction ended as {claim.chain_status}"
            except Exception:
                op.error = "Network reconciliation unavailable; worker will retry this read."
        if op.status == "reconciling":
            op.status = "submitted"
        # A pending receipt or temporarily unavailable read must not monopolize
        # the outbox or exhaust the StudioNet RPC budget.
        op.updated = int(time.time()) + (30 if op.status == "submitted" and op.error else 0)
        claim.chain_note = op.error or f"{op.action}: {op.status}; transaction {op.tx_hash or 'not yet broadcast'}"
        db.commit()
        return True


def _command(op, claim, payload):
    manifest = json.loads(claim.manifest_json)
    source = origin()+f"/v1/claims/{claim.id}/manifest"
    if op.stage == "register":
        method, args = "register_claim", [claim.manifest_hash, manifest["claim_type"], manifest["policy_version"], source, manifest["target"]["id"]]
    elif op.stage == "review":
        method, args = "request_evidence_review", [claim.chain_claim_id, chain.review_argument(claim.manifest_json)]
    elif op.stage == "challenge":
        method, args = "challenge_claim", [claim.chain_claim_id, sha256_text(payload["reason"].strip())]
    elif op.stage == "retract":
        method, args = "retract_claim", [claim.chain_claim_id]
    elif op.stage == "supersede":
        replacement_source = origin()+f"/v1/claims/{payload['replacement_id']}/manifest"
        method, args = "supersede_claim", [claim.chain_claim_id, payload["replacement_hash"], replacement_source]
    else:
        raise RuntimeError(f"Unsupported chain operation stage: {op.stage}")
    return {"action": "broadcast", "method": method, "args": args}


def _finish(db, op, claim, cfg, payload):
    if op.stage == "register":
        result = chain.invoke({"action": "read", "method": "read_claim_by_manifest", "args": [claim.manifest_hash]}, cfg)
        found = chain._nested_claim_id(result.get("result"))
        if not result.get("ok") or not found:
            raise RuntimeError("Registered claim not readable yet")
        claim.chain_claim_id = found
        if op.authorization == "wallet_transaction":
            op.status, op.error = "done", ""
            event(db, claim, "REGISTERED", f"Wallet registration finalized as {found}. On-chain review is ready.")
            return
        op.stage, op.status, op.tx_hash, op.error = "review", "queued", "", ""
        claim.chain_status = "QUEUED"
        return
    result = chain.invoke({"action": "read", "method": "read_claim", "args": [claim.chain_claim_id]}, cfg)
    state = result.get("result")
    if not result.get("ok") or not isinstance(state, dict):
        raise RuntimeError("Claim not readable yet")
    policy = json.loads(claim.manifest_json).get("policy_version", "")
    v5 = policy in ("celestial-v5", "signal-v5")
    expected = {
        "review": ("FINALIZED", "NEEDS_REVIEW"),
        "challenge": ("FINALIZED", "NEEDS_REVIEW") if v5 else ("CHALLENGED",),
        "retract": ("RETRACTED",),
        "supersede": ("SUPERSEDED",),
    }.get(op.stage)
    if expected and state.get("status") not in expected:
        raise RuntimeError("Contract claim state has not caught up with the finalized transaction")
    if op.stage == "supersede" and not state.get("superseded_by"):
        raise RuntimeError("Contract replacement is not readable yet")
    if op.stage == "challenge" and v5 and state.get("challenge_reason_hash") != sha256_text(payload["reason"].strip()):
        raise RuntimeError("Finalized objection hash does not match the submitted reason")
    if op.stage == "supersede":
        replacement_view = chain.invoke({"action": "read", "method": "read_claim_by_manifest", "args": [payload["replacement_hash"]]}, cfg)
        replacement_state = replacement_view.get("result")
        if (not replacement_view.get("ok") or not isinstance(replacement_state, dict)
                or replacement_state.get("claim_id") != state["superseded_by"]
                or replacement_state.get("manifest_hash") != payload["replacement_hash"]):
            raise RuntimeError("Contract replacement hash or ID is not readable yet")
    claim.chain_protocol_result = str(state.get("protocol_result", ""))
    claim.chain_rationale = str(state.get("rationale", ""))
    if op.stage == "challenge":
        claim.challenge_reason = payload["reason"].strip()
        claim.challenge_reason_hash = sha256_text(claim.challenge_reason)
    if op.stage == "supersede":
        replacement = db.get(ClaimRow, payload["replacement_id"])
        if replacement is None or replacement.manifest_hash != payload["replacement_hash"]:
            raise RuntimeError("Published replacement manifest is missing or changed")
        replacement.status = "EVIDENCE_READY"
        replacement.chain_claim_id = str(state.get("superseded_by", ""))
        claim.superseded_by = replacement.id
        claim.status = "SUPERSEDED"
        event(db, claim, "SUPERSEDED", f"Chain replacement {replacement.id} finalized")
        if op.authorization == "wallet_transaction":
            op.status, op.error = "done", ""
            replacement.chain_status = "FINALIZED"
            return
        op.claim_id = replacement.id
        op.stage, op.status, op.tx_hash, op.error = "review", "queued", "", ""
        replacement.chain_status = "QUEUED"
        return
    state_status = state.get("status")
    if state_status in ("FINALIZED", "NEEDS_REVIEW", "CHALLENGED", "RETRACTED", "SUPERSEDED"):
        claim.status = state_status
    op.status, op.error = "done", ""
    event(db, claim, "FINALIZED", f"{op.stage} execution succeeded and finalized. Policy: {claim.chain_protocol_result}.")
