# DeepSight audit remediation status

Updated 2026-10-18. **Deployed, but not production ready.** The public Netlify site uses a dedicated Railway project with a live Python API, worker, PostgreSQL and S3-compatible bucket. `/v1/health` returns HTTP 200. The v3 GenLayer contract is finalized and the relay is enabled. Scientific source reproduction and live social-login verification remain open.

## Current remediation

- Contract `celestial-v3` is at `0xadE6737f44b65b3Faeb7C0aCedd3b0fD23844a0a`; deployment execution succeeded and deployed code matched source. It converts NASA TAP numeric values to strings before GenLayer validator agreement. A v3 read-method check was blocked by StudioNet's 5,000-read daily limit. Unpublished candidates and radio measurements stay in human review.
- A live v2 TESS review failed on GenLayer's inability to encode floating-point TAP values; v3 fixes that boundary. A fresh v3 TESS analysis and signed claim were created, but StudioNet returned no transaction hash at registration. The outbox marked it `unknown` and did not replay it. The relay pending nonce remained 15, immediately after v3 deployment nonce 14. A successful live v3 archive review has **not** yet been demonstrated.
- Live disposable-wallet v2 submit/review, supersession and retraction finalized on StudioNet. Claim `clm_3ce8c291c763` became `SUPERSEDED` by `clm_704cc4eb15eb`, which became `RETRACTED`.
- EOA and deployed EIP-1271 message signature verification are wired to sign-in and each relay intent. Unit tests cover both formats and RPC failure. Reown email/Google consent has not been completed live, so social login remains unverified.
- Railway Postgres PITR is enabled. A separate PITR restore failed because its default 500 MB volume filled during WAL replay. A portable production SQL dump restored into isolated PostgreSQL with 2 claims, 4 analyses, 7 artifacts and migration `0003`. An 11-object evidence copy passed SHA-256 checks. Both archives were uploaded to a separate private recovery bucket and read back. The worker now runs a daily copy; its latest logged snapshot verified 12 objects. Railway scheduled database backups are unavailable on this workspace plan.
- The old UI's post-finality appeal action was invalid under GenLayer's appeal window. The no-op live appeal was marked failed and the UI/API no longer offer that action. A correct pre-finality appeal workflow remains unimplemented.

## Verified fixes

| Finding | Status and evidence |
| --- | --- |
| Nearby catalogue match could be presented as the target | Exact TIC/host matching and regression test. |
| Split, revocable auth and public private data | Database-backed challenge/session/logout, owner-scoped analyses/artifacts, replay/revocation tests. |
| Stale or retried chain operations | Outbox waits for final state and respects retry deadlines. Invalid post-finality appeal was disabled after a live no-op exposed the gap. |
| Published claim provenance | Fixed origin, manifest hash, target, and relay claimant checks in deployed contract. V3 additionally compares known-TIC period and depth to live NASA TAP rows, but does **not** reprocess source artifacts. The v3 live review remains unproven. |
| Premature Discoveries and supersession | Feed requires finalized chain evidence; replacement manifests are published before broadcast; regression tests. |
| Scientific uncertainty and source status | Conditional residual bootstrap, quality warnings, and explicit unverified source status. Independent scientific review remains open. |
| Human-review race and self-review | Two independent matching attestations required for resolution; transaction lock and conflict disclosure; regression tests. |
| Unbounded archive downloads and costly routes | Download size limits, Voyager checksum, account/global direct-route budgets shared across IPs, and queued job cap with database locking and heartbeats; tests. |
| Proxy identity spoofing | Forwarded client IP accepted only from configured trusted CIDRs; deployment CIDRs still need configuration. |
| Large unpaged record queries | Claims cursor pagination, bounded discoveries/reviews queries, frontend load-more control. |
| Login and wallet UI race | Session restore cannot overwrite a newer sign-in/out; connected-wallet account control remains distinct from app sign-out; browser tests. |
| Image notebook was browser-only | Authenticated, owner-scoped JPG/PNG/WebP upload, private file download, saved notes/marks, checksum validation, failed-commit cleanup, browser save/reopen check, and retry feedback. This is a visual notebook, not scientific image analysis. |
| Database schema and durable evidence storage | Alembic revisions 0001–0003 applied on Railway Postgres; S3-backed private image upload, read and checksum passed through the public site. Backup/restore drill remains open. |
| GenLayer result parser | Handles `FINISHED_WITH_RETURN`; Node test. Invalid post-finality appeal was removed. |
| Live GenLayer integration | Disposable EOA signed a hosted intent; worker registered `pod-1` on the deployed contract, finalized evidence review as `EVIDENCE_SUFFICIENT`, and finalized a challenge signed by a second wallet. The API reflected all three transaction outcomes. |
| Netlify build configuration | `API_PROXY` points to the healthy Railway API; public `/v1/health` returns 200. |
| Gaia public timeout | The Netlify proxy timed out on a live 36-second Gaia TAP query. The public read-only Gaia form now calls Railway directly; the API CORS preflight permits the Netlify origin. A live Chromium form submission returned one Gaia source. |
| Public dashboard | The live browser loaded a real TESS claim from the hosted API. The claim projection now maps the manifest's `period` metric to the dashboard's `period_days` field; a regression test covers the mapping. The dashboard labels records as research claims rather than finalized publications. |

## Open blockers

| Severity | Finding | Required completion |
| --- | --- | --- |
| High | Validators compare known TIC period and depth against NASA TAP, but do not reprocess raw TESS pixels or independently verify the artifact contents; radio measurements have no independent archive comparison. | Build a reproducible source-data verification service or validator-bounded proof before treating the measurements themselves as verified. |
| High | The v3 known-TIC comparison has not passed a live consensus review. A v2 review hit a float-encoding error; v3 fixes the encoding, but the first v3 registration returned no hash. StudioNet also exhausted its daily read-call allowance. | Reconcile the uncertain registration, restore RPC quota/funding as needed, and complete a signed v3 register/review with verified on-chain rationale. |
| High | Railway PITR's default-size isolated restore failed; portable restore passed, but database backup automation and operational alerts are not proven. | Increase restore volume capacity, rerun PITR restore, and add an independent scheduled database export/monitor. |
| High | Reown email/Google consent remains unverified live. EIP-1271 support has only mocked-RPC coverage. | Complete a real social-wallet sign-in and claim signature on the hosted site, including a deployed smart-account case if Reown issues one. |
| Medium | Image upload is a private visual notebook and does not process FITS data or detect planets. | Define and implement a scientifically valid image workflow only if required by the product. |
| Medium | MCP, persistent collaborative notebooks and Redis from the broader architecture are absent. | Prioritize after the deployed TESS workflow and evidence chain are reliable. |
| Medium | No scheduled archive availability or snapshot-comparison monitor. | Add live smoke monitoring and scientific source review. |
| Medium | Pre-finality consensus appeal has no supported UI or signed relay flow. | Implement only against StudioNet's authoritative appeal-window lifecycle; do not offer appeal on finalized claims. |

## Verification

- Latest run after v3: `uv run pytest -q api/tests`: 77 passed.
- `node --test api/tests/chain_execution.test.mjs`: passed.
- `npm run build --prefix apps/web`: passed; `npm run test:browser --prefix apps/web`: 11 passed after the final test cleanup. Browser tests mock API data.
- PostgreSQL 16: Alembic upgraded through 0003; `DEEPSIGHT_REQUIRE_MIGRATIONS=1` startup check passed. SQLite fresh/upgrade checks passed.
- `uv pip install -r requirements.lock --dry-run`, `POSTGRES_PASSWORD=dev-only-validation docker compose config --quiet`, and `git diff --check`: passed.
- Public Netlify-to-Railway live smoke passed: health and registry reads; disposable EOA challenge, signature session and logout; private S3 image upload/read/notes; queued MAST import, BLS analysis, evidence preflight and local claim bundle; radio worker analysis. Test records remain private to their disposable wallets.
- Public NASA TAP, JPL Horizons, Breakthrough Listen and direct Railway Gaia calls returned live results. The deployed Gaia page returned a live source through Chromium after bypassing the timed-out proxy.
- Hosted GenLayer registration `0xee82531b...`, review `0x1ea1cb67...`, and independent challenge `0x62fa28e1...` finalized successfully on StudioNet. Reown social sign-in still needs independent live verification.
