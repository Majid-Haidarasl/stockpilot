import { defineConfig, devices } from "@playwright/test";

const baseURL = process.env.BASE_URL ?? "http://frontend-dev:5173";

export default defineConfig({
  testDir: "./specs",
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: 0,
  workers: 1,
  reporter: [["list"], ["html", { open: "never", outputFolder: "playwright-report" }]],
  timeout: 120_000,
  expect: { timeout: 20_000 },
  outputDir: "test-results",
  use: {
    baseURL,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "off",
    locale: "fa-IR",
    ...devices["Desktop Chrome"],
  },
});
