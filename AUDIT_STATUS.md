# DeepSight audit remediation status

Updated 2026-10-16. The project is **not production ready**. The public Netlify site still returns HTTP 500 for `/v1/health`; no public Python API, worker, or PostgreSQL service is configured. The GenLayer contract has been deployed to StudioNet, with a finalized successful deployment and matching code, but its claim lifecycle has not been exercised live.

## Verified fixes

| Finding | Status | Evidence |
| --- | --- | --- |
| Coordinate fallback could label a nearby published planet as the target | Fixed | Exact TIC/host matching and regression test in `api/tests/test_archives.py` |
| Revocable auth was split between Netlify blobs and Python | Fixed in code | One database-backed challenge/session/logout flow; replay and revocation tests |
| Private analyses and unpublished artifacts were public | Fixed in code | Owner checks, artifact grants, private cache headers, regression test |
| Chain outbox treated stale reads as finalized operations | Fixed in code | Expected state checks and stale-read regression test |
| Supersession used an unpublished replacement manifest | Fixed in code | Signed intent creates a pending published record before broadcast; regression test |
| Contract trusted only the submitted manifest bytes | Partially fixed | Fixed HTTPS origin, GenLayer validator fetch, hash, target and relay claimant checks; GenVM lint passes. Scientific measurements and archive snapshots are not independently verified. |
| Claims could be front-run by another on-chain sender | Fixed in new contract code | Published manifest binds the relay claimant; researcher is separately recorded. Requires new contract deployment. |
| Local policy previews appeared in Discoveries | Fixed | Feed requires successful finalized chain evidence decision; regression test |
| No period uncertainty / false-positive warnings | Partially fixed | Conditional residual bootstrap, explicit uncertainty method, and quality warnings. This is not an independent astrophysical validation. |
| Reviewer notes lacked decision and conflict declaration | Fixed in code | Reviewer attestation model, self-review rejection, review form and display |
| Archive/source status asserted unverified connectivity | Fixed in code | External reachability is marked unverified until actually queried |
| Radio/MAST downloads lacked bounded integrity controls | Fixed in code | Size limits and pinned Voyager sample checksum; source authenticity remains a deployment concern |
| Costly public operations lacked budgets | Fixed in code | Database-backed request limits; limits behind a shared reverse proxy need live tuning |
| Job polling was fixed at two seconds | Fixed | Bounded backoff and visible progress |
| Netlify silently rewrote API calls to its own loopback | Fixed for future builds | Netlify build now rejects missing/non-HTTPS `API_PROXY`; public service is still unavailable |
| Claim detail and catalogue/discovery pages mishandled partial/API errors | Fixed | Guarded requests, independent detail loading, visible errors |

## Open release blockers

| Severity | Finding | Required completion |
| --- | --- | --- |
| Critical | The public API returns HTTP 500 because no backend target exists. Railway rejected project creation with a free-plan resource limit. | Provision an isolated public API, worker, PostgreSQL and durable evidence store; configure `API_PROXY` and `DEEPSIGHT_ORIGIN`; run live end-to-end checks. |
| High | StudioNet contract is deployed, but no real claim lifecycle write has been tested. | Deploy the public evidence API, configure relay credentials and funds, then test registration, review, supersession, challenge and finality against the deployed address. |
| High | Validators confirm published bytes and field structure, but do not independently verify archive snapshots, measurements or artifact contents. | Add bounded independent source and artifact verification before treating `EVIDENCE_SUFFICIENT` as a robust provenance decision. |
| High | Evidence artifacts are stored as database text, with no external object storage, retention policy or restore drill. | Provision durable object storage, migrations, backup/restore and lifecycle policies. |
| High | Reown email/Google and contract-wallet signatures have not been tested against a live API; backend verifies EOA signatures only. | Exercise both login paths and add supported contract-wallet signature verification if Reown issues a smart-account address. |
| Medium | The image upload is a local visual notebook; it does not ingest science data or persist a collaborative workspace. | Implement authenticated upload/object storage and a clearly scoped image-analysis workflow. |
| Medium | MCP services, persistent research notebooks and Redis are absent from the revised architecture. | Implement after the core deployed TESS workflow is reliable. |
| Medium | Live external-archive queries work, but there is no scheduled availability test or source snapshot comparison. | Add scheduled live smoke checks and independent scientific review. |

## Local verification

- `uv run pytest -q api/tests`: 63 passed.
- Live MAST fetched TIC 259377017 sector 30 (16,436 usable cadences); NASA Exoplanet Archive, Gaia DR3, and JPL Horizons queries returned real data.
- `npm run build --prefix apps/web`: passed.
- `npm run test:browser --prefix apps/web`: 9 passed with mocked API responses.
- `genvm-lint check contracts/proof_of_discovery.py`: passed.
- `POSTGRES_PASSWORD=dev-only-validation docker compose config --quiet`: passed.
- `git diff --check`: passed.

Local and mocked checks do not substitute for deployed API, storage, wallet and GenLayer tests.
