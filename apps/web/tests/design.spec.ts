import { test, expect } from "@playwright/test";

test.beforeEach(async ({ page }) => {
  await page.route("**/v1/images", route => route.fulfill({ status: 401, json: { detail: "Sign in" } }));
});

for (const width of [1440, 390]) {
  test(`editorial layout and navigation at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 1000 });
    await page.route("**/v1/auth/session", route => route.fulfill({ status: 401, json: { detail: "Sign in" } }));
    await page.goto("/");
    await expect(page.getByRole("heading", { name: "Wonder, with evidence." })).toBeVisible();
    await expect(page.getByRole("link", { name: "Enter the workspace" })).toHaveAttribute("href", "/explore");
    await expect(page.getByRole("button", { name: "Open menu" })).toHaveCount(0);
    await expect(page.getByRole("img", { name: "NASA Blue Marble view of Earth" })).toBeVisible();
    await expect(page.getByRole("img", { name: "Hubble view of the Andromeda galaxy" })).toBeVisible();
    await page.evaluate(() => document.fonts.ready);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.screenshot({ path: `/tmp/deepsight-home-${width}.png`, fullPage: true });
    await page.getByRole("link", { name: "Enter the workspace" }).click();
    await expect(page.getByRole("heading", { name: "Explore the sky" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Load TESS example" })).toBeVisible();
    await page.getByRole("button", { name: "Open menu" }).click();
    await expect(page.getByRole("navigation", { name: "Pages" })).toBeVisible();
    await expect(page.getByRole("navigation", { name: "Pages" }).getByRole("link", { name: "Analyze a light curve" })).toBeVisible();
    await page.getByRole("button", { name: "Close", exact: true }).click();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.screenshot({ path: `/tmp/deepsight-explorer-${width}.png`, fullPage: true });
  });
}

test("registry filters records, searches targets, and opens evidence", async ({ page }) => {
  await page.route("**/v1/auth/session", route => route.fulfill({ status: 401, json: {} }));
  await page.route("**/v1/claims", route => route.fulfill({ json: { claims: [
    { id: "clm_one", target_id: "TIC-123", status: "NEEDS_REVIEW", scientific_status: "unconfirmed_candidate", protocol_result: "NEEDS_HUMAN_REVIEW", chain_protocol_result: "", chain_status: "not_submitted", chain_execution: "" },
    { id: "clm_two", target_id: "TIC-456", status: "FINALIZED", scientific_status: "known", protocol_result: "EVIDENCE_SUFFICIENT", chain_protocol_result: "EVIDENCE_SUFFICIENT", chain_status: "FINALIZED", chain_execution: "SUCCESS" },
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

test("image notebook accepts a photo and exports notes locally", async ({ page }) => {
  await page.route("**/v1/auth/session", route => route.fulfill({ status: 401, json: {} }));
  await page.goto("/explore");
  await page.getByRole("textbox", { name: "TIC ID" }).isVisible();
  await page.getByLabel("Choose a sky image").setInputFiles({
    name: "moon.png", mimeType: "image/png",
    buffer: Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVQIHWP4z8DwHwAFgAI/ScL/nwAAAABJRU5ErkJggg==", "base64"),
  });
  await expect(page.getByText("1 × 1 pixels")).toBeVisible();
  await page.getByRole("button", { name: "Mark a point on the image" }).click();
  await expect(page.getByText("1 point marked")).toBeVisible();
  await page.getByLabel("What caught your eye?").fill("A bright spot");
  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download notes" }).click();
  expect((await download).suggestedFilename()).toBe("deepsight-image-notes.json");
});

test("image notebook saves and reopens a private image with its notes", async ({ page }) => {
  const pixels = Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVQIHWP4z8DwHwAFgAI/ScL/nwAAAABJRU5ErkJggg==", "base64");
  const saved = { id: "img_test", filename: "moon.png", image_url: "/v1/images/img_test/file", note: "", marks: [] as { x: number; y: number }[] };
  let uploads = 0;
  await page.route("**/v1/auth/session", route => route.fulfill({ status: 401, json: {} }));
  await page.route("**/v1/images", route => {
    if (route.request().method() === "POST") {
      uploads++;
      return route.fulfill({ status: 201, json: saved });
    }
    return route.fulfill({ json: { images: [] } });
  });
  await page.route("**/v1/images/img_test", async route => {
    const body = route.request().postDataJSON();
    saved.note = body.note;
    saved.marks = body.marks;
    await route.fulfill({ json: saved });
  });
  await page.route("**/v1/images/img_test/file", route => route.fulfill({ body: pixels, contentType: "image/png" }));
  await page.goto("/explore");
  await page.getByLabel("Choose a sky image").setInputFiles({ name: "moon.png", mimeType: "image/png", buffer: pixels });
  await expect(page.getByText("1 × 1 pixels")).toBeVisible();
  await page.getByLabel("What caught your eye?").fill("A bright spot");
  await page.getByRole("button", { name: "Save image to workspace" }).click();
  await expect(page.getByRole("button", { name: "moon.png · A bright spot" })).toBeVisible();
  expect(uploads).toBe(1);
  await page.getByLabel("What caught your eye?").fill("Changed locally");
  await page.getByRole("button", { name: "moon.png · A bright spot" }).click();
  await expect(page.getByLabel("What caught your eye?")).toHaveValue("A bright spot");
  await page.getByRole("button", { name: "Update saved image" }).click();
  expect(uploads).toBe(1);
});

test("registry distinguishes failed requests from empty records", async ({ page }) => {
  await page.route("**/v1/auth/session", route => route.fulfill({ status: 401, json: {} }));
  await page.route("**/v1/claims", route => route.fulfill({ status: 503, json: { detail: "Unavailable" } }));
  await page.goto("/claims");
  await expect(page.getByRole("alert").filter({ hasText: "Claims could not be loaded" })).toHaveText("Claims could not be loaded. Please try again later.");
  await expect(page.getByText("An open page for your evidence.")).toHaveCount(0);
});
