import { randomUUID } from "node:crypto";
import { expect, test } from "@playwright/test";
import { labCredentials, login } from "./auth-helpers";

test("leader briefing creation, immutable revision, meeting, print and shared member access", async ({
  page,
  browser,
}, testInfo) => {
  test.setTimeout(180000);
  const origin = "http://127.0.0.1:15173";
  const adminLogin = await page.request.post("/api/v1/auth/login", {
    headers: { Origin: origin },
    data: labCredentials(),
  });
  expect(adminLogin.ok()).toBe(true);
  const headers = {
    Origin: origin,
    "X-CSRF-Token": (await adminLogin.json()).csrf_token as string,
  };
  const networksResponse = await page.request.get("/api/v1/networks?limit=50");
  expect(networksResponse.ok(), await networksResponse.text()).toBe(true);
  const networks = await networksResponse.json();
  const overviewResponse = await page.request.get(
    "/api/v1/leader/overview?limit=200",
  );
  expect(overviewResponse.ok(), await overviewResponse.text()).toBe(true);
  const overview = await overviewResponse.json();
  const network = overview.items.find(
    (item: { network_id: string; latest_ready_snapshot: unknown }) =>
      item.latest_ready_snapshot &&
      networks.items.some(
        (entry: { id: string }) => entry.id === item.network_id,
      ),
  );
  expect(network).toBeTruthy();
  const networkId = network.network_id as string;
  const snapshotId = network.latest_ready_snapshot.id as string;
  const networkName = network.display_name as string;
  const snapshotName = network.latest_ready_snapshot.display_name as string;
  const submitted = await page.request.post("/api/v1/leader/check-runs", {
    headers: { ...headers, "Idempotency-Key": randomUUID() },
    data: {
      network_id: networkId,
      snapshot_id: snapshotId,
      template_id: "devices",
    },
  });
  expect(submitted.status()).toBe(201);
  const runId = (await submitted.json()).id as string;
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

  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "网络分析，从一份配置开始" }),
  ).toBeVisible();
  await page.goto("/leader/briefings/new");
  await expect(
    page.getByRole("heading", { name: "从已完成的检查，形成固定汇报" }),
  ).toBeVisible();
  await page.getByLabel("汇报网络").click();
  await page
    .getByRole("option", {
      name: `${networkName} · ${networkId.slice(0, 8)}`,
      exact: true,
    })
    .click();
  await page.getByLabel("汇报快照").click();
  await page
    .getByRole("option", {
      name: `${snapshotName} · ${snapshotId.slice(0, 8)}`,
      exact: true,
    })
    .click();
  await page
    .locator(".leader-briefing-run")
    .filter({ hasText: runId.slice(0, 8) })
    .getByRole("checkbox")
    .check();
  const title = `领导端汇报-${randomUUID().slice(0, 6)}`;
  await page.getByLabel("汇报标题").fill(title);
  await page.getByLabel("汇报人工备注").fill("人工观察：等待例会确认");
  await expect(page.getByText("模型覆盖", { exact: false })).toBeVisible();
  await page.getByRole("button", { name: "生成固定汇报" }).click();
  await expect(page).toHaveURL(/\/leader\/briefings\/[0-9a-f-]+$/, {
    timeout: 30000,
  });
  const firstId = page.url().split("/").pop()!;
  await expect(page.getByRole("heading", { name: title })).toBeVisible();
  await expect(page.getByText("人工备注 · 由团队填写")).toBeVisible();
  await expect(page.getByText("模型边界")).toBeVisible();
  await page.screenshot({
    path: testInfo.outputPath("briefing-detail-light.png"),
    fullPage: true,
  });

  await page.getByRole("link", { name: /打开会议视图/ }).click();
  await expect(page).toHaveURL(
    new RegExp(`/leader/briefings/${firstId}/present$`),
  );
  await expect(page.locator(".leader-presentation h1")).toHaveText(title);
  await expect(
    page
      .locator(".leader-presentation-hero-meta")
      .getByText(networkName, { exact: true }),
  ).toBeVisible();
  await expect(
    page
      .locator(".leader-presentation-hero-meta")
      .getByText(snapshotName, { exact: true }),
  ).toBeVisible();
  await expect(page.getByText("模型边界")).toBeVisible();
  await expect(page.locator(".leader-shell")).toHaveCount(0);
  await page.screenshot({
    path: testInfo.outputPath("briefing-meeting-light.png"),
    fullPage: true,
  });
  await page.emulateMedia({ media: "print" });
  await expect(page.locator(".leader-presentation-controls")).toHaveCSS(
    "display",
    "none",
  );
  await expect(page.locator(".leader-presentation h1")).toHaveText(title);
  await page.pdf({
    path: testInfo.outputPath("briefing-print.pdf"),
    format: "A4",
    printBackground: true,
  });
  await page.emulateMedia({ media: "screen", reducedMotion: "reduce" });
  await page.getByRole("button", { name: "深色主题" }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await page.screenshot({
    path: testInfo.outputPath("briefing-meeting-dark.png"),
    fullPage: true,
  });
  await page.getByRole("link", { name: /返回详情/ }).click();
  await page.getByRole("button", { name: "修改标题/备注" }).click();
  const revisedTitle = `${title}（修订）`;
  await page.getByLabel("修订标题").fill(revisedTitle);
  await page.getByRole("button", { name: "保存为新版本" }).click();
  await expect(page.getByRole("heading", { name: revisedTitle })).toBeVisible();
  await expect(
    page.getByText("这是一份新修订", { exact: false }),
  ).toBeVisible();
  const secondId = new URL(page.url()).pathname.split("/").pop()!;
  expect(secondId).not.toBe(firstId);
  await page.goto(`/leader/briefings/${firstId}`);
  await expect(page.getByRole("heading", { name: title })).toBeVisible();

  const username = `briefing-${randomUUID().slice(0, 8)}`;
  const temporary = `Temp-${randomUUID()}`;
  const password = `New-${randomUUID()}`;
  const createMember = await page.request.post("/api/v1/users", {
    headers,
    data: { username, temporary_password: temporary, role: "member" },
  });
  expect(createMember.status()).toBe(201);
  const memberContext = await browser.newContext();
  try {
    const member = await memberContext.newPage();
    await login(member, username, temporary);
    await expect(
      member.getByRole("heading", { name: "设置新密码" }),
    ).toBeVisible();
    await member.getByLabel("当前密码").fill(temporary);
    await member.getByLabel("新密码", { exact: true }).fill(password);
    await member.getByLabel("确认新密码").fill(password);
    await member.getByRole("button", { name: "更新密码并重新登录" }).click();
    await expect(
      member.getByRole("heading", { name: "登录工作台" }),
    ).toBeVisible();
    await login(member, username, password);
    await expect(
      member.getByRole("heading", { name: "网络分析，从一份配置开始" }),
    ).toBeVisible();
    await member.goto(`/leader/briefings/${firstId}`);
    await expect(member.getByRole("heading", { name: title })).toBeVisible();
    await expect(member.getByText("人工观察：等待例会确认")).toBeVisible();
    await expect(member.getByRole("button", { name: "归档汇报" })).toHaveCount(
      0,
    );
    await member.goto(`/leader/briefings/${firstId}/present`);
    await expect(member.locator(".leader-presentation h1")).toHaveText(title);
  } finally {
    await memberContext.close();
  }

  await page.route(`**/api/v1/leader/briefings/${firstId}`, async (route) => {
    const response = await route.fetch();
    const body = await response.json();
    body.source_available = false;
    body.sections = body.sections.map((section: object) => ({
      ...section,
      evidence_available: false,
    }));
    await route.fulfill({ response, body: JSON.stringify(body) });
  });
  await page.reload();
  await expect(page.getByText(/原网络、快照或比较来源已不可用/)).toBeVisible();
  await expect(page.getByText(/来源已不可用 ·/)).toBeVisible();
  await expect(
    page.locator(".leader-briefing-section a[href^='/results/']"),
  ).toHaveCount(0);
  await expect(page.getByRole("heading", { name: title })).toBeVisible();
});
