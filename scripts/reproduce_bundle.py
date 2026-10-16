"""Verify exact evidence bytes and optionally rerun the transit search locally."""
import argparse
import hashlib
import json
from pathlib import Path
import sys


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("bundle", type=Path)
    parser.add_argument("--rerun", action="store_true")
    args = parser.parse_args()
    bundle = json.loads(args.bundle.read_text())
    digest = lambda text: hashlib.sha256(text.encode()).hexdigest()
    if digest(bundle["manifest"]) != bundle["manifest_sha256"]:
        raise SystemExit("Manifest checksum mismatch")
    for checksum, content in bundle["artifacts"].items():
        if digest(content) != checksum:
            raise SystemExit(f"Artifact checksum mismatch: {checksum}")
    manifest = json.loads(bundle["manifest"])
    print(f"Verified manifest and {len(bundle['artifacts'])} exact artifacts")
    if not args.rerun:
        return
    if manifest["claim_type"] != "celestial_object_evidence":
        raise SystemExit("Automatic rerun currently supports transit bundles only")
    environment = json.loads(bundle["artifacts"][manifest["analysis"]["environment_sha256"]])
    root = Path(__file__).resolve().parent.parent
    science_file = root / "api" / "science.py"
    if hashlib.sha256(science_file.read_bytes()).hexdigest() != environment["source_checksums"]["science.py"]:
        raise SystemExit("Local science code differs from bundle; use the recorded source before rerunning")
    sys.path.insert(0, str(root))
    import importlib.metadata
    for package in ("numpy", "astropy"):
        if importlib.metadata.version(package) != environment["packages"][package]:
            raise SystemExit(f"Install recorded {package} version {environment['packages'][package]}")
    import numpy as np
    from api.science import fit_transit
    artifact = next(item for item in manifest["artifacts"] if item["kind"] == "light_curve")
    series = json.loads(bundle["artifacts"][artifact["sha256"]])
    fit = fit_transit(np.asarray(series["time_days"]), np.asarray(series["flux"]))
    recorded = next(item["value"] for item in manifest["metrics"] if item["name"] == "period")
    if abs(fit.period_days - recorded) > 0.000001:
        raise SystemExit("Recomputed period differs from recorded period")
    print(f"Reproduced period: {fit.period_days:.6f} d; depth: {fit.depth:.6f}")


if __name__ == "__main__":
    main()
