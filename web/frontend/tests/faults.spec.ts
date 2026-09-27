import { test, expect } from "@playwright/test";
import { randomUUID } from "node:crypto";
import { readdirSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { loginAdmin } from "./auth-helpers";

test("real Cisco model fault keeps the original baseline and requires scoped analysis", async ({
  page,
}, info) => {
  test.setTimeout(300000);
  await page.setViewportSize({ width: 1440, height: 1000 });
  await loginAdmin(page);
  await page.getByRole("link", { name: "网络与快照", exact: true }).click();
  await page.getByRole("button", { name: "创建网络", exact: true }).click();
  const dialog = page.getByRole("dialog", { name: "创建网络" });
  await dialog
    .getByLabel("网络名称", { exact: true })
    .fill(`Fault-${randomUUID().slice(0, 6)}`);
  await dialog.getByRole("button", { name: "创建", exact: true }).click();
  const folder = resolve("../backend/tests/fixtures/cisco_four/configs");
  await page.getByLabel("选择配置文件", { exact: true }).setInputFiles(
    readdirSync(folder).map((filename) => ({
      name: filename,
      mimeType: "text/plain",
      buffer: Buffer.from(readFileSync(resolve(folder, filename))),
    })),
  );
  await page.getByRole("button", { name: "上传并校验", exact: true }).click();
  await expect(page.getByText(/文件校验完成.*尚未初始化/)).toBeVisible();
  await page.getByLabel("快照名称", { exact: true }).fill("故障基线");
  await page.getByRole("button", { name: "提交初始化", exact: true }).click();
  await expect(
    page.getByRole("row").filter({ hasText: "故障基线" }).getByText(/^就绪/),
  ).toBeVisible({ timeout: 90000 });
  await page.getByRole("link", { name: "故障模拟", exact: true }).click();
  await page.getByRole("combobox", { name: "基线快照" }).click();
  await page.getByRole("option", { name: "故障基线" }).click();
  await page.getByRole("button", { name: "加载设备与接口候选" }).click();
  await expect(page.getByText(/已加载 4 台设备的候选值/)).toBeVisible({
    timeout: 90000,
  });
  await page.getByRole("combobox", { name: "停用设备" }).click();
  await page.getByRole("option", { name: "c1", exact: true }).click();
  await page.getByRole("textbox", { name: "方案名称" }).fill("模拟 c1 故障");
  await expect(page.getByText(/原始基线保持不变/)).toBeVisible();
  await expect(page.getByText(/仅在 Batfish 模型中模拟/)).toBeVisible();
  await page.evaluate(() => window.scrollTo(0, 0));
  for (const theme of ["深色主题", "浅色主题"]) {
    await page.getByRole("button", { name: theme, exact: true }).click();
    await page.screenshot({
      path: info.outputPath(`fault-${theme}.png`),
      fullPage: true,
      animations: "disabled",
    });
  }
  await page.getByRole("button", { name: "创建派生快照" }).click();
  await expect(page.getByRole("link", { name: "查看任务详情" })).toBeVisible();
  await expect(page.getByRole("link", { name: "进入影响分析" })).toBeVisible({
    timeout: 120000,
  });
  await page.getByRole("link", { name: "进入影响分析" }).click();
  await expect(page.getByText(/已带入故障方案的原始基线/)).toBeVisible();
  await expect(page.getByRole("button", { name: "创建比较" })).toBeEnabled();
  await page.getByRole("button", { name: "创建比较" }).click();
  await expect(page.getByText("基线：故障基线")).toBeVisible();
  await expect(page.getByText("候选：模拟 c1 故障")).toBeVisible();
  await page.getByRole("tab", { name: "可达性变化" }).click();
  await expect(
    page.getByRole("button", { name: "分析可达性变化" }),
  ).toBeDisabled();
});
