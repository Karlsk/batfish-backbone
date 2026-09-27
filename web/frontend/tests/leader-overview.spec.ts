import { expect, test, type Page } from "@playwright/test";
import { loginAdmin } from "./auth-helpers";

const fixtureSnapshots = ["small_network", "cisco_four"];

async function findCard(page: Page, name: string) {
  for (let attempt = 0; attempt < 20; attempt++) {
    const card = page
      .locator(".leader-overview-card")
      .filter({ hasText: name });
    if (await card.count()) return card;
    const more = page.getByRole("button", { name: "加载更多网络" });
    if (!(await more.count())) break;
    await more.click();
    await expect(more).toBeEnabled();
  }
  throw new Error(`Network ${name} was not listed`);
}

test("real r1/r2 and Cisco networks appear in the complete overview and retain evidence", async ({
  page,
}, testInfo) => {
  test.setTimeout(120000);
  await loginAdmin(page);
  await page.getByRole("link", { name: "领导视图" }).click();
  await expect(page.getByRole("heading", { name: "网络总览" })).toBeVisible();
  const response = await page.request.get(
    "/api/v1/leader/overview?offset=0&limit=20",
  );
  expect(response.ok()).toBe(true);
  const overview = await response.json();
  expect(overview.recent_comparisons.length).toBeGreaterThan(0);
  await expect(
    page.locator(".leader-overview-metrics strong").first(),
  ).toHaveText(String(overview.total));
  await expect(page.locator(".leader-recent-card")).toHaveCount(
    overview.recent_comparisons.length,
  );
  await expect(page.locator(".leader-recent-card").first()).toContainText(
    overview.recent_comparisons[0].display_name,
  );
  const networkLinks: { name: string; href: string }[] = [];
  for (const fixture of fixtureSnapshots) {
    const card = await findCard(page, `就绪快照：${fixture}`);
    const name = await card.getByRole("heading", { level: 3 }).innerText();
    await expect(card).toContainText("结果");
    const href = await card
      .getByRole("link", { name: "查看网络详情" })
      .getAttribute("href");
    expect(href).toBeTruthy();
    networkLinks.push({ name, href: href! });
  }
  for (const { name, href } of networkLinks) {
    await page.goto(href);
    await expect(
      page.getByRole("heading", { name, exact: true }),
    ).toBeVisible();
    await expect(page.getByText("最近就绪来源")).toBeVisible();
    await expect(
      page.getByRole("link", { name: "查看解析证据" }),
    ).toBeVisible();
    await page.reload();
    await expect(
      page.getByRole("heading", { name, exact: true }),
    ).toBeVisible();
    await page.getByRole("link", { name: "返回全部网络" }).click();
    await expect(page.locator(".leader-overview-metrics")).toBeVisible();
  }
  for (const [width, theme] of [
    [1280, "light"],
    [1440, "dark"],
    [1920, "light"],
  ] as const) {
    await page.setViewportSize({ width, height: 900 });
    if (theme === "dark")
      await page.getByRole("button", { name: "深色主题" }).click();
    else if (await page.getByRole("button", { name: "浅色主题" }).count())
      await page.getByRole("button", { name: "浅色主题" }).click();
    await expect(page.locator("html")).toHaveAttribute("data-theme", theme);
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
    await page.screenshot({
      path: testInfo.outputPath(`overview-${width}-${theme}.png`),
      animations: "disabled",
      fullPage: true,
    });
  }
  await page.keyboard.press("Tab");
  expect(await page.evaluate(() => document.activeElement?.tagName)).toMatch(
    /A|BUTTON/,
  );
});

test("overview keeps the service failure and retry visible", async ({
  page,
}) => {
  await loginAdmin(page);
  await page.route("**/api/v1/leader/overview?*", async (route) => {
    await route.fulfill({
      status: 503,
      contentType: "application/json",
      body: JSON.stringify({
        error: {
          code: "NOT_READY",
          message: "服务尚未就绪，请稍后重试。",
          request_id: "leader-overview-test",
        },
      }),
    });
  });
  await page.goto("/leader/overview");
  await expect(page.getByRole("button", { name: "重试" })).toBeVisible();
  await expect(page.getByText("服务尚未就绪，请稍后重试。")).toBeVisible();
  await page.unroute("**/api/v1/leader/overview?*");
  await page.getByRole("button", { name: "重试" }).click();
  await expect(page.locator(".leader-overview-metrics")).toBeVisible();
});
