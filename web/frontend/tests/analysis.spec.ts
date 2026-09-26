import { verifyDeletion } from "./deletion-helpers";
import { verifyDownloads } from "./export-helpers";
import { randomUUID } from "node:crypto";
import { resolve } from "node:path";
import { readdirSync } from "node:fs";
import { test, expect, type Page } from "@playwright/test";
import { loginAdmin } from "./auth-helpers";
async function query(
  page: Page,
  label: string,
  ip?: string,
  node?: string,
  screenshot?: string,
) {
  await page.getByRole("link", { name: "网络分析", exact: true }).click();
  await page.getByRole("link", { name: label, exact: true }).click();
  if (node) {
    await page
      .getByRole("button", { name: "加载设备与接口候选", exact: true })
      .click();
    await expect(page.getByText(/已加载 .* 台设备的候选值/)).toBeVisible({
      timeout: 90000,
    });
    await page.getByRole("combobox", { name: "设备名称", exact: true }).click();
    await page.getByRole("option", { name: node, exact: true }).click();
    await page.keyboard.press("Escape");
    const initialTheme = await page.locator("html").getAttribute("data-theme");
    await page
      .getByRole("button", {
        name: initialTheme === "dark" ? "浅色主题" : "深色主题",
      })
      .click();
    await expect(
      page
        .locator(".selector-field .ant-select-selection-item")
        .filter({ hasText: node }),
    ).toBeVisible();
    await page.getByRole("button", { name: "跟随系统" }).click();
    await expect(page.locator("html")).toHaveAttribute(
      "data-theme",
      initialTheme!,
    );
    await page.getByRole("link", { name: "接口", exact: true }).click();
    await expect(
      page.getByRole("dialog", { name: "放弃尚未提交的分析条件？" }),
    ).toBeVisible();
    await page.getByRole("button", { name: "继续填写", exact: true }).click();
    await expect(
      page.getByRole("dialog", { name: "放弃尚未提交的分析条件？" }),
    ).toBeHidden();
  }
  if (screenshot)
    await page.screenshot({
      path: screenshot,
      fullPage: true,
      animations: "disabled",
    });
  if (ip)
    await page
      .getByRole("textbox", {
        name: label === "最长前缀匹配" ? "目标 IPv4 地址" : "IPv4 路由前缀",
        exact: true,
      })
      .fill(ip);
  await page.getByRole("button", { name: "执行查询", exact: true }).click();
  await expect(page.getByText("已完成", { exact: true })).toBeVisible({
    timeout: 90000,
  });
  await page.getByRole("button", { name: "查看分析结果", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "分析结果", exact: true }),
  ).toBeVisible();
}
for (const topology of ["small_network", "cisco_four"]) {
  test(`actual ${topology} inventory routes and LPM results`, async ({
    page,
  }, testInfo) => {
    test.setTimeout(240000);
    await page.setViewportSize({ width: 1280, height: 1000 });
    await loginAdmin(page);
    await page.getByRole("link", { name: "网络与快照", exact: true }).click();
    await page.getByRole("button", { name: "创建网络", exact: true }).click();
    const dialog = page.getByRole("dialog", { name: "创建网络" });
    const name = `分析-${topology}-${randomUUID().slice(0, 6)}`;
    await dialog.getByLabel("网络名称", { exact: true }).fill(name);
    await dialog.getByRole("button", { name: "创建", exact: true }).click();
    await expect(
      page.getByRole("heading", { name, exact: true }),
    ).toBeVisible();
    const folder = resolve(`../backend/tests/fixtures/${topology}/configs`);
    await page
      .getByLabel("选择配置文件", { exact: true })
      .setInputFiles(readdirSync(folder).map((n) => resolve(folder, n)));
    await page.getByRole("button", { name: "上传并校验", exact: true }).click();
    await expect(page.getByText(/文件校验完成.*尚未初始化/)).toBeVisible();
    await page.getByLabel("快照名称", { exact: true }).fill("分析样本");
    const response = page.waitForResponse(
      (r) =>
        r.request().method() === "POST" &&
        /\/snapshots$/.test(new URL(r.url()).pathname),
    );
    await page.getByRole("button", { name: "提交初始化", exact: true }).click();
    const created = await (await response).json();
    const row = page.getByRole("row").filter({ hasText: "分析样本" });
    await expect(row.getByText(/^就绪/)).toBeVisible({ timeout: 90000 });
    await row.getByRole("button", { name: "选择快照", exact: true }).click();
    const node = topology === "small_network" ? "r1" : "c1";
    await query(
      page,
      "设备",
      undefined,
      node,
      testInfo.outputPath(`${topology}-query-form.png`),
    );
    await expect(
      page.getByRole("cell", { name: node, exact: true }).first(),
    ).toBeVisible();
    await expect(
      page.getByText(`来源快照：${created.snapshot_id}`, { exact: true }),
    ).toBeVisible();
    const resultUrl = page.url();
    await page.reload();
    await expect(
      page.getByRole("cell", { name: node, exact: true }).first(),
    ).toBeVisible();
    // Restoring the selector changes future queries, not the immutable result URL.
    const network = page.getByRole("combobox", {
      name: "当前网络",
      exact: true,
    });
    await network.fill(name);
    await expect(
      page.getByRole("option", { name: new RegExp(name) }),
    ).toBeVisible();
    await page.getByRole("option", { name: new RegExp(name) }).click();
    const snapshot = page.getByRole("combobox", {
      name: "当前快照",
      exact: true,
    });
    await snapshot.fill("分析样本");
    await page.getByRole("option", { name: /分析样本/ }).click();
    expect(page.url()).toBe(resultUrl);
    await query(page, "接口");
    await expect(
      page.getByRole("columnheader", { name: "接口", exact: true }).first(),
    ).toBeVisible();
    await query(page, "路由前缀");
    await expect(
      page.getByRole("columnheader", { name: "下一跳", exact: true }).first(),
    ).toBeVisible();
    await expect(
      page.getByRole("cell", { name: node, exact: true }).first(),
    ).toBeVisible();
    if (topology === "cisco_four") {
      await page.getByTitle("下一页", { exact: true }).click();
      await expect(page.getByTitle("上一页", { exact: true })).not.toHaveClass(
        /disabled/,
      );
    }
    await page
      .getByRole("combobox", { name: "结果筛选列", exact: true })
      .click();
    await page.getByRole("option", { name: "路由前缀", exact: true }).click();
    await page
      .getByRole("textbox", { name: "结果筛选值", exact: true })
      .fill("nonexistent-unique-device");
    await page.getByRole("button", { name: "应用筛选", exact: true }).click();
    await expect(
      page.getByText("没有匹配结果；这是有效的空结果，并非任务失败。"),
    ).toBeVisible();
    await verifyDownloads(page, testInfo, "table");
    await page.getByRole("button", { name: "清除筛选", exact: true }).click();
    await expect(
      page.getByRole("cell", { name: node, exact: true }).first(),
    ).toBeVisible();
    await page
      .getByRole("button", { name: "原始行", exact: true })
      .first()
      .click();
    await expect(
      page.getByRole("dialog", { name: "原始结果行" }),
    ).toBeVisible();
    await page
      .getByRole("dialog")
      .getByRole("button", { name: "关闭", exact: true })
      .click();
    await page.screenshot({
      path: testInfo.outputPath(`${topology}-routes.png`),
      fullPage: true,
      animations: "disabled",
    });
    await query(
      page,
      "最长前缀匹配",
      topology === "small_network" ? "10.0.0.2" : "10.64.0.4",
    );
    await expect(
      page.getByRole("columnheader", { name: "匹配路由数", exact: true }),
    ).toBeVisible();
    await expect(
      page.getByRole("cell", { name: node, exact: true }).first(),
    ).toBeVisible();
    await expect(
      page.getByRole("columnheader", { name: "下一跳", exact: true }),
    ).toHaveCount(0);
    await expect(
      page.getByText(`来源快照：${created.snapshot_id}`, { exact: true }),
    ).toBeVisible();
    await page.screenshot({
      path: testInfo.outputPath(`${topology}-lpm.png`),
      fullPage: true,
      animations: "disabled",
    });
    await verifyDeletion(page, testInfo, name, created.snapshot_id);
  });
}
