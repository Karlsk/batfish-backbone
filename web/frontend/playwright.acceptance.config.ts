import { defineConfig } from "@playwright/test";
import { readFileSync } from "node:fs";
import standard from "./playwright.config";
const folder = process.env.BFW_DEPLOYMENT_STATE;
const deployment = folder
  ? JSON.parse(readFileSync(`${folder}/deployment.json`, "utf8"))
  : null;
export default defineConfig({
  ...standard,
  testDir: "./e2e",
  testMatch: "mvp.spec.ts",
  webServer: deployment ? undefined : standard.webServer,
  use: deployment
    ? { ...standard.use, baseURL: deployment.origin, ignoreHTTPSErrors: true }
    : standard.use,
  reporter: [
    ["list"],
    ["json", { outputFile: "test-results/acceptance.json" }],
  ],
});
