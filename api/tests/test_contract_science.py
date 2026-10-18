"""The consensus policy must never upgrade a self-reported candidate."""

import ast
import json
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import quote

from api.tests.test_policy import _base


def verifier(payload):
    tree = ast.parse(Path("contracts/proof_of_discovery.py").read_text())
    selected = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in
                {"_verify_archive_measurements", "_metric_value", "_ratio"}]
    web = SimpleNamespace(get=lambda _url: SimpleNamespace(body=json.dumps(payload).encode()))
    def strict_eq(work):
        rows = work()
        assert all(isinstance(value, str) for row in rows for value in row)
        return rows
    gl = SimpleNamespace(nondet=SimpleNamespace(web=web), eq_principle=SimpleNamespace(strict_eq=strict_eq))
    namespace = {"gl": gl, "json": json, "quote": quote}
    exec(compile(ast.Module(body=selected, type_ignores=[]), "contract-verifier", "exec"), namespace)
    return namespace["_verify_archive_measurements"]


def test_published_period_and_depth_must_both_match_exact_tic():
    document = _base()
    document["target"]["id"] = "TIC-259377017"
    document["scientific_status"] = "known_object"
    document["metrics"][0]["value"] = 5.66051
    document["metrics"][1]["value"] = 0.003451844
    row = {"tic_id": "TIC 259377017", "pl_orbper": 5.66051, "pl_trandep": 0.3451844}
    assert verifier([row])(document) == "matched"
    document["metrics"][1]["value"] = 0.1
    assert "does not match" in verifier([row])(document)
    assert "does not match" in verifier([{**row, "tic_id": "TIC 000000000"}])(document)


def test_unpublished_candidate_never_passes_external_comparison():
    document = _base()
    document["target"]["id"] = "TIC-259377017"
    assert "human review" in verifier([])(document)
