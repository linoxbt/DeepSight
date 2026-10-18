# DeepSight audit remediation status

Updated 2026-10-18. **Not production ready.** The public Netlify site uses a dedicated Railway project with a live Python API, worker, PostgreSQL and S3-compatible bucket. The v3 GenLayer contract is finalized and the relay is enabled. Scientific source reproduction, live v3 consensus, and live social-login verification remain open. This release was deployed as Railway API `327e946b-9880-48d8-9ebf-8d519f4c86e3`, worker `a16ab979-e434-4cd9-af8e-afec3391a428`, and Netlify `6ad50ff94123ca89e3b15f67`.

## Current remediation

- Contract `celestial-v3` is at `0xadE6737f44b65b3Faeb7C0aCedd3b0fD23844a0a`; deployment execution succeeded and deployed code matched source. It converts NASA TAP numeric values to strings before GenLayer validator agreement. A v3 read-method check was blocked by StudioNet's 5,000-read daily limit. Unpublished candidates and radio measurements stay in human review.
- A live v2 TESS review failed on GenLayer's inability to encode floating-point TAP values; v3 fixes that boundary. A fresh v3 TESS analysis and signed claim were created, but StudioNet returned no transaction hash at registration. The outbox marked it `unknown` and did not replay it. The relay pending nonce remained 15, immediately after v3 deployment nonce 14. A successful live v3 archive review has **not** yet been demonstrated.
- Live disposable-wallet v2 submit/review, supersession and retraction finalized on StudioNet. Claim `clm_3ce8c291c763` became `SUPERSEDED` by `clm_704cc4eb15eb`, which became `RETRACTED`.
- EOA and deployed EIP-1271 message signature verification are wired to sign-in and each relay intent. Unit tests cover both formats and RPC failure. Reown email/Google consent has not been completed live, so social login remains unverified.
- Railway Postgres PITR is enabled. A separate PITR restore failed because its default 500 MB volume filled during WAL replay. The worker now makes daily, checksum-verified evidence and PostgreSQL custom-format snapshots in a separate private bucket. Its first scheduled database dump restored into isolated PostgreSQL 18 with 8 claims, 9 analyses, 10 artifacts, 9 chain operations, and migration `0003`; the latest evidence copy verified 13 objects. Railway scheduled backups are unavailable on this workspace plan.
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
| Database schema and durable evidence storage | Alembic revisions 0001–0003 applied on Railway Postgres; S3-backed private image upload, read and checksum passed through the public site. Daily independent object and database backups passed read-back verification, and the scheduled database dump restored into isolated PostgreSQL 18. |
| GenLayer result parser | Handles `FINISHED_WITH_RETURN`; Node test. Invalid post-finality appeal was removed. |
| Live GenLayer integration | Disposable EOA signed a hosted intent; worker registered `pod-1` on the deployed contract, finalized evidence review as `EVIDENCE_SUFFICIENT`, and finalized a challenge signed by a second wallet. The API reflected all three transaction outcomes. |
| Netlify build configuration | `API_PROXY` points to the healthy Railway API; public `/v1/health` returns 200. |
| Gaia public timeout | The Netlify proxy timed out on a live 36-second Gaia TAP query. The public read-only Gaia form now calls Railway directly; the API CORS preflight permits the Netlify origin. A live Chromium form submission returned one Gaia source. |
| Public dashboard | The live browser loaded a real TESS claim from the hosted API. The claim projection now maps the manifest's `period` metric to the dashboard's `period_days` field; a regression test covers the mapping. The dashboard labels records as research claims rather than finalized publications. |
| Public draft exposure | Unsigned claims and their JSON evidence are owner-only until explicit publication or signed chain submission. Existing submitted claims remain public. Owner/anonymous regression test passes. |
| Raw MAST provenance | The exact FITS product is pinned in object storage by SHA-256 and linked in the manifest. Submission refuses a missing or corrupted pinned product. The JSON evidence bundle links to the binary product separately. |
| Chain broadcast uncertainty | Designated operators can attach a network-visible transaction hash or document a verified non-broadcast and requeue the original signed operation. The endpoint is audited and role-restricted. A live uncertain operation still needs manual reconciliation. |
| Build identification and contract link | Evidence records a deployed commit SHA or source checksum; the frontend links to the deployed v3 contract. |
| Service dependency health | `/v1/ready` checks database, worker heartbeat, object store, and production backup freshness. The worker persists each successful backup heartbeat. This does not replace external alert delivery. |
| Worker queue saturation and charts | Global active/rate limits prevent unbounded job backlog. Light-curve and radio plots expose axis labels, hover values and CSV export. |
| Netlify HTML hydration | Netlify inserts a newline and comment into the production document head. A small synchronous head script removes those injected nodes before React hydrates. Both a controlled injected-HTML browser test and the deployed production page had zero React page errors; the live wallet modal remained open and displayed email and Google controls. |

## Open blockers

| Severity | Finding | Required completion |
| --- | --- | --- |
| High | Radio measurements have no independent archive comparison and the Voyager calibration is not an open-ended signal search. | Add an independently sourced archive comparison before claiming validator-verified radio measurements. |
| High | The v3 known-TIC comparison has not passed a live consensus review. A v2 review hit a float-encoding error; v3 fixes the encoding, but the first v3 registration returned no hash. StudioNet also exhausted its daily read-call allowance. | Reconcile the uncertain registration, restore RPC quota/funding as needed, and complete a signed v3 register/review with verified on-chain rationale. |
| High | The current v3 validator compares NASA catalogue period/depth; it does not recompute the submitted light curve from the pinned raw FITS or rerun BLS independently. | Design and deploy a bounded verifier for raw-source measurements, then prove it with a live consensus review. Until then label results as evidence review only. |
| Medium | Railway PITR's default-size isolated restore failed; the independent daily database dump was restored successfully, but PITR and operational alerting remain unproven. | Increase restore volume capacity, rerun PITR restore, and add backup failure/staleness alerts. |
| High | The live Reown modal displays email and Google on the allowlisted primary domain after asynchronous initialization, but neither consent flow nor a social-wallet signature has been completed end to end. EIP-1271 support has only mocked-RPC coverage. | Complete a real social-wallet sign-in and claim signature on the hosted site, including a deployed smart-account case if Reown issues one. Preview domains are not in Reown's allowed origins and correctly reject embedded-wallet login. |
| High | `DEEPSIGHT_OPERATORS` and `DEEPSIGHT_REVIEWERS` are not configured in the production API; operator reconciliation and designated human review cannot be exercised by real staff accounts. | Assign controlled wallet addresses, set the variables on API and worker where needed, then run signed live role tests. |
| Medium | Image upload is a private visual notebook and does not process FITS data or detect planets. | Define and implement a scientifically valid image workflow only if required by the product. |
| Medium | MCP, persistent collaborative notebooks and Redis from the broader architecture are absent. | Prioritize after the deployed TESS workflow and evidence chain are reliable. |
| Medium | No scheduled archive availability or snapshot-comparison monitor. | Add live smoke monitoring and scientific source review. |
| Medium | Pre-finality consensus appeal has no supported UI or signed relay flow. | Implement only against StudioNet's authoritative appeal-window lifecycle; do not offer appeal on finalized claims. |
| Medium | Readiness has a diagnostic endpoint but no external alert receiver; the Railway health check still targets process liveness. | Add an external monitor of `/v1/ready` and page an operator on stale worker/backup. |
| Medium | A binary MAST FITS product is separately downloadable; the JSON bundle is not one self-contained archive. | Offer a ZIP export when portable single-file scientific reproduction is required. |

## Verification

- Latest full backend suite: `uv run pytest -q api/tests`: 84 passed. A focused post-fix subset: 53 passed.
- `node --test api/tests/chain_execution.test.mjs`: passed.
- `npm run build --prefix apps/web`: passed; `npm run test:browser --prefix apps/web`: 11 passed. Browser tests mock API data.
- Isolated PostgreSQL 16: Alembic upgraded through 0005; `DEEPSIGHT_REQUIRE_MIGRATIONS=1` startup check passed. SQLite migration checks passed.
- `uv pip install -r requirements.lock --dry-run`, `POSTGRES_PASSWORD=dev-only-validation docker compose config --quiet`, and `git diff --check`: passed.
- Public Netlify-to-Railway live smoke passed: health and registry reads; disposable EOA challenge, signature session and logout; private S3 image upload/read/notes; queued MAST import, BLS analysis, evidence preflight and local claim bundle; radio worker analysis. Test records remain private to their disposable wallets.
- This release's live checks: `/v1/ready` returned 200 through both Railway and Netlify with all five dependencies true; both Railway deployments reported `SUCCESS`; the Netlify landing page returned 200 and its GenLayer badge linked to v3. A disposable EOA signed in, created a claim, and proved anonymous claim/manifest/bundle reads return 404. An artifact reused from a previously public claim remains public by design. A fresh MAST import stored and served a 1,998,720-byte FITS product with matching SHA-256 `375c0a83...92838b04c81`; a queued BLS analysis and private manifest referenced that exact hash. Railway API HTTP logs showed no 5xx responses during the final review.
- Public NASA TAP, JPL Horizons, Breakthrough Listen and direct Railway Gaia calls returned live results. The deployed Gaia page returned a live source through Chromium after bypassing the timed-out proxy.
- Hosted GenLayer registration `0xee82531b...`, review `0x1ea1cb67...`, and independent challenge `0x62fa28e1...` finalized successfully on StudioNet. Reown social sign-in still needs independent live verification.
