import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./tests",
  ...(process.env.SOLOLMNP_VOLUME ? {} : { testIgnore: "**/volume.spec.ts" }),
  timeout: 240_000,
  expect: { timeout: 20_000 },
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL: "http://127.0.0.1:5173",
    trace: "retain-on-failure",
    viewport: { width: 1280, height: 800 },
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: {
    command: `${process.env.PYTHON ?? "python3"} serve.py`,
    url: "http://127.0.0.1:5173",
    timeout: 120_000,
    reuseExistingServer: false,
    stdout: "pipe",
    stderr: "pipe",
  },
});
