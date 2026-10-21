# GenLayer Portal project submission — DeepSight

Use the text below for a **Projects → Project** submission. It describes the deployed build as of 19 October 2026. Do not describe a `NEEDS_HUMAN_REVIEW` result as a confirmed planet or independently reproduced measurement.

## 01 · Identity

- **Project name:** DeepSight
- **Logo:** Upload [`submission-logo.png`](submission-logo.png), a 512 × 512 PNG under 2 MB, exported from the app icon.
- **Primary tag:** Choose the Portal's closest available **Science / DeSci** category. If neither exists, choose the closest **AI / Intelligent Contracts** category. Use the exact displayed label; available tags were not supplied.
- **Tag 1:** Astronomy / Space, if available.
- **Tag 2:** Research / Data Verification, if available.

## 02 · One-liner — paste into the 180-character field

> DeepSight turns public sky data into inspectable research claims whose evidence and review history are anchored by a GenLayer Intelligent Contract.

## 03 · Description — paste into the 1,000-character field

> DeepSight is an astronomy research workspace for investigating possible transits without treating a plotted dip as a discovered planet. Import a real TESS light curve from NASA MAST, run a box-least-squares search, and inspect measurements, quality flags, source files, and an evidence manifest. Connect a wallet to register the claim on GenLayer StudioNet. Its Intelligent Contract binds claimant, target, manifest hash, and evidence pointers; a separate review checks manifest integrity and, for eligible known TESS objects, catalogue consistency. It does not reproduce FITS measurements. Other wallets can record unadjudicated objections; the owner can replace or retract a claim. The app links transactions and distinguishes local analysis, contract checks, and scientific confirmation. Raw data stays in content-addressed storage, with hashes committed in the manifest. Live transactions have finalized for registration, review, challenge, replacement, and retraction.

## 04 · Demo video

Optional. Leave blank until a direct YouTube video or X post showing the deployed flow is available. Do not paste a channel, profile, or unrelated clip.

## 05 · How-to — enter these steps in order

| Heading | Instruction |
| --- | --- |
| 1. Connect and sign in | Open the website, select **Connect wallet**, connect a StudioNet-capable wallet, then select **Sign in to DeepSight** and approve the message signature. |
| 2. Load real sky data | Open **Explore the sky** and select **Load TESS example**. The app imports the light curve for TIC 259377017 from NASA MAST. Wait for the import job to finish, then select **Analyze this light curve**. |
| 3. Analyze the observation | In **Discovery Lab**, select the imported TESS target and **Analyze light curve**. Inspect the light curve, phase-folded plot, period search, quality flags, and limitations. |
| 4. Build the evidence | Select **Build evidence**, read the checklist and uncertainty statement, acknowledge it, keep **My wallet sends transactions** selected, and select **Create evidence claim**. |
| 5. Register on GenLayer | On the claim page, select **Send registration from my wallet**. Confirm that publishing the manifest and evidence is acceptable, approve the StudioNet transaction in the wallet, and wait for finalized registration. The wallet needs StudioNet test GEN for fees. |
| 6. Request contract review | Select **Send on-chain evidence review**, approve the second wallet transaction, and wait for finality. Read **Chain evidence decision** and its rationale; a result can require human review if an archive comparison is unavailable. |
| 7. Inspect the proof | Open the contract and transaction links on the claim page. Download the canonical manifest and evidence bundle, compare the displayed manifest hash, and inspect the claim timeline. |

If live import or wallet confirmation is unavailable during review, use the already-finalized example below to inspect the real contract path. The example was operated with disposable wallets through an EIP-1193 provider harness, not by a human clicking through Reown.

## 06 · Review verification — paste into the 500-character field

> The claim page should show a manifest hash, StudioNet contract link, finalized registration and review transactions, and a contract rationale. Review may say NEEDS_HUMAN_REVIEW when NASA archive comparison is unavailable; that is the correct bounded result, not a confirmed planet. Inspect live claim clm_092f3f5afa85 and contract 0x5cfaE959BbFF6Be9e4A1F477abDCc61fAfD5eeb1. Its registration, review, independent challenge, replacement, and retraction are finalized on StudioNet.

**Contract link 1:** https://explorer-studio.genlayer.com/address/0x5cfaE959BbFF6Be9e4A1F477abDCc61fAfD5eeb1

## 07 · Project links

- **Website:** https://deepsight-evidence.netlify.app
- **GitHub:** https://github.com/linoxbt/DeepSight
- **Live claim:** https://deepsight-evidence.netlify.app/claims/clm_092f3f5afa85
- **Live known-TIC catalogue-matching claim:** https://deepsight-evidence.netlify.app/claims/clm_868cfd805618
- **Contract source:** https://github.com/linoxbt/DeepSight/blob/feat/evidence-workspace/contracts/proof_of_discovery.py
- **Deployment record:** https://github.com/linoxbt/DeepSight/blob/feat/evidence-workspace/deployments/studionet-v4.json

## Evidence & Supporting Information — add individually

The Portal requires at least one item. Add the GitHub repository first, then these direct proof links where the Portal permits additional URL evidence:

1. **GitHub Repository:** https://github.com/linoxbt/DeepSight
2. **Finalized wallet-origin registration:** https://explorer-studio.genlayer.com/tx/0xe7faaea95f4c16a0745e75ff1b5e5e607f6df9f117e74fa82775a310fafc41e2
3. **Finalized contract evidence review:** https://explorer-studio.genlayer.com/tx/0x3274ea3522b3ca8275381381972093ed6c82d6957369deb0c883b4619349f9f6
4. **Second-wallet challenge:** https://explorer-studio.genlayer.com/tx/0x277d20deb80ff33ea1deb9f6bf69e54c67de040e8770b59a1435f51880c7a8a4
5. **Owner replacement:** https://explorer-studio.genlayer.com/tx/0x3f3c210b7ee7a2f4a753d3da3fee138fca68e2b689286dfbc1bd9d7055b2aeee
6. **Replacement review:** https://explorer-studio.genlayer.com/tx/0x7803738809a14c406c41d4a7272d8c39006fcb5f27fb8185d010920890596c47
7. **Owner retraction:** https://explorer-studio.genlayer.com/tx/0x6e19c7386f019c088a00d9fa89b6ddf75c2d58180ee417d5c80d37ab002c65c7
8. **Technical verification and known limits:** https://github.com/linoxbt/DeepSight/blob/feat/evidence-workspace/AUDIT_STATUS.md
9. **Finalized v4 known-TIC catalogue match:** https://explorer-studio.genlayer.com/tx/0xb9a90a77e9904e886b826cd45bdabbacf810adc572b3c5ccd14caf10612adf17

### What makes GenLayer central

The app's scientific work produces an evidence package, but the public claim lifecycle depends on its Intelligent Contract. The connected wallet sends registration and review transactions; the contract holds the claimant and evidence commitment and records the review outcome. Challenges, replacements, and retractions are also contract mutations. The backend verifies the sender and exact contract call before attaching a wallet transaction, and its worker waits for finality before updating the public record. The local analysis alone does not create an on-chain claim.

### Accuracy note for the steward

This is a research-claim and evidence-review system, not an exoplanet confirmation service. The current contract can compare submitted measurements with a live NASA catalogue response when available; it does not recompute BLS from the pinned FITS file. A matching catalogue row can be copied into a fabricated manifest, so that match proves consistency only. A challenge is an unadjudicated objection and has no on-chain dismissal in v4. Radio measurements are not independently verified on-chain. Some social-wallet and operational acceptance checks remain open. These limits are shown in the app and tracked in [`AUDIT_STATUS.md`](AUDIT_STATUS.md) and [`STEWARD_REVIEW.md`](STEWARD_REVIEW.md).
