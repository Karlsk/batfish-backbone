import { randomUUID } from "node:crypto";
import { expect, test } from "@playwright/test";
import { labCredentials } from "./auth-helpers";

test("fixed briefing API keeps immutable facts across revisions on the real worker", async ({
  page,
}) => {
  test.setTimeout(150000);
  const origin = "http://127.0.0.1:15173";
  const login = await page.request.post("/api/v1/auth/login", {
    headers: { Origin: origin },
    data: labCredentials(),
  });
  expect(login.ok()).toBe(true);
  const headers = {
    Origin: origin,
    "X-CSRF-Token": (await login.json()).csrf_token as string,
  };
  const overview = await (
    await page.request.get("/api/v1/leader/overview?limit=200")
  ).json();
  const network = overview.items.find(
    (item: { latest_ready_snapshot: unknown }) => item.latest_ready_snapshot,
  );
  expect(network).toBeTruthy();
  const networkId = network.network_id as string;
  const snapshotId = network.latest_ready_snapshot.id as string;
  const check = await page.request.post("/api/v1/leader/check-runs", {
    headers: { ...headers, "Idempotency-Key": randomUUID() },
    data: {
      template_id: "devices",
      network_id: networkId,
      snapshot_id: snapshotId,
    },
  });
  expect(check.status()).toBe(201);
  const runId = (await check.json()).id as string;
  await expect
    .poll(
      async () =>
        (
          await (
            await page.request.get(`/api/v1/leader/check-runs/${runId}`)
          ).json()
        ).status,
      { timeout: 90000, intervals: [1000, 2000, 3000] },
    )
    .toBe("succeeded");
  const run = await (
    await page.request.get(`/api/v1/leader/check-runs/${runId}`)
  ).json();
  expect(run.result_ids).toHaveLength(1);
  const resultId = run.result_ids[0] as string;
  const result = await (
    await page.request.get(`/api/v1/results/${resultId}`)
  ).json();
  const body = {
    title: `网络周报-${randomUUID().slice(0, 6)}`,
    network_id: networkId,
    snapshot_id: snapshotId,
    result_ids: [resultId],
    notes: "人工记录：待团队确认",
  };
  const key = randomUUID();
  const created = await page.request.post("/api/v1/leader/briefings", {
    headers: { ...headers, "Idempotency-Key": key },
    data: body,
  });
  expect(created.status()).toBe(201);
  const first = await created.json();
  expect(first.sections[0].summary).toEqual(result.summary);
  expect(first.sections[0].evidence_available).toBe(true);
  expect(first.sections[0].engine_version).toBeTruthy();
  const again = await page.request.post("/api/v1/leader/briefings", {
    headers: { ...headers, "Idempotency-Key": key },
    data: body,
  });
  expect((await again.json()).id).toBe(first.id);
  const revised = await page.request.patch(
    `/api/v1/leader/briefings/${first.id}`,
    {
      headers: { ...headers, "Idempotency-Key": randomUUID() },
      data: { expected_version: 1, title: `${body.title}（修订）` },
    },
  );
  expect(revised.status()).toBe(200);
  const second = await revised.json();
  expect(second.id).not.toBe(first.id);
  expect(second.sections).toEqual(first.sections);
  expect(
    (
      await (
        await page.request.get(`/api/v1/leader/briefings/${first.id}`)
      ).json()
    ).title,
  ).toBe(body.title);
  const listing = await (
    await page.request.get(
      `/api/v1/leader/briefings?network_id=${networkId}&limit=100`,
    )
  ).json();
  expect(
    listing.items.some((item: { id: string }) => item.id === second.id),
  ).toBe(true);
});
