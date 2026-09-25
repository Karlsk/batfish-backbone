import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "./tests",
  testMatch: "*.spec.ts",
  fullyParallel: false,
  workers: 1,
  reporter: [["list"], ["json", { outputFile: "test-results/results.json" }]],
  use: { baseURL: "http://127.0.0.1:15173", trace: "retain-on-failure" },
  webServer: {
    command:
      "./node_modules/.bin/vite --host 127.0.0.1 --port 15173 --strictPort",
    url: "http://127.0.0.1:15173",
    reuseExistingServer: false,
  },
  projects: [{ name: "chromium", use: { browserName: "chromium" } }],
});
