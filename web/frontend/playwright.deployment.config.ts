import { defineConfig } from "@playwright/test";
import { readFileSync } from "node:fs";
const folder = process.env.BFW_DEPLOYMENT_STATE;
if (!folder)
  throw new Error("BFW_DEPLOYMENT_STATE must identify the owned deployment");
const state = JSON.parse(readFileSync(`${folder}/deployment.json`, "utf8"));
export default defineConfig({
  testDir: "./e2e",
  testMatch: "deployment.spec.ts",
  workers: 1,
  reporter: [
    ["list"],
    ["json", { outputFile: "test-results/deployment.json" }],
  ],
  use: {
    baseURL: state.origin,
    ignoreHTTPSErrors: true, // Local self-signed certificate; HTTP verifier checks its CA and host.
    browserName: "chromium",
    trace: "retain-on-failure",
    viewport: { width: 1280, height: 1000 },
  },
});
