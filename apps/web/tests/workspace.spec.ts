import { test, expect } from "@playwright/test";

test("workspace navigation, sign-in boundary, and queued analysis", async ({ page }) => {
  let authenticated = false;
  await page.route("**/v1/auth/session", async route => route.fulfill({ status: authenticated ? 200 : 401,
    json: authenticated ? { address: "0x1111111111111111111111111111111111111111" } : { detail: "Sign in with your wallet to continue" } }));
  await page.route("**/v1/targets", route => route.fulfill({ json: { targets: [{ id: "DS-SYN-001", name: "Calibration", summary: "Synthetic calibration", ra_deg: 10, dec_deg: -20, synthetic: true, observation_id: "synthetic" }] } }));
  await page.route("**/v1/jobs", route => route.fulfill({ status: authenticated ? 202 : 401, json: authenticated ? { id: "job_browser", status: "queued" } : { detail: "Sign in with your wallet to continue" } }));
  await page.route("**/v1/jobs/job_browser", route => route.fulfill({ json: { status: "succeeded", result: {
    id: "an_browser", target: { id: "DS-SYN-001", name: "Calibration", synthetic: true },
    metrics: { period_days: 2.5, period_resolution_days: 0.016, period_uncertainty_days: null, duration_days: 0.1, depth: 0.008, snr_proxy: 12, odd_even_delta: 0.1, secondary_depth: 0, n_samples: 100, n_in_transit: 10 },
    quality_flags: [], cross_match: { result: "no_exact_match", note: "No exact match" }, limitations: ["Synthetic calibration"],
    series_plot: { time_days: [0, 1, 2], flux: [1, 0.99, 1] }, folded: { phase: [0, 0.5, 1], flux: [1, 0.99, 1] }, periodogram: { period_days: [1, 2.5, 4], power: [0, 1, 0] },
  } } }));
  await page.goto("/lab");
  await expect(page.getByRole("heading", { name: "Analyze a star's light" })).toBeVisible();
  await page.getByRole("button", { name: "Analyze light curve" }).click();
  await expect(page.getByText("Sign in with your wallet to continue", { exact: true })).toBeVisible();
  authenticated = true;
  await page.getByRole("button", { name: "Analyze light curve" }).click();
  await expect(page.getByText("Period grid resolution", { exact: true })).toBeVisible();
  await expect(page.getByText("0.016 d (not uncertainty)", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Open menu" }).click();
  await expect(page.getByRole("navigation", { name: "Pages" })).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("button", { name: "Open menu" })).toBeVisible();
});

test("claim page separates local policy and chain outcome and offers exact downloads", async ({ page }) => {
  await page.route("**/v1/auth/session", route => route.fulfill({ status: 401, json: { detail: "Sign in" } }));
  await page.route("**/v1/claims/clm_browser", route => route.fulfill({ json: { id: "clm_browser", owner: "0x1111111111111111111111111111111111111111", status: "FINALIZED", protocol_result: "EVIDENCE_SUFFICIENT", rationale: "Local preview", scientific_status: "unconfirmed_candidate", scientific_confirmation: false, manifest_hash: "a".repeat(64), chain_status: "ACCEPTED", chain_note: "Provisional", chain_claim_id: "pod-1", chain_tx: "", chain_protocol_result: "", chain_execution: "SUCCESS", target_id: "TIC-1", policy_version: "celestial-v1", manifest: { archive: { name: "MAST" }, limitations: ["Not confirmed"], metrics: [] } } }));
  await page.route("**/v1/claims/clm_browser/timeline", route => route.fulfill({ json: { events: [] } }));
  await page.route("**/v1/claims/clm_browser/finality", route => route.fulfill({ json: { reason: "Awaiting finality" } }));
  await page.route("**/v1/claims/clm_browser/operations", route => route.fulfill({ json: { operations: [{ id: "op_one", action: "submit", stage: "review", status: "submitted", tx_hash: `0x${"a".repeat(64)}`, error: "" }] } }));
  await page.route("**/v1/chain/config", route => route.fulfill({ json: { configured: true, relay_enabled: true, contract_address: "0x6B6dC06981Aa6903434dBab601D8b61c5fD57ff8" } }));
  await page.route("**/v1/research/attestations?claim_id=clm_browser", route => route.fulfill({ json: { attestations: [] } }));
  await page.goto("/claims/clm_browser");
  await expect(page.getByRole("heading", { name: "Local policy preview" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Chain evidence decision" })).toBeVisible();
  await expect(page.getByText("No chain decision", { exact: true })).toBeVisible();
  await expect(page.getByRole("link", { name: "Download reproducible evidence bundle" })).toHaveAttribute("href", "/v1/claims/clm_browser/bundle");
  await expect(page.getByRole("link", { name: "View Proof of Discovery on GenLayer StudioNet" })).toHaveAttribute("href", "https://explorer-studio.genlayer.com/address/0x6B6dC06981Aa6903434dBab601D8b61c5fD57ff8");
  await expect(page.getByRole("link", { name: `0x${"a".repeat(64)} ↗` })).toHaveAttribute("href", `https://explorer-studio.genlayer.com/tx/0x${"a".repeat(64)}`);
  await expect(page.getByRole("button", { name: "Sign retraction" })).toHaveCount(0);
});

test("wallet-owned claim offers a wallet transaction instead of a relay signature", async ({ page }) => {
  await page.route("**/v1/auth/session", route => route.fulfill({ json: { address: "0x1111111111111111111111111111111111111111" } }));
  await page.route("**/v1/claims/clm_wallet", route => route.fulfill({ json: {
    id: "clm_wallet", owner: "0x1111111111111111111111111111111111111111", submission_mode: "wallet",
    status: "EVIDENCE_READY", public: false, manifest_hash: "a".repeat(64), chain_claim_id: "",
    chain_status: "not_submitted", chain_tx: "", chain_protocol_result: "", chain_execution: "",
    scientific_status: "unconfirmed_candidate", scientific_confirmation: false, target_id: "TIC-1",
    policy_version: "celestial-v4", manifest: { archive: { name: "MAST" }, limitations: [], metrics: [] },
  } }));
  await page.route("**/v1/claims/clm_wallet/timeline", route => route.fulfill({ json: { events: [] } }));
  await page.route("**/v1/claims/clm_wallet/finality", route => route.fulfill({ json: { reason: "Not submitted" } }));
  await page.route("**/v1/claims/clm_wallet/operations", route => route.fulfill({ json: { operations: [] } }));
  await page.route("**/v1/chain/config", route => route.fulfill({ json: { configured: true, relay_enabled: true, contract_address: "0x5cfaE959BbFF6Be9e4A1F477abDCc61fAfD5eeb1" } }));
  await page.route("**/v1/research/attestations?claim_id=clm_wallet", route => route.fulfill({ json: { attestations: [] } }));
  await page.goto("/claims/clm_wallet");
  await expect(page.getByRole("button", { name: "Send registration from my wallet" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Sign relay submission" })).toHaveCount(0);
});

test("evidence builder defaults to wallet ownership and offers the relay fallback", async ({ page }) => {
  await page.route("**/v1/auth/session", route => route.fulfill({ status: 401, json: { detail: "Sign in" } }));
  await page.route("**/v1/evidence/preflight", route => route.fulfill({ json: { ready: true, items: [] } }));
  await page.route("**/v1/claims", route => route.fulfill({ json: { id: "clm_relay_choice" } }));
  await page.goto("/evidence?analysis=an_choice");
  await expect(page.getByRole("combobox", { name: "GenLayer submission" })).toHaveValue("wallet");
  await page.getByRole("combobox", { name: "GenLayer submission" }).selectOption("relay");
  await page.getByRole("checkbox").check();
  const submitted = page.waitForRequest(request => request.url().endsWith("/v1/claims") && request.method() === "POST");
  await page.getByRole("button", { name: "Create evidence claim" }).click();
  expect((await submitted).postDataJSON().submission_mode).toBe("relay");
});

test("saved research runs link back to their completed analysis", async ({ page }) => {
  await page.route("**/v1/auth/session", route => route.fulfill({ status: 401, json: { detail: "Sign in" } }));
  await page.route("**/v1/jobs", route => route.fulfill({ json: { jobs: [{ id: "job_saved", kind: "analysis", status: "succeeded", error: "", created: 1700000000, href: "/lab?analysis=an_saved" }] } }));
  await page.goto("/jobs");
  await expect(page.getByRole("heading", { name: "Research runs" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Open result" })).toHaveAttribute("href", "/lab?analysis=an_saved");
});
