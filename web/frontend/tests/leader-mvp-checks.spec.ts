import { expect, test, type Page } from "@playwright/test";
import { loginAdmin } from "./auth-helpers";

async function selectReadyFixture(page: Page, fixture: string) {
  const response = await page.request.get("/api/v1/leader/overview?limit=200");
  expect(response.ok()).toBe(true);
  const overview = await response.json();
  const listed = await page.request.get("/api/v1/networks?limit=50");
  expect(listed.ok()).toBe(true);
  const visibleIds = new Set(
    (await listed.json()).items.map((item: { id: string }) => item.id),
  );
  const card = overview.items.find(
    (item: {
      network_id: string;
      latest_ready_snapshot?: { display_name: string };
    }) =>
      visibleIds.has(item.network_id) &&
      item.latest_ready_snapshot?.display_name === fixture,
  );
  expect(card).toBeTruthy();
  await page.getByLabel("检查网络").click();
  const networkOption = page
    .locator('.ant-select-dropdown:visible [role="option"]')
    .filter({ hasText: card.network_id.slice(0, 8) });
  await expect(networkOption).toBeVisible();
  await networkOption.click();
  await page.getByLabel("配置快照").click();
  await page
    .locator('.ant-select-dropdown:visible [role="option"]')
    .filter({ hasText: card.latest_ready_snapshot.id.slice(0, 8) })
    .click();
}

test("leader runs a configuration check and resumes its fixed detail after refresh", async ({
  page,
}, testInfo) => {
  test.setTimeout(120000);
  await loginAdmin(page);
  await page.getByRole("link", { name: "领导视图" }).click();
  await page.getByRole("link", { name: "自主检查" }).click();
  await expect(page.getByRole("heading", { name: "自主检查" })).toBeVisible();
  await selectReadyFixture(page, "small_network");
  await page.getByRole("button", { name: "配置质量" }).click();
  await page.setViewportSize({ width: 1440, height: 900 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: testInfo.outputPath("checks-workspace-light.png"),
    fullPage: true,
    animations: "disabled",
  });
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: testInfo.outputPath("checks-workspace-mobile.png"),
    fullPage: true,
    animations: "disabled",
  });
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.getByRole("button", { name: "开始检查" }).click();
  await expect(page.getByText("配置解析记录已生成")).toBeVisible();
  await expect(page.getByText("解析问题：", { exact: false })).toBeVisible();
  await page.reload();
  await expect(page.getByText("配置解析记录已生成")).toBeVisible();
  await expect(page.getByRole("link", { name: "查看解析证据" })).toBeVisible();
  await page.getByRole("button", { name: "深色主题" }).click();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: testInfo.outputPath("checks-detail-dark.png"),
    fullPage: true,
    animations: "disabled",
  });
});

test("leader requires a scope and runs one-way trace with preserved advanced options", async ({
  page,
}) => {
  test.setTimeout(120000);
  await loginAdmin(page);
  await page.goto("/leader/checks");
  await selectReadyFixture(page, "cisco_four");
  await page.getByRole("button", { name: "路由检查" }).click();
  await page.getByRole("button", { name: "开始检查" }).click();
  await expect(page.getByText("请填写要检查的 IPv4 网段")).toBeVisible();
  await page.getByRole("button", { name: "虚拟连通性" }).click();
  await page.getByLabel("起点设备或接口").fill("c1");
  await page.getByLabel("目的 IPv4 地址").fill("10.64.0.4");
  await page.getByText("高级条件").click();
  await page.getByLabel("最多返回路径").fill("3");
  await page.getByText("高级条件").click();
  await expect(page.getByText("已生效 1 项")).toBeVisible();
  await page.getByRole("button", { name: "开始检查" }).click();
  await expect(page.getByText(/单向路径推演/).first()).toBeVisible({
    timeout: 90000,
  });
  await expect(page.getByText(/不证明在线转发或回程/)).toBeVisible();
  await expect(
    page.getByRole("link", { name: "查看完整路径证据" }),
  ).toBeVisible();
});

test("business concern prefills an explicit flow and switching networks clears the draft", async ({
  page,
}) => {
  await loginAdmin(page);
  await page.route("**/api/v1/business-concerns?*", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        items: [
          {
            id: "11111111-1111-4111-8111-111111111111",
            name: "支付链路",
            version: 3,
            flows: [
              {
                start_location: "c1",
                destination_ip: "10.64.0.4",
                protocol: "tcp",
                destination_port: 443,
              },
            ],
          },
        ],
        offset: 0,
        limit: 200,
        total: 1,
      }),
    });
  });
  await page.goto("/leader/checks");
  await selectReadyFixture(page, "cisco_four");
  await page.getByRole("button", { name: "虚拟连通性" }).click();
  await page.getByLabel("业务关注项").click();
  await page.getByRole("option", { name: /支付链路/ }).click();
  await expect(page.getByLabel("起点设备或接口")).toHaveValue("c1");
  await expect(page.getByLabel("目的 IPv4 地址")).toHaveValue("10.64.0.4");
  await expect(page.getByText(/已预填 支付链路 第 3 版/)).toBeVisible();
  await page.getByLabel("检查网络").click();
  await page
    .locator(
      '.ant-select-dropdown:visible [role="option"]:not([aria-selected="true"])',
    )
    .first()
    .click();
  await expect(page.getByLabel("配置快照")).toHaveValue("");
  await expect(page.getByLabel("起点设备或接口")).toHaveValue("");
});

test("a service-not-ready response stays visible and offers retry", async ({
  page,
}) => {
  await loginAdmin(page);
  await page.goto("/leader/checks");
  await selectReadyFixture(page, "small_network");
  await page.route("**/api/v1/leader/check-runs", async (route) => {
    if (route.request().method() !== "POST") return route.continue();
    await route.fulfill({
      status: 503,
      contentType: "application/json",
      body: JSON.stringify({
        error: {
          code: "NOT_READY",
          message: "服务尚未就绪",
          request_id: "leader-check-not-ready",
          retryable: true,
          field_errors: [],
        },
      }),
    });
  });
  await page.getByRole("button", { name: "开始检查" }).click();
  await expect(page.getByText("服务尚未就绪，请稍后重试。")).toBeVisible();
  await expect(
    page.getByText("请求编号：leader-check-not-ready"),
  ).toBeVisible();
  await expect(page.getByRole("button", { name: "重试" })).toBeVisible();
  await expect(page).toHaveURL(/\/leader\/checks$/);
});
