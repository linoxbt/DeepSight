import { test, expect } from "@playwright/test";

for (const width of [1440, 390]) {
  test(`editorial layout and navigation at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 1000 });
    await page.route("**/v1/auth/session", route => route.fulfill({ status: 401, json: { detail: "Sign in" } }));
    await page.goto("/");
    await expect(page.getByRole("heading", { name: "Wonder, with evidence." })).toBeVisible();
    await expect(page.getByRole("link", { name: "Enter the workspace" })).toHaveAttribute("href", "/explore");
    await page.evaluate(() => document.fonts.ready);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.screenshot({ path: `/tmp/deepsight-home-${width}.png`, fullPage: true });
    await page.getByRole("button", { name: "Open menu" }).click();
    await expect(page.getByRole("navigation", { name: "Pages" })).toBeVisible();
    await page.getByRole("navigation", { name: "Pages" }).getByRole("link", { name: "Explorer", exact: false }).click();
    await expect(page.getByRole("heading", { name: "Import one TESS sector" })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.screenshot({ path: `/tmp/deepsight-explorer-${width}.png`, fullPage: true });
  });
}

test("registry filters records, searches targets, and opens evidence", async ({ page }) => {
  await page.route("**/v1/auth/session", route => route.fulfill({ status: 401, json: {} }));
  await page.route("**/v1/claims", route => route.fulfill({ json: { claims: [
    { id: "clm_one", target_id: "TIC-123", status: "SUBMITTED", scientific_status: "unconfirmed_candidate", protocol_result: "NEEDS_HUMAN_REVIEW" },
    { id: "clm_two", target_id: "TIC-456", status: "FINALIZED", scientific_status: "known", protocol_result: "EVIDENCE_SUFFICIENT" },
  ] } }));
  await page.goto("/claims");
  await expect(page.locator(".claim-card")).toHaveCount(2);
  await page.screenshot({ path: "/tmp/deepsight-claims.png", fullPage: true });
  await page.getByRole("button", { name: "Needs review", exact: true }).click();
  await expect(page.locator(".claim-card")).toHaveCount(1);
  await expect(page.getByRole("link", { name: "Inspect the evidence" })).toHaveAttribute("href", "/claims/clm_one");
  await page.getByRole("button", { name: "All claims" }).click();
  await page.getByRole("textbox", { name: "Search claims" }).fill("456");
  await expect(page.locator(".claim-card")).toHaveCount(1);
  await expect(page.getByRole("link", { name: "TIC-456" })).toBeVisible();
  await page.getByRole("textbox", { name: "Search claims" }).fill("missing");
  await expect(page.getByRole("heading", { name: "No matching records." })).toBeVisible();
});

test("paper is default and theme preference persists", async ({ page }) => {
  await page.route("**/v1/auth/session", route => route.fulfill({ status: 401, json: {} }));
  await page.goto("/");
  await expect(page.getByRole("button", { name: "Observation mode" })).toBeVisible();
  await page.getByRole("button", { name: "Observation mode" }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "observation");
  await page.reload();
  await expect(page.getByRole("button", { name: "Paper mode" })).toBeVisible();
  await page.getByRole("button", { name: "Paper mode" }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "paper");
});

test("registry distinguishes failed requests from empty records", async ({ page }) => {
  await page.route("**/v1/auth/session", route => route.fulfill({ status: 401, json: {} }));
  await page.route("**/v1/claims", route => route.fulfill({ status: 503, json: { detail: "Unavailable" } }));
  await page.goto("/claims");
  await expect(page.getByRole("alert").filter({ hasText: "Claims could not be loaded" })).toHaveText("Claims could not be loaded. Please try again later.");
  await expect(page.getByText("An open page for your evidence.")).toHaveCount(0);
});
