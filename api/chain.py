"""GenLayer submission through the local StudioNet account.

A missing contract address is reported as not configured. This module does not
invent a transaction hash.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

from api.db import DATA_DIR

SUMMARY_PREFIX = "ds1:"
CLIENT = Path(__file__).with_name("chain_client.mjs")


class ChainError(Exception):
    def __init__(self, message: str, status_code: int = 502):
        super().__init__(message)
        self.status_code = status_code


def review_argument(manifest_text: str) -> str:
    return SUMMARY_PREFIX + manifest_text


def configured() -> bool:
    return load_config() is not None


def load_config() -> dict[str, str] | None:
    address = os.environ.get("DEEPSIGHT_CONTRACT_ADDRESS", "").strip()
    account = os.environ.get("DEEPSIGHT_CHAIN_ACCOUNT", "deepsight-studio").strip() or "deepsight-studio"
    password = os.environ.get("DEEPSIGHT_CHAIN_PASSWORD", "")
    keystore = os.environ.get("DEEPSIGHT_KEYSTORE", "").strip()
    ignore_file = os.environ.get("DEEPSIGHT_IGNORE_CHAIN_FILE") == "1"
    path = DATA_DIR / "chain.json"
    stored_address = ""
    if path.exists() and not ignore_file:
        stored = json.loads(path.read_text())
        stored_address = str(stored.get("address", "")).strip()
        account = str(stored.get("account", account))
        keystore = keystore or str(stored.get("keystore", "")).strip()
    deployment = Path(__file__).resolve().parent.parent / "deployments" / "studionet-v3.json"
    if not deployment.exists():
        deployment = deployment.with_name("studionet-v2.json")
    if not address and deployment.exists() and not ignore_file:
        recorded = json.loads(deployment.read_text())
        if recorded.get("network") == "studionet" and recorded.get("finalized_execution") == "SUCCESS":
            address = str(recorded.get("contract_address", "")).strip()
    address = address or stored_address
    password_path = DATA_DIR / "genlayer.password"
    if not password and password_path.exists() and not ignore_file:
        password = password_path.read_text().strip()
    if not address:
        return None
    if not keystore:
        keystore = str(Path.home() / ".genlayer" / "keystores" / f"{account}.json")
    return {"address": address, "account": account, "password": password, "keystore": keystore}


def invoke(payload: dict[str, Any], config: dict[str, str] | None = None) -> dict[str, Any]:
    config = config or _require()
    if payload.get("action") == "broadcast" and not config.get("password"):
        raise ChainError("The StudioNet account password is not available to this process.", 503)
    body = {
        **payload,
        "address": config["address"],
        "keystore": config["keystore"],
        "password": config["password"],
    }
    environment = os.environ.copy()
    try:
        completed = subprocess.run(
            ["node", str(CLIENT)],
            input=json.dumps(body),
            text=True,
            capture_output=True,
            timeout=90,
            check=False,
            env=environment,
        )
    except subprocess.TimeoutExpired as exc:
        raise ChainError("The GenLayer transaction did not reach a decided status in time.") from exc
    text = (completed.stdout or "").strip().splitlines()
    if not text:
        detail = (completed.stderr or "genlayer client produced no output").strip()
        raise ChainError(detail[-500:])
    try:
        parsed = json.loads(text[-1])
    except json.JSONDecodeError as exc:
        raise ChainError("The GenLayer client did not return JSON.") from exc
    if not isinstance(parsed, dict):
        raise ChainError("The GenLayer client returned an unexpected payload.")
    return parsed


def _require() -> dict[str, str]:
    config = load_config()
    if config is None:
        raise ChainError("No GenLayer contract address is configured.", 503)
    return config


def _nested_claim_id(value: Any) -> str:
    if isinstance(value, dict):
        for key in ("claim_id", "claimId"):
            if value.get(key):
                return str(value[key])
        for child in value.values():
            found = _nested_claim_id(child)
            if found:
                return found
    if isinstance(value, list):
        for child in value:
            found = _nested_claim_id(child)
            if found:
                return found
    if isinstance(value, str) and value.startswith("pod-"):
        return value
    return ""


def _return_value(receipt: Any) -> str:
    found = _find_key(receipt, "result")
    return found if isinstance(found, str) else ""


def _find_key(value: Any, key: str) -> Any:
    if isinstance(value, dict):
        if key in value and not isinstance(value[key], (dict, list)):
            return value[key]
        for child in value.values():
            found = _find_key(child, key)
            if found is not None:
                return found
    if isinstance(value, list):
        for child in value:
            found = _find_key(child, key)
            if found is not None:
                return found
    return None


def _note(claim_id: str, reviewed: dict[str, Any], chain_result: str) -> str:
    status = reviewed.get("status") or "undecided"
    execution = reviewed.get("execution") or "unknown"
    result = chain_result or "not returned"
    return (
        f"StudioNet claim {claim_id}. Transaction status {status}. Execution {execution}. "
        f"Chain policy result {result}. This is not a scientific confirmation, and ACCEPTED is not finality."
    )
