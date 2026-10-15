import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests",
  timeout: 120000,
  workers: 1,
  reporter: [["list"]],
  use: { baseURL: "http://127.0.0.1:4173", browserName: "chromium", deviceScaleFactor: 1 },
  webServer: {
    command: "node scripts/serve.mjs",
    url: "http://127.0.0.1:4173",
    reuseExistingServer: false,
    timeout: 30000,
  },
});
