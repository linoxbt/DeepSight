# DeepSight

Local research workspace for the DeepSight Proof of Discovery specification.

The runnable path generates a calibration light curve, fits a box transit, writes a canonical evidence manifest, and applies the celestial evidence policy. Protocol results are `EVIDENCE_SUFFICIENT`, `EVIDENCE_INSUFFICIENT`, or `NEEDS_HUMAN_REVIEW`. None of those confirm a planet.

Explorer imports one TESS sector from MAST and can query NASA Exoplanet Archive TAP, Gaia DR3, and JPL Horizons. Radio lists Breakthrough Listen catalog rows and screens one public Voyager 1 calibration spectrum. Claims can be challenged, retracted, or submitted to a configured GenLayer StudioNet contract. The consensus rules live in `contracts/proof_of_discovery.py`. Set `DEEPSIGHT_LIVE_TAP=0` to keep cross-matches on the local extract.

## Run

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn api.main:app --port 8000
```

In a second shell:

```bash
cd apps/web
npm install
npm run dev
```

Open http://127.0.0.1:3000. The home page is a publication. Explorer, NASA TAP, Gaia, Horizons, the catalogue extract, source status, Discovery Lab, evidence, radio, discoveries, claims, review, and the protocol each have their own page. The menu button opens that list. Connect wallet uses Reown AppKit on GenLayer StudioNet.

## Deploy

Netlify builds `apps/web`. The astronomy API stays on a Python host. Set `API_PROXY` to that public URL at build time so `/v1` is rewritten to it. Without that variable, the published site has no analysis API. A contract address is recorded only after a StudioNet deploy receipt. This tree does not invent one.

## Tests

```bash
pytest
genvm-lint check contracts/proof_of_discovery.py
```
