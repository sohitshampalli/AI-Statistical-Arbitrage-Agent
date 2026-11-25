// Screenshots of the dashboard with a headless Chromium, served by the real
// backend over the project's stored results (spec section 11).
import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "e2e",
  timeout: 60_000,
  fullyParallel: false,
  workers: 1,
  reporter: [["list"]],
  use: {
    baseURL: "http://127.0.0.1:8000",
    viewport: { width: 1440, height: 900 },
    deviceScaleFactor: 1,
    colorScheme: "dark",
  },
  webServer: {
    command: "uv run statarb dashboard --no-open --port 8000",
    cwd: "..",
    url: "http://127.0.0.1:8000/api/meta",
    reuseExistingServer: false,
    timeout: 120_000,
  },
});
