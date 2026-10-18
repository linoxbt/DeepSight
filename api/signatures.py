"""EIP-191 EOA and EIP-1271 deployed smart-account message proofs."""

import os

import httpx
from eth_abi import encode
from eth_account import Account
from eth_account.messages import defunct_hash_message, encode_defunct


def valid_message_signature(address: str, message: str, signature: str) -> bool:
    address = address.lower()
    try:
        if Account.recover_message(encode_defunct(text=message), signature=signature).lower() == address:
            return True
    except Exception:
        pass
    # EIP-1271 is checked on the same StudioNet chain selected in AppKit.
    # A remote RPC failure fails closed; it never grants a session.
    rpc = os.environ.get("DEEPSIGHT_EVM_RPC", "https://studio.genlayer.com/api")
    try:
        code = _rpc(rpc, "eth_getCode", [address, "latest"])
        if not isinstance(code, str) or code in ("0x", "0x0", "0x00"):
            return False
        digest = defunct_hash_message(text=message)
        calldata = "0x1626ba7e" + encode(["bytes32", "bytes"], [digest, bytes.fromhex(signature.removeprefix("0x"))]).hex()
        result = _rpc(rpc, "eth_call", [{"to": address, "data": calldata}, "latest"])
        return isinstance(result, str) and result.lower().startswith("0x1626ba7e")
    except (ValueError, TypeError, httpx.HTTPError):
        return False


def _rpc(url: str, method: str, params: list):
    response = httpx.post(url, json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params}, timeout=8)
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict) or "error" in payload:
        raise ValueError("EVM RPC rejected signature verification")
    return payload.get("result")
