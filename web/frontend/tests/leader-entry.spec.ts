import { randomUUID } from "node:crypto";
import { resolve } from "node:path";
import { expect, test } from "@playwright/test";
import { labCredentials, loginAdmin } from "./auth-helpers";

test("a chosen leader entry survives refresh while login defaults stay technical", async ({
  page,
}) => {
  await loginAdmin(page);
  await page.getByRole("link", { name: "领导视图" }).click();
  await expect(page).toHaveURL(/\/leader\/overview$/);
  await expect(page.getByRole("heading", { name: "网络总览" })).toBeVisible();
  await page.reload();
  await expect(page.getByRole("heading", { name: "网络总览" })).toBeVisible();
  await page.goto("/");
  await expect(page).toHaveURL(/\/leader\/overview$/);
  await page.getByRole("link", { name: "技术工作台" }).click();
  await expect(page).toHaveURL(/\/$/);
  await expect(
    page.getByRole("heading", { name: "网络分析，从一份配置开始" }),
  ).toBeVisible();
  await page.reload();
  await expect(page).toHaveURL(/\/$/);
});

test("leader entry shares the session and appearance controls", async ({
  page,
}, testInfo) => {
  await loginAdmin(page);
  await page.getByRole("button", { name: "深色主题" }).click();
  await page.getByRole("link", { name: "领导视图" }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await expect(
    page.getByText(labCredentials().username, { exact: false }),
  ).toBeVisible();
  for (const [width, theme] of [
    [1440, "dark"],
    [768, "light"],
    [390, "light"],
  ] as const) {
    await page.setViewportSize({ width, height: 960 });
    await page
      .getByRole("button", { name: theme === "dark" ? "深色主题" : "浅色主题" })
      .click();
    await expect(page.locator("html")).toHaveAttribute("data-theme", theme);
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
    await page.screenshot({
      path: testInfo.outputPath(`leader-${width}-${theme}.png`),
      animations: "disabled",
      fullPage: true,
    });
  }
  await page.getByRole("button", { name: "退出登录" }).click();
  await expect(page.getByRole("heading", { name: "登录工作台" })).toBeVisible();
});

test("entry switching keeps the chosen network and snapshot in memory", async ({
  page,
}) => {
  test.setTimeout(120000);
  await loginAdmin(page);
  const networkName = `入口保持-${randomUUID().slice(0, 8)}`;
  const snapshotName = `基线-${randomUUID().slice(0, 8)}`;
  await page.getByRole("link", { name: "网络与快照", exact: true }).click();
  await page.getByRole("button", { name: "创建网络", exact: true }).click();
  const dialog = page.getByRole("dialog", { name: "创建网络" });
  await dialog.getByLabel("网络名称", { exact: true }).fill(networkName);
  await dialog.getByRole("button", { name: "创建", exact: true }).click();
  await expect(page.getByRole("heading", { name: networkName })).toBeVisible();
  await page.getByRole("radio", { name: "配置文件", exact: true }).check();
  await page
    .getByLabel("选择配置文件", { exact: true })
    .setInputFiles(
      ["r1.cfg", "r2.cfg"].map((name) =>
        resolve("../backend/tests/fixtures/small_network/configs", name),
      ),
    );
  await page.getByRole("button", { name: "上传并校验" }).click();
  await expect(page.getByText(/文件校验完成.*尚未初始化/)).toBeVisible();
  await page.getByLabel("快照名称", { exact: true }).fill(snapshotName);
  await page.getByRole("button", { name: "提交初始化", exact: true }).click();
  const row = page.getByRole("row").filter({ hasText: snapshotName });
  await expect(row.getByText(/^就绪/)).toBeVisible({ timeout: 90000 });
  await row.getByRole("button", { name: "选择快照" }).click();
  await expect(page.locator(".context-group")).toContainText(snapshotName);
  await page.getByRole("link", { name: "领导视图" }).click();
  await expect(page.locator(".leader-context-note")).toContainText(networkName);
  await expect(page.locator(".leader-context-note")).toContainText(
    snapshotName,
  );
  await page.getByRole("link", { name: "技术工作台" }).click();
  await expect(page.locator(".context-group")).toContainText(networkName);
  await expect(page.locator(".context-group")).toContainText(snapshotName);
});
