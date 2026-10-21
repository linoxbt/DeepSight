import { test, expect } from "@playwright/test";

test("opening a connected wallet leaves it connected and does not sign out", async ({ page }) => {
  let signOutRequests = 0;
  await page.route("**/v1/auth/session", route => {
    if (route.request().method() === "DELETE") signOutRequests++;
    return route.fulfill({ status: 401, json: { detail: "Sign in required" } });
  });
  await page.addInitScript(() => {
    const address = "0x1111111111111111111111111111111111111111";
    const listeners: Record<string, Function[]> = {};
    const provider = {
      isMetaMask: true,
      isConnected: () => true,
      on(name: string, callback: Function) { (listeners[name] ||= []).push(callback); return provider; },
      removeListener(name: string, callback: Function) { listeners[name] = (listeners[name] || []).filter(item => item !== callback); return provider; },
      async request({ method }: { method: string }) {
        if (method === "eth_accounts" || method === "eth_requestAccounts") return [address];
        if (method === "eth_chainId") return "0xf22f";
        if (method === "net_version") return "61999";
        return null;
      },
    };
    Object.defineProperty(window, "ethereum", { value: provider, configurable: true });
    const info = { uuid: "deepsight-test-wallet", name: "Test Wallet", icon: 'data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg"/>', rdns: "org.deepsight.test" };
    const announce = () => window.dispatchEvent(new CustomEvent("eip6963:announceProvider", { detail: { info, provider } }));
    window.addEventListener("eip6963:requestProvider", announce);
    setTimeout(announce, 0);
  });
  await page.goto("/");
  const wallet = page.getByRole("button", { name: /Wallet 0x1111111111111111111111111111111111111111\. Open wallet account/i });
  await expect(wallet).toBeVisible({ timeout: 15000 });
  await expect(page.getByRole("button", { name: "Sign in to DeepSight" })).toBeVisible();
  await wallet.click();
  await expect(page.locator("w3m-modal")).toBeVisible();
  await expect(wallet).toBeVisible();
  expect(signOutRequests).toBe(0);
  await page.keyboard.press("Escape");
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});
