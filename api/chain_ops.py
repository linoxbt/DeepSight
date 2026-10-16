"""Signed relay intents and durable transaction outbox.

A researcher signs each operation; the configured relay pays and is the on-chain
claimant. The signed intent binds the researcher's identity to the exact manifest.
An uncertain broadcast is never automatically repeated.
"""
import json
import os
import secrets
import time

from eth_account import Account
from eth_account.messages import encode_defunct
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import delete, select, update

from api import chain, evidence
from api.auth import current_user, require_owner, origin
from api.db import ChainIntent, ChainOperation, ClaimRow, ClaimEventRow, SessionLocal
from api.manifest import canonicalize, sha256_text

router = APIRouter(prefix="/v1", tags=["chain"])
ACTIVE = ("queued", "broadcasting", "submitted", "reconciling", "unknown")


class IntentIn(BaseModel):
    action: str = Field(pattern="^(submit|challenge|retract|supersede|appeal)$")
    reason: str = Field(default="", max_length=400)
    tx_hash: str = Field(default="", max_length=80)


class AuthorizationIn(BaseModel):
    intent_id: str = Field(min_length=48, max_length=48)
    signature: str = Field(pattern=r"^(0x)?[0-9a-fA-F]{130}$")


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
        "appeal": ("FINALIZED", "NEEDS_REVIEW", "CHALLENGED", "EVIDENCE_READY"),
    }
    if claim.status not in allowed[action]:
        raise HTTPException(409, f"Cannot {action} a claim in status {claim.status}")
    if action == "submit" and claim.chain_claim_id:
        raise HTTPException(409, "Claim is already registered")
    if action != "submit" and not claim.chain_claim_id:
        raise HTTPException(409, "This claim has not been registered on chain")


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
            "signing_mode": "signed_intent_relay", "network": "GenLayer StudioNet",
            "note": "Your signature authorizes this exact operation. The server relay pays fees and is the on-chain claimant."}


@router.post("/claims/{claim_id}/intent")
def prepare(claim_id: str, body: IntentIn, user: str = Depends(current_user)):
    cfg = chain.load_config()
    if cfg is None or os.environ.get("DEEPSIGHT_RELAY_ENABLED") != "1":
        raise HTTPException(503, "The chain relay is not configured and enabled")
    relay_address = os.environ.get("DEEPSIGHT_RELAY_ADDRESS", "").lower()
    if len(relay_address) != 42 or not relay_address.startswith("0x") or any(c not in "0123456789abcdef" for c in relay_address[2:]):
        raise HTTPException(503, "Set DEEPSIGHT_RELAY_ADDRESS to the submitting relay wallet address")
    with SessionLocal() as db:
        claim = claim_for(db, claim_id)
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
            for match in manifest.get("cross_matches", []):
                evidence.read(match["query_snapshot_sha256"])
            # Legacy local references must be regenerated before publication.
            for item in manifest.get("artifacts", []):
                if not str(item.get("uri", "")).startswith("/v1/artifacts/"):
                    raise HTTPException(422, "Regenerate evidence with retrievable artifacts before submission")
                evidence.read(item["sha256"])
        if body.action == "challenge" and len(body.reason.strip()) < 20:
            raise HTTPException(422, "Provide a challenge reason of at least 20 characters")
        if body.action == "appeal" and body.tx_hash not in json.loads(claim.chain_tx or "{}").values():
            raise HTTPException(422, "Transaction does not belong to this claim")
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
                   "I authorize the DeepSight server relay to execute this operation and review any registered replacement. The relay is the on-chain claimant and pays network fees.")
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
        cfg = chain.load_config()
        payload = json.loads(intent.payload)
        if not cfg or os.environ.get("DEEPSIGHT_RELAY_ENABLED") != "1" or cfg["address"] != payload["contract"] or payload["manifest_hash"] != claim.manifest_hash:
            raise HTTPException(409, "Configuration or claim changed; sign a new authorization")
        try:
            signer = Account.recover_message(encode_defunct(text=intent.message), signature=body.signature).lower()
        except Exception as exc:
            raise HTTPException(401, "Invalid operation signature") from exc
        if signer != user:
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
            else:
                now = claim.updated_at
                db.add(ClaimRow(id=payload["replacement_id"], analysis_id=claim.analysis_id, owner=user,
                                manifest_json=payload["replacement"], manifest_hash=payload["replacement_hash"],
                                status="PENDING_CHAIN", chain_status="QUEUED", supersedes=claim.id,
                                created_at=now, updated_at=now))
        operation = ChainOperation(id="op_"+secrets.token_hex(16), claim_id=claim_id, actor=user,
                                   action=intent.action, stage="register" if intent.action == "submit" else intent.action,
                                   status="queued", payload=intent.payload, authorization=intent.message,
                                   signature=body.signature, updated=int(time.time()))
        db.add(operation)
        event(db, claim, "QUEUED", f"Signed {intent.action} authorization by {user}.")
        db.commit()
        return {"id": operation.id, "status": "queued"}


@router.get("/claims/{claim_id}/operations")
def operations(claim_id: str):
    with SessionLocal() as db:
        claim_for(db, claim_id)
        rows = db.scalars(select(ChainOperation).where(ChainOperation.claim_id == claim_id).order_by(ChainOperation.updated)).all()
        return {"operations": [{"id": r.id, "action": r.action, "stage": r.stage, "status": r.status,
                                "tx_hash": r.tx_hash, "error": r.error, "actor": r.actor} for r in rows]}


def execute_one():
    """One bounded outbox iteration. It never replays an uncertain broadcast."""
    with SessionLocal() as db:
        # A process may die after sending and before recording a hash.
        db.execute(update(ChainOperation).where(ChainOperation.status == "broadcasting", ChainOperation.updated < int(time.time())-180).values(status="unknown", error="Broadcast outcome unknown; reconcile with the network before retrying."))
        db.execute(update(ChainOperation).where(ChainOperation.status == "reconciling", ChainOperation.updated < int(time.time())-180).values(status="submitted"))
        db.commit()
        selectable = ("queued", "submitted") if os.environ.get("DEEPSIGHT_RELAY_ENABLED") == "1" else ("submitted",)
        op = db.scalar(select(ChainOperation).where(ChainOperation.status.in_(selectable)).order_by(ChainOperation.updated).limit(1))
        if op is None:
            return False
        claim = claim_for(db, op.claim_id)
        payload = json.loads(op.payload)
        cfg = chain.load_config()
        if not cfg or cfg["address"] != payload["contract"]:
            op.error = "Relay configuration differs from the signed contract; operation is paused."
            op.updated = int(time.time())
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
                    op.status, op.error = "unknown", "No transaction hash returned. Operator reconciliation required."
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
        op.updated = int(time.time())
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
        return {"action": "appeal", "tx_hash": payload["tx_hash"]}
    return {"action": "broadcast", "method": method, "args": args}


def _finish(db, op, claim, cfg, payload):
    if op.stage == "register":
        result = chain.invoke({"action": "read", "method": "read_claim_by_manifest", "args": [claim.manifest_hash]}, cfg)
        found = chain._nested_claim_id(result.get("result"))
        if not result.get("ok") or not found:
            raise RuntimeError("Registered claim not readable yet")
        claim.chain_claim_id = found
        op.stage, op.status, op.tx_hash, op.error = "review", "queued", "", ""
        claim.chain_status = "QUEUED"
        return
    result = chain.invoke({"action": "read", "method": "read_claim", "args": [claim.chain_claim_id]}, cfg)
    state = result.get("result")
    if not result.get("ok") or not isinstance(state, dict):
        raise RuntimeError("Claim not readable yet")
    expected = {
        "review": ("FINALIZED", "NEEDS_REVIEW"),
        "challenge": ("CHALLENGED",),
        "retract": ("RETRACTED",),
        "supersede": ("SUPERSEDED",),
    }.get(op.stage)
    if expected and state.get("status") not in expected:
        raise RuntimeError("Contract claim state has not caught up with the finalized transaction")
    if op.stage == "supersede" and not state.get("superseded_by"):
        raise RuntimeError("Contract replacement is not readable yet")
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
        op.claim_id = replacement.id
        op.stage, op.status, op.tx_hash, op.error = "review", "queued", "", ""
        replacement.chain_status = "QUEUED"
        return
    state_status = state.get("status")
    if state_status in ("FINALIZED", "NEEDS_REVIEW", "CHALLENGED", "RETRACTED", "SUPERSEDED"):
        claim.status = state_status
    op.status, op.error = "done", ""
    event(db, claim, "FINALIZED", f"{op.stage} execution succeeded and finalized. Policy: {claim.chain_protocol_result}.")
