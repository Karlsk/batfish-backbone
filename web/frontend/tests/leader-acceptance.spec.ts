import { randomUUID } from "node:crypto";
import { expect, test } from "@playwright/test";
import { labCredentials } from "./auth-helpers";

test("Cisco concern and fixed report remain scoped after mapping changes and an r1/r2 check", async ({
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
  const networkPage = await (
    await page.request.get("/api/v1/networks?limit=200")
  ).json();
  const cisco = networkPage.items.find(
    (item: { display_name: string }) =>
      item.display_name === "LDR12 cisco_four",
  );
  const small = networkPage.items.find(
    (item: { display_name: string }) =>
      item.display_name === "LDR12 small_network",
  );
  expect(cisco).toBeTruthy();
  expect(small).toBeTruthy();

  async function readySnapshot(networkId: string) {
    const response = await page.request.get(
      `/api/v1/networks/${networkId}/snapshots?limit=100`,
    );
    expect(response.ok()).toBe(true);
    const data = await response.json();
    const snapshot = data.items.find(
      (item: { status: string }) =>
        item.status === "ready" || item.status === "ready_with_warnings",
    );
    expect(snapshot).toBeTruthy();
    return snapshot.id as string;
  }
  async function completedDevices(networkId: string, snapshotId: string) {
    const response = await page.request.post("/api/v1/leader/check-runs", {
      headers: { ...headers, "Idempotency-Key": randomUUID() },
      data: {
        network_id: networkId,
        snapshot_id: snapshotId,
        template_id: "devices",
      },
    });
    expect(response.status()).toBe(201);
    const id = (await response.json()).id as string;
    await expect
      .poll(
        async () =>
          (
            await (
              await page.request.get(`/api/v1/leader/check-runs/${id}`)
            ).json()
          ).status,
        { timeout: 90000, intervals: [1000, 2000, 3000] },
      )
      .toBe("succeeded");
    return (
      await (await page.request.get(`/api/v1/leader/check-runs/${id}`)).json()
    ).result_ids[0] as string;
  }

  const ciscoSnapshot = await readySnapshot(cisco.id);
  const name = `关键流量-${randomUUID().slice(0, 6)}`;
  const concernResponse = await page.request.post("/api/v1/business-concerns", {
    headers,
    data: {
      network_id: cisco.id,
      name,
      priority: "high",
      flows: [
        { start_location: "c1", destination_ip: "10.64.0.4", protocol: "icmp" },
      ],
    },
  });
  expect(concernResponse.status()).toBe(201);
  const concern = await concernResponse.json();
  const resultId = await completedDevices(cisco.id, ciscoSnapshot);
  const reportResponse = await page.request.post("/api/v1/leader/briefings", {
    headers: { ...headers, "Idempotency-Key": randomUUID() },
    data: {
      title: `固定范围-${randomUUID().slice(0, 6)}`,
      network_id: cisco.id,
      snapshot_id: ciscoSnapshot,
      result_ids: [resultId],
      concern_id: concern.id,
      concern_version: concern.version,
    },
  });
  expect(reportResponse.status()).toBe(201);
  const frozen = await reportResponse.json();
  expect(frozen.frozen_concern.name).toBe(name);
  expect(frozen.concern_version).toBe(1);

  const update = await page.request.patch(
    `/api/v1/business-concerns/${concern.id}`,
    {
      headers,
      data: { expected_version: 1, name: `${name}-更新` },
    },
  );
  expect(update.status()).toBe(200);
  expect((await update.json()).version).toBe(2);
  const smallResult = await completedDevices(
    small.id,
    await readySnapshot(small.id),
  );
  expect(smallResult).not.toBe(resultId);
  const stillFrozen = await (
    await page.request.get(`/api/v1/leader/briefings/${frozen.id}`)
  ).json();
  expect(stillFrozen.frozen_concern.name).toBe(name);
  expect(stillFrozen.concern_version).toBe(1);
  expect(stillFrozen.sections).toEqual(frozen.sections);
  expect(stillFrozen.snapshot_id).toBe(ciscoSnapshot);

  await page.goto(`/leader/briefings/${frozen.id}`);
  await expect(page.getByRole("heading", { name: frozen.title })).toBeVisible();
  await expect(page.getByText(`业务关注项：${name} · 第 1 版`)).toBeVisible();
  await expect(page.getByText(ciscoSnapshot, { exact: true })).toBeVisible();
  await expect(page.locator(`a[href='/results/${resultId}']`)).toBeVisible();
  await page.reload();
  await expect(page.getByRole("heading", { name: frozen.title })).toBeVisible();
  await expect(page.getByText(`业务关注项：${name} · 第 1 版`)).toBeVisible();
});
