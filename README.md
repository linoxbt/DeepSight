# DeepSight

An astronomy research workspace with authenticated claim ownership, reproducible
TESS evidence, asynchronous analysis, and signed GenLayer relay operations.
Evidence sufficiency never means scientific confirmation.

## Run locally

Requires Python 3.12 and Node 22. Run each service in its own terminal:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.lock
npm ci --prefix api
DEEPSIGHT_ORIGIN=http://localhost:3000 .venv/bin/uvicorn api.main:app --port 8000
```

```bash
.venv/bin/python -m api.worker
```

```bash
cd apps/web
npm ci
npm run dev
```

Open http://localhost:3000. Connect a wallet, then **Sign in**. Sign-in verifies a
single-use message and creates an eight-hour HttpOnly session. It does not send
transactions. Analysis, imports, and radio screening run through the worker.
Reading public claims, manifests, and archive tools does not require sign-in.

The default database is `data/deepsight.db`. For PostgreSQL, set `DATABASE_URL`
to a `postgresql+psycopg://...` connection string for both API and worker. Existing
SQLite records are retained; legacy records have no authenticated owner and
cannot be adopted by arbitrary users. Rerun legacy analyses to create complete
evidence under your own identity.

## Architecture

- `api/auth.py`: wallet proofs, expiring sessions, origin checks, reviewer and operator roles.
- `api/jobs.py`, `api/worker.py`: durable analysis queue, bounded concurrency per
  researcher, failed-worker detection, and chain reconciliation.
- `api/evidence.py`: content-addressed JSON artifacts and pinned raw MAST FITS
  products. Production stores both in an S3-compatible bucket. Back up the
  database and bucket to retain evidence, sessions, jobs, and signed operations.
- `api/main.py`: archive routes, research workflows, claim lifecycle, downloads.
- `api/chain_ops.py`: claim-specific signed intents and durable chain outbox.
- `api/chain_client.mjs`: pinned Node SDK bridge; broadcasts return immediately.
- `api/policy.py`, `contracts/proof_of_discovery_v5.py`: mirrored bounded evidence
  predicates, with parity fixtures. Hashes bind bytes; policy results alone do
  not independently establish that the source measurements are true.
- `apps/web`: Next.js interface, session signing, queued runs, separate local and
  chain decisions, and evidence downloads.

Database-backed jobs avoid an additional queue service. Use PostgreSQL for shared
multi-process deployments. The legacy synchronous analysis/import endpoints are
retained for API compatibility and require authentication; the web app uses jobs.
Raw MAST products are pinned by SHA-256 and downloadable through `/v1/raw/{sha256}`.
Processed inputs and catalogue snapshots are immutable evidence artifacts.

## Evidence and reproducibility

Claim detail exposes canonical manifests and complete JSON evidence bundles.
Each embedded artifact preserves the exact bytes used for its SHA-256 hash.
Transit bundles include the full processed curve, catalogue query snapshot,
diagnostics, analysis parameters, package versions, and source checksums/code.
The raw FITS product is referenced by hash and URL in the manifest and must be
downloaded separately; the JSON bundle does not embed its binary bytes.
Period grid resolution is labeled separately from statistical uncertainty.

```bash
.venv/bin/python scripts/reproduce_bundle.py downloaded-bundle.json
.venv/bin/python scripts/reproduce_bundle.py downloaded-bundle.json --rerun
```

The rerun verifies local science code and dependency versions before execution;
it never executes source downloaded inside a bundle automatically.

## GenLayer relay

Configure the same settings on API and worker:

- `DEEPSIGHT_ORIGIN`: exact browser origin; HTTPS enables secure session cookies.
- `DEEPSIGHT_CONTRACT_ADDRESS`: actual deployed contract address.
- `DEEPSIGHT_RELAY_ADDRESS`: address of the optional legacy relay account. New claims default to wallet ownership and bind the researcher's address as the on-chain claimant.
- `DEEPSIGHT_KEYSTORE`, `DEEPSIGHT_CHAIN_PASSWORD`: encrypted relay account access.
- `DEEPSIGHT_RELAY_ENABLED=1`: explicitly enable broadcasting.
- `DEEPSIGHT_REVIEWERS`: comma-separated wallet addresses allowed to add review notes.
- `DEEPSIGHT_OPERATORS`: comma-separated wallet addresses authorized to reconcile
  chain operations with unknown broadcast outcomes. An operator must document
  independent nonce/explorer evidence before marking an attempt unbroadcast.
- `DEEPSIGHT_GIT_COMMIT`: optional exact 40- or 64-character deployed source
  revision. Railway's `RAILWAY_GIT_COMMIT_SHA` is used automatically when present;
  otherwise evidence records a checksum of the running Python sources.

New claims default to **wallet-owned GenLayer transactions**. The connected wallet
sends and pays for registration, evidence review, challenges, retractions, and
replacements. The API publishes the evidence before registration, verifies the
transaction sender, contract, method, and exact arguments on StudioNet, and the
worker waits for successful finality before recording an on-chain outcome.
The app asks for explicit publication consent before that preparation step;
publication still happens if the user later cancels the wallet transaction.
Registration and review are separate wallet confirmations. The browser retains
a pending transaction hash in local storage so it can be attached again after
an interrupted API response. Raw FITS and image bytes remain in content-addressed
storage; the canonical manifest and its artifact hashes are anchored on-chain.

Older relay-owned claims retain their signed-intent path. For those claims the
relay pays fees and is the on-chain claimant; the researcher signs a separate
operation message binding identity, origin, contract, manifest hash, action,
parameters, nonce, and expiry.

A signed operation enters the outbox. Registration must finalize successfully
before review is broadcast. `ACCEPTED` remains provisional. A finalized failed
execution is reported as a failure, not successful finality. Local policy preview
and chain policy outcomes have separate fields.

A live wallet-origin StudioNet test finalized registration, review, independent
challenge, replacement, replacement review, and retraction. The test used a
disposable EIP-1193 provider harness with an `eth_sendTransaction` handler;
human-operated Reown wallet confirmation remains a separate acceptance check.
The [registration](https://explorer-studio.genlayer.com/tx/0xe7faaea95f4c16a0745e75ff1b5e5e607f6df9f117e74fa82775a310fafc41e2)
and [review](https://explorer-studio.genlayer.com/tx/0x3274ea3522b3ca8275381381972093ed6c82d6957369deb0c883b4619349f9f6)
belong to hosted claim `clm_092f3f5afa85`.

`GET /v1/release` exposes the running API's source revision, source fingerprint,
configured contract address, and policy version without credentials. Compare its
`source_sha256` with the digest of the sorted `source_checksums` from
`api.evidence.environment()` in the exact source checkout. The deployment record
in [`deployments/studionet-v4.json`](deployments/studionet-v4.json) separately
records matching SHA-256 hashes for local contract source and deployed StudioNet
code. The live known-TIC catalogue-matching review is linked in
[`STEWARD_REVIEW.md`](STEWARD_REVIEW.md); matching a catalogue row does not
reproduce measurements from the FITS file.

On network read failures the worker retries reconciliation. If broadcasting
fails before returning a hash, the operation is marked `unknown` and blocks
further mutations: it is never blindly replayed. An operator must inspect the
network before resolving that uncertainty. The local status remains unchanged
until a chain mutation is successfully finalized.
`POST /v1/chain/operations/{id}/reconcile` accepts an observed transaction hash
or a documented confirmation that the original attempt was never broadcast.
The latter requeues the existing signed operation; it does not create a new intent.

Claims are private drafts until the owner publishes them or signs a chain
submission. Publication exposes the manifest, referenced evidence, and the
researcher's wallet address. The publish action requires an explicit
acknowledgement in the app. Existing submitted claims remain public after the
`0004` migration.

Installation and tests do not deploy contracts or submit live transactions.
Local lint and mock-based integration tests are not proof of live network behavior.
The contract in [`deployments/studionet.json`](deployments/studionet.json) was
deployed to StudioNet on 2026-10-16. Its deployment transaction finalized with
successful execution and the code at that address matched this repository.
On 2026-10-18, a disposable wallet signed a hosted claim intent; the Railway
worker registered `pod-1`, finalized its evidence review with
`EVIDENCE_SUFFICIENT`, and finalized a challenge signed by a second wallet.
The [contract](https://explorer-studio.genlayer.com/address/0x6B6dC06981Aa6903434dBab601D8b61c5fD57ff8)
and the [registration](https://explorer-studio.genlayer.com/tx/0xee82531b43197cec5a5c75ccd20d7d4a45cc311642014bcd7e9b0a1ee4ea4681),
[review](https://explorer-studio.genlayer.com/tx/0x1ea1cb6760137502d94975143332c5a60985c3f8eee885f5e9c04c8ea9955968),
and [challenge](https://explorer-studio.genlayer.com/tx/0x62fa28e1af641ce11bcfc0f4c52cbd99a70d30d4593e6c50784e4bd0d8c89973)
transactions are publicly inspectable. This is a development-network deployment;
it verifies protocol execution, not the scientific measurements in a manifest.
The [`celestial-v4` contract](deployments/studionet-v4.json) is deployed
at [0x5cfaE959BbFF6Be9e4A1F477abDCc61fAfD5eeb1](https://explorer-studio.genlayer.com/address/0x5cfaE959BbFF6Be9e4A1F477abDCc61fAfD5eeb1).
Its deployment finalized, deployed code matched this repository, and its read
method succeeded. Earlier contracts remain available for existing claims. V4
normalizes TAP numeric values and handles malformed or unavailable archive
responses within each validator. A live signed TESS registration and review
finalized on v4; the archive was unavailable to validators, so the on-chain
result was `NEEDS_HUMAN_REVIEW` with an explicit reason.
Validators query NASA TAP for an exact TIC and compare period and transit depth.
Unpublished candidates, archive mismatches, and radio observations remain in
human review. This does not reprocess source pixels or confirm a planet.
Deploy `ProofOfDiscovery` with the public HTTPS web origin as its constructor
argument. Validators fetch each published manifest from that fixed origin and
check its hash, target, and relay claimant before registration. The v4 review
adds a live NASA period-and-depth comparison for known TIC objects.

The v5 source in [`contracts/proof_of_discovery_v5.py`](contracts/proof_of_discovery_v5.py)
narrows a successful automated verdict to `CATALOGUE_CONSISTENT`: it compares
submitted values with NASA TAP but does not verify that they came from the
referenced FITS observation. V5 records one unadjudicated objection without
changing the underlying review status or result. Existing v4 claims stay on
their original contract; v5 routing requires a finalized, source-matched
`deployments/studionet-v5.json` record. No observational or radio signal
measurement is independently verified by this contract.

## Deployment

`docker-compose.yml` runs PostgreSQL, API, worker, and web. Supply
`POSTGRES_PASSWORD` in the environment, then run `docker compose up --build`.
The API applies versioned Alembic migrations before it starts; the worker
requires the resulting schema revision. For separately deployed services, run
`alembic upgrade head` once as a release step before starting either process.
`/v1/health` is process liveness. `/v1/ready` checks the database, worker
heartbeat, object store, and (in production) backup freshness; monitor the
latter for HTTP 503. The current schema revision is `0005`.
The relay is disabled in this default configuration. API and worker share the
archive volume. The Python image includes Node and the pinned adapter packages.

For separately hosted web and API services, set `API_PROXY` when building the
Next.js app and set `DEEPSIGHT_ORIGIN` to the public web origin. Keep the same
origin proxy for session cookies. Netlify builds fail if `API_PROXY` is absent
or does not use HTTPS; a loopback rewrite cannot serve a deployed site.

Set `DEEPSIGHT_S3_BUCKET` and standard AWS S3 credentials for durable evidence
objects. `DEEPSIGHT_S3_ENDPOINT` selects an S3-compatible service. Set
`DEEPSIGHT_REQUIRE_OBJECT_STORE=1` in production so new evidence cannot fall
back to database text when the bucket is missing. Keep independent, tested
backups of PostgreSQL and the bucket; object checksums are verified on read.
In production, Railway PITR is enabled for Postgres. The worker copies evidence
objects daily and creates a PostgreSQL 18 custom-format dump in a separate
recovery bucket. Each is read back and checksum-verified before its dated
completion manifest is written. Set `DEEPSIGHT_BACKUP_ENDPOINT`,
`DEEPSIGHT_BACKUP_BUCKET`, `DEEPSIGHT_BACKUP_ACCESS_KEY_ID`, and
`DEEPSIGHT_BACKUP_SECRET_ACCESS_KEY` on the worker. On 2026-10-18, the first
scheduled database dump was downloaded, checked, and restored into an isolated
PostgreSQL 18 instance with migration `0003` and expected row counts. To restore
one of these dumps, download `database/YYYY-MM-DD.dump` and its manifest,
verify the file SHA-256, then use `pg_restore --no-owner --no-privileges
--exit-on-error -d <empty-database> database/YYYY-MM-DD.dump` against a matching
PostgreSQL version. Railway's separate PITR restore failed on its default
500 MB volume; increase restore volume capacity before relying on that path.
The current workspace plan does not allow Railway scheduled backups, so the
worker's tested dump is the independent recovery path.
If the API is behind a reverse proxy, set `DEEPSIGHT_TRUSTED_PROXY_CIDRS` to
the proxy's exact source network before using `X-Forwarded-For` for rate limits.

## Checks

```bash
.venv/bin/python -m pytest -q
cd apps/web && npm run build
npm run test:browser  # uses local Google Chrome; set CHROME_PATH if needed
# From repository root, when the GenVM linter is installed:
genvm-lint check contracts/proof_of_discovery_v5.py
```

Tests cover signature replay and ownership, exact evidence retrieval, local/contract
policy parity, an Astropy reference comparison, job privacy, provisional/finalized
chain outcomes, and interrupted broadcast handling. They use isolated databases
and mocked chain calls. CI runs Python tests, the frontend production build, and browser workflow checks.

For a real local integration smoke test, run the production web app, Python API,
and `python -m api.worker` against the same database, with `DEEPSIGHT_ORIGIN`
set to the web origin. Then run `uv run python scripts/live_smoke.py`. The script
accepts loopback origins only, creates a disposable wallet and local claims, and
queries MAST, NASA Exoplanet Archive, Gaia, JPL Horizons, and Breakthrough Listen.
