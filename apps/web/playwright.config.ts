import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "./tests",
  webServer: { command: "npm run start -- --hostname 127.0.0.1 --port 3300", url: "http://127.0.0.1:3300", reuseExistingServer: !process.env.CI, timeout: 120000 },
  use: { baseURL: process.env.E2E_BASE_URL || "http://127.0.0.1:3300", headless: true,
    launchOptions: { executablePath: process.env.CHROME_PATH || (process.env.CI ? undefined : "/usr/bin/google-chrome"), args: ["--no-sandbox", "--disable-dev-shm-usage"] } },
});
