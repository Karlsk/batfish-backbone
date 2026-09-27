import { randomUUID } from "node:crypto";
import { expect, test } from "@playwright/test";
import { labCredentials } from "./auth-helpers";

test("leader checks persist through the real API and independent worker", async ({
  page,
}) => {
  test.setTimeout(120000);
  const origin = "http://127.0.0.1:15173";
  const credentials = labCredentials();
  const login = await page.request.post("/api/v1/auth/login", {
    headers: { Origin: origin },
    data: credentials,
  });
  expect(login.ok()).toBe(true);
  const csrf = (await login.json()).csrf_token as string;
  const headers = { Origin: origin, "X-CSRF-Token": csrf };
  const overview = await page.request.get("/api/v1/leader/overview?limit=200");
  expect(overview.ok()).toBe(true);
  const network = (await overview.json()).items.find(
    (item: { latest_ready_snapshot: unknown }) => item.latest_ready_snapshot,
  );
  expect(network).toBeTruthy();
  const source = {
    network_id: network.network_id,
    snapshot_id: network.latest_ready_snapshot.id,
  };
  const key = randomUUID();
  const quality = await page.request.post("/api/v1/leader/check-runs", {
    headers: { ...headers, "Idempotency-Key": key },
    data: { ...source, template_id: "configuration-quality" },
  });
  expect(quality.status()).toBe(201);
  expect((await quality.json()).status).toBe("succeeded");
  const same = await page.request.post("/api/v1/leader/check-runs", {
    headers: { ...headers, "Idempotency-Key": key },
    data: { ...source, template_id: "configuration-quality" },
  });
  expect((await same.json()).id).toBe((await quality.json()).id);
  const changed = await page.request.post("/api/v1/leader/check-runs", {
    headers: { ...headers, "Idempotency-Key": key },
    data: { ...source, template_id: "devices" },
  });
  expect(changed.status()).toBe(409);
  const submitted = await page.request.post("/api/v1/leader/check-runs", {
    headers: { ...headers, "Idempotency-Key": randomUUID() },
    data: { ...source, template_id: "devices" },
  });
  expect(submitted.status()).toBe(201);
  const run = await submitted.json();
  expect(run.job_ids).toHaveLength(1);
  await expect
    .poll(
      async () => {
        const response = await page.request.get(
          `/api/v1/leader/check-runs/${run.id}`,
        );
        expect(response.ok()).toBe(true);
        return (await response.json()).status;
      },
      { timeout: 90000, intervals: [1000, 2000, 3000] },
    )
    .toBe("succeeded");
  const final = await (
    await page.request.get(`/api/v1/leader/check-runs/${run.id}`)
  ).json();
  expect(final.result_ids).toHaveLength(1);
  expect(final.snapshot_id).toBe(source.snapshot_id);
  const listed = await (
    await page.request.get(
      `/api/v1/leader/check-runs?network_id=${source.network_id}`,
    )
  ).json();
  expect(listed.items.some((item: { id: string }) => item.id === run.id)).toBe(
    true,
  );
});
