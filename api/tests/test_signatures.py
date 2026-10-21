from eth_account import Account
from eth_account.messages import encode_defunct

from api import signatures


def test_eoa_signature_and_wrong_wallet():
    wallet = Account.create()
    proof = Account.sign_message(encode_defunct(text="DeepSight challenge"), wallet.key).signature.hex()
    assert signatures.valid_message_signature(wallet.address, "DeepSight challenge", proof)
    assert not signatures.valid_message_signature(Account.create().address, "DeepSight challenge", proof)


def test_deployed_contract_signature_uses_1271_magic(monkeypatch):
    address = "0x" + "a" * 40
    calls = []

    def rpc(_url, method, params):
        calls.append((method, params))
        return "0x6000" if method == "eth_getCode" else "0x1626ba7e" + "0" * 56

    monkeypatch.setattr(signatures, "_rpc", rpc)
    assert signatures.valid_message_signature(address, "signed message", "0x" + "ab" * 65)
    assert [item[0] for item in calls] == ["eth_getCode", "eth_call"]
    assert calls[1][1][0]["to"] == address


def test_1271_rpc_failure_fails_closed(monkeypatch):
    def fail(*_args):
        raise ValueError("unavailable")

    monkeypatch.setattr(signatures, "_rpc", fail)
    assert not signatures.valid_message_signature("0x" + "b" * 40, "message", "0x" + "cd" * 65)
