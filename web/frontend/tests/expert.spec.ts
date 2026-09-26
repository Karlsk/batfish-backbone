import { test, expect } from "@playwright/test";
import { randomUUID } from "node:crypto";
import { readdirSync } from "node:fs";
import { resolve } from "node:path";
import { loginAdmin } from "./auth-helpers";

test("registered expert query matches dedicated nodes and rejects unknown options", async ({
  page,
}, info) => {
  test.setTimeout(240000);
  await page.setViewportSize({ width: 1440, height: 1000 });
  await loginAdmin(page);
  await page.getByRole("link", { name: "网络与快照", exact: true }).click();
  await page.getByRole("button", { name: "创建网络", exact: true }).click();
  const name = "专家目录-" + randomUUID().slice(0, 6);
  const dialog = page.getByRole("dialog", { name: "创建网络" });
  await dialog.getByLabel("网络名称", { exact: true }).fill(name);
  await dialog.getByRole("button", { name: "创建", exact: true }).click();
  const folder = resolve("../backend/tests/fixtures/cisco_four/configs");
  await page
    .getByLabel("选择配置文件", { exact: true })
    .setInputFiles(readdirSync(folder).map((file) => resolve(folder, file)));
  await page.getByRole("button", { name: "上传并校验", exact: true }).click();
  await expect(page.getByText(/文件校验完成.*尚未初始化/)).toBeVisible();
  await page.getByLabel("快照名称", { exact: true }).fill("专家查询样本");
  await page.getByRole("button", { name: "提交初始化", exact: true }).click();
  const snapshot = page.getByRole("row").filter({ hasText: "专家查询样本" });
  await expect(snapshot.getByText(/^就绪/)).toBeVisible({ timeout: 90000 });
  await snapshot.getByRole("button", { name: "选择快照", exact: true }).click();

  await page.getByRole("link", { name: "专家查询", exact: true }).click();
  await page.getByRole("combobox", { name: "专家能力" }).click();
  await page.getByRole("option", { name: /Devices · nodes/ }).click();
  await expect(page.getByText(/"properties"/).first()).toBeVisible();
  await page.getByRole("button", { name: /高级参数/ }).click();
  const options = page.getByRole("textbox", { name: "专家 options JSON" });
  await options.fill('{"host":"foreign"}');
  await page.getByRole("button", { name: "运行专家查询" }).click();
  await expect(page.getByText(/body.parameters.options.host/)).toBeVisible();
  await expect(options).toHaveValue('{"host":"foreign"}');
  await options.fill("{}");
  await expect(page.getByText(/body.parameters.options.host/)).toBeHidden();
  for (const theme of ["深色主题", "浅色主题"]) {
    await page.getByRole("button", { name: theme, exact: true }).click();
    await page.screenshot({
      path: info.outputPath("expert-" + theme + ".png"),
      fullPage: true,
      animations: "disabled",
    });
  }
  await page.getByRole("button", { name: "运行专家查询" }).click();
  await expect(page.getByText("已完成", { exact: true })).toBeVisible({
    timeout: 90000,
  });
  await page.getByRole("button", { name: "查看分析结果" }).click();
  await expect(page.getByText("c1", { exact: true }).first()).toBeVisible();
  const expertResult = page.url();

  await page.getByRole("link", { name: "网络分析", exact: true }).click();
  await page.getByRole("button", { name: "执行查询", exact: true }).click();
  await expect(page.getByText("已完成", { exact: true })).toBeVisible({
    timeout: 90000,
  });
  await page.getByRole("button", { name: "查看分析结果" }).click();
  expect(page.url()).toBe(expertResult);
});
