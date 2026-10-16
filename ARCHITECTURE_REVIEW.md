# DeepSight implementation assessment

Review date: 2026-10-15. Scope: local repository, revised build specification,
source inspection, existing checks, and isolated behavioral probes. Live archive
availability, the published frontend, and deployed contract execution were not
verified. This is an implementation assessment, not a complete security audit.

## Implementation follow-through

The rebuild following this assessment adds signed wallet sessions, authenticated
claim ownership, reviewer permissions, exact content-addressed evidence and
bundle downloads, database-backed jobs, PostgreSQL support, per-operation wallet
authorization, a durable chain outbox, and finality reconciliation. See README.md
for the current architecture and run instructions. Findings below describe the
pre-rebuild baseline and are retained as the rationale for these changes. Live
contract execution still requires verification against a deployed contract.

## Assessment

DeepSight is a functional local research prototype. It implements a coherent
TESS analysis-to-evidence-to-local-review workflow, with a GenLayer contract and
submission adapter. The revised specification's production and finalized-chain
release gates remain incomplete. Radio provides a calibration demonstration.

The clearest strength is the separation between protocol evidence sufficiency
and scientific confirmation. Synthetic data, catalogue coincidences, known
objects, and radio calibration limitations are explicitly labeled.

## Current architecture

```text
Next.js 15 / React 19 / TypeScript
  page-local fetch calls, custom plots, Reown wallet connection
                     |
                 /v1 proxy
                     |
FastAPI application (api/main.py)
  |-- MAST/TESS, NASA TAP, Gaia, JPL, Breakthrough Listen clients
  |-- NumPy box transit search and HDF5 radio screening
  |-- Canonical evidence manifests and local policy evaluation
  |-- SQLAlchemy / SQLite: datasets, analyses, radio analyses, claims, events
  |-- Local archive cache
  `-- Python subprocess -> Node SDK -> GenLayer StudioNet
                                      |
                            ProofOfDiscovery contract
```

The backend is a modular monolith, although request orchestration and claim
transitions are concentrated in a 936-line main module. Expensive analyses,
downloads, and chain waits execute during HTTP requests. There is no worker
queue, durable job state, or chain reconciliation process.

The contract checks manifest hash binding, claimant ownership for applicable
updates, duplicate registration, and policy fields. It does not fetch artifacts
or independently verify the underlying science. The local policy implementation
duplicates the contract rules and needs parity testing.

## Specification coverage

| Milestone | Evidence in repository | Remaining release gate |
| --- | --- | --- |
| M0 Foundation | Frontend, archive clients, API, SQLite | Authentication, jobs, durable object storage |
| M1 Real science | Single-sector TESS import, custom BLS-like search, diagnostics | Reproducible downloadable bundle, broader scientific validation, stronger uncertainty treatment |
| M2 Proof of Discovery | Canonical manifests, registry source, submission adapter | User signing/ownership, verified deployed workflow, finality reconciliation and indexed chain outcomes |
| M3 Celestial policy | Local/contract field checks, review queue, claim detail | Artifact integrity checks, policy parity tests, chain integration tests, reviewer resolution workflow |
| M4 Public beta | Buildable frontend and deployment configuration | Security, reliability, operations, browser validation |
| M5 Radio | Public Voyager calibration spectrum, narrowband screening | General observation selection, drift/waterfall workflow, off-target comparisons and specialist review |

Not implemented: research notebooks, independent attestations, image anomaly
analysis, collaborative workspaces, AI research agents, and MCP servers. Some
of these are later-stage or optional scope rather than MVP blockers.

## Prioritized findings

### P0: API writes are not bound to an authenticated claimant

`api/main.py` exposes review, challenge, retract, submit, supersede, and appeal
operations without authentication or ownership checks. `ClaimRow` has no user
ownership field. Wallet connection is UI state; the chain adapter signs with a
server-held account. Contract ownership checks therefore do not establish which
HTTP caller was authorized to act for that account.

Before public multi-user use, introduce authenticated identities, claimant
binding, reviewer permissions, and explicit signing authorization. Verify that
one user cannot mutate another user's claim or invoke privileged signing.

### P1: Retracted claims can be submitted

`api/main.py:821` checks only whether a chain claim ID already exists. An isolated
probe inserted a RETRACTED claim into a temporary database and called
`submit_claim` with a mocked chain adapter. The adapter was called, and the
returned record remained RETRACTED while gaining a chain ID.

Define allowed transitions centrally and reject submission of terminal or
otherwise ineligible claims before invoking the adapter. Include superseded
claims in regression coverage.

### P1: Chain decisions and finality are not reconciled

`api/chain.py` returns a protocol result, but `submit_claim` does not persist it.
The isolated probe returned EVIDENCE_SUFFICIENT from the adapter while the local
record retained an empty protocol result. The policy-result endpoint hardcodes
`on_chain: false`.

The Node client waits for ACCEPTED, and the finality endpoint reads the stored
status without refreshing it. Local supersession never invokes the contract's
supersede method. Appeals accept a transaction hash without verifying its
relationship to the claim. These paths can leave chain and local histories
inconsistent.

Persist transaction attempts immediately, make retries idempotent, reconcile
execution outcomes separately from consensus finality, and maintain distinct
local-preview and chain-policy results. Test failures after registration and
before review completion, not only successful submissions.

### P1: Evidence references are not independently retrievable

`api/manifest.py` emits `local://analyses/{id}/series`, but no matching artifact
retrieval endpoint exists. The analysis response stores binned plots rather
than exposing the exact hashed series bytes. Manifests use `local-dev` as a
container digest, omit complete analysis parameters, and record false-positive
tests by name without their measured results. Snapshot hashes alone do not
provide a retrievable snapshot.

Persist exact canonical bytes and raw/processed artifact checksums, expose
versioned retrieval, and include parameters, diagnostics, snapshots, and an
environment identifier sufficient for an independent rerun.

### P1: Policy sufficiency permits invalid measurements and provenance fields

Three isolated evaluations of modified valid fixtures returned
EVIDENCE_SUFFICIENT for:

- Period of -2.5 days.
- Coordinates of RA 999 degrees and declination 999 degrees.
- Catalogue snapshot hash equal to `x`.

This is consistent with checks for numeric presence and nonempty strings rather
than physical ranges or complete hash validation. Artifact contents are not
verified. Treat the current policy as a completeness check until stronger
predicates and bounded integrity verification exist.

Local and contract numeric-string parsing also differ: Python's float parser
accepts exponent notation, while the contract helper accepts only a sign,
digits, and one decimal point. Shared fixtures should exercise both policies.

### P2: Scientific uncertainty and validation are preliminary

`api/science.py:100` uses period grid spacing as period uncertainty. The fitter
searches a fixed 0.7–12 day range and processes one sector. Existing synthetic
recovery coverage does not establish accuracy across correlated noise, gaps,
aliases, weak signals, and eclipsing binaries.

Label grid resolution accurately, validate against an established reference
implementation, and introduce injection/recovery and false-positive evaluation
before making research-grade accuracy claims.

### P2: Runtime and deployment portability need work

The backend uses SQLite with ad hoc additive migrations, unpinned Python
dependency ranges, local storage, and synchronous operations. The chain client
imports dependencies from an absolute global installation path. There is no
checked-in CI workflow or browser test suite. The frontend requires a reachable
API_PROXY target in deployment; a successful frontend build does not establish
that the deployed scientific workflow works.

## Validation performed

- Existing Python suite: 24 passed, one dependency deprecation warning.
- Next.js production build: passed, including TypeScript checks.
- GenLayer contract lint and validation: passed, eight public methods reported.
- Isolated claim/policy probes: reproduced the findings above using a temporary
  database and a mocked chain adapter; no chain writes or production data edits.
- Initial sandboxed pytest collection hung; rerunning outside the sandbox passed.

The existing tests cover useful local behavior and mocked archive responses.
They do not establish live archive health, deployed-contract correctness,
policy parity, multi-user authorization, or browser usability.

## Recommended implementation order

1. Secure claimant identity and signing; enforce claim transitions and ownership.
2. Persist and serve exact evidence bundles with reproducibility metadata.
3. Tighten policy predicates and test local/contract parity.
4. Complete durable submission, recovery, execution-status and finality indexing.
5. Validate scientific recovery and uncertainty against reference cases.
6. Add job processing, portable deployment, observability and browser coverage.

Exit criterion: an authenticated researcher imports a real TESS observation,
creates independently retrievable evidence, explicitly authorizes submission,
and sees the correctly reconciled finalized chain outcome. Another researcher
can retrieve and reproduce the evidence, and unauthorized users cannot mutate
the original claim.
