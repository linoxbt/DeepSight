# DeepSight audit remediation status

Updated 2026-10-16. **Deployed, but not production ready.** The public Netlify site now proxies to a dedicated Railway project with a live Python API, worker, PostgreSQL and S3-compatible bucket. `/v1/health` returns HTTP 200. The on-chain relay is still disabled pending signer deployment and a finalized StudioNet lifecycle test; scientific provenance and social-login gaps also remain.

## Verified fixes

| Finding | Status and evidence |
| --- | --- |
| Nearby catalogue match could be presented as the target | Exact TIC/host matching and regression test. |
| Split, revocable auth and public private data | Database-backed challenge/session/logout, owner-scoped analyses/artifacts, replay/revocation tests. |
| Stale or retried chain operations | Outbox waits for final state, respects retry deadlines, checks appeal rounds and final outcome; regression tests. |
| Published claim provenance | Fixed origin, manifest hash, target, and relay claimant checks in deployed contract. This does **not** independently verify archive measurements or artifacts. |
| Premature Discoveries and supersession | Feed requires finalized chain evidence; replacement manifests are published before broadcast; regression tests. |
| Scientific uncertainty and source status | Conditional residual bootstrap, quality warnings, and explicit unverified source status. Independent scientific review remains open. |
| Human-review race and self-review | Two independent matching attestations required for resolution; transaction lock and conflict disclosure; regression tests. |
| Unbounded archive downloads and costly routes | Download size limits, Voyager checksum, account/global direct-route budgets shared across IPs, and queued job cap with database locking and heartbeats; tests. |
| Proxy identity spoofing | Forwarded client IP accepted only from configured trusted CIDRs; deployment CIDRs still need configuration. |
| Large unpaged record queries | Claims cursor pagination, bounded discoveries/reviews queries, frontend load-more control. |
| Login and wallet UI race | Session restore cannot overwrite a newer sign-in/out; connected-wallet account control remains distinct from app sign-out; browser tests. |
| Image notebook was browser-only | Authenticated, owner-scoped JPG/PNG/WebP upload, private file download, saved notes/marks, checksum validation, failed-commit cleanup, browser save/reopen check, and retry feedback. This is a visual notebook, not scientific image analysis. |
| Database schema and durable evidence storage | Alembic revisions 0001–0003 applied on Railway Postgres; S3-backed private image upload, read and checksum passed through the public site. Backup/restore drill remains open. |
| GenLayer result parser | Handles `FINISHED_WITH_RETURN` and exposes appeal round data; Node test. |
| Netlify build configuration | `API_PROXY` points to the healthy Railway API; public `/v1/health` returns 200. |

## Open blockers

| Severity | Finding | Required completion |
| --- | --- | --- |
| High | Relay is disabled and StudioNet contract has not completed a live claim/review/challenge/appeal lifecycle. | Deploy encrypted signer to worker, then test finalized writes and reads against the deployed contract. |
| High | Validators verify manifest bytes and structure, but not independent archive snapshots, measurements or artifact contents. | Add bounded independent verification and redeploy before treating an evidence-sufficient outcome as robust provenance. |
| High | Hosted Postgres and bucket have no verified backup/restore drill, retention policy or monitoring. | Perform and document restore drill and operational alerts. |
| High | Reown email/Google and smart-account signatures remain unverified live; backend currently verifies EOA signatures. | Exercise both social paths against hosted API and support the issued account's signature type. |
| Medium | Image upload is a private visual notebook and does not process FITS data or detect planets. | Define and implement a scientifically valid image workflow only if required by the product. |
| Medium | MCP, persistent collaborative notebooks and Redis from the broader architecture are absent. | Prioritize after the deployed TESS workflow and evidence chain are reliable. |
| Medium | No scheduled archive availability or snapshot-comparison monitor. | Add live smoke monitoring and scientific source review. |

## Verification

- `uv run pytest -q api/tests`: 69 passed.
- `node --test api/tests/chain_execution.test.mjs`: passed.
- `npm run build --prefix apps/web`: passed; `npm run test:browser --prefix apps/web`: 11 passed after the final test cleanup. Browser tests mock API data.
- PostgreSQL 16: Alembic upgraded through 0003; `DEEPSIGHT_REQUIRE_MIGRATIONS=1` startup check passed. SQLite fresh/upgrade checks passed.
- `uv pip install -r requirements.lock --dry-run`, `POSTGRES_PASSWORD=dev-only-validation docker compose config --quiet`, and `git diff --check`: passed.
- Public Netlify-to-Railway live smoke passed: health and registry reads; disposable EOA challenge, signature session and logout; private S3 image upload/read/notes; queued MAST import, BLS analysis, evidence preflight and local claim bundle; radio worker analysis. Test records remain private to their disposable wallets.
- Earlier local live smoke exercised NASA/ESA/JPL/Breakthrough Listen queries. Public archive calls, GenLayer writes and social sign-in still need independent live verification.
