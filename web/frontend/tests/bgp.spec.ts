import { test, expect } from "@playwright/test";
import { randomUUID } from "node:crypto";
import { readdirSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { loginAdmin } from "./auth-helpers";

test("Cisco BGP model status, raw filter, endpoint detail, route and compatibility", async ({
  page,
}, info) => {
  test.setTimeout(240000);
  await loginAdmin(page);
  await page.getByRole("link", { name: "网络与快照", exact: true }).click();
  await page.getByRole("button", { name: "创建网络", exact: true }).click();
  const network = `BGP-${randomUUID().slice(0, 6)}`;
  const dialog = page.getByRole("dialog", { name: "创建网络" });
  await dialog.getByLabel("网络名称", { exact: true }).fill(network);
  await dialog.getByRole("button", { name: "创建", exact: true }).click();
  await expect(page.getByRole("heading", { name: network })).toBeVisible();
  const folder = resolve("../backend/tests/fixtures/cisco_four/configs");
  const files = readdirSync(folder).map((filename) => {
    let content = readFileSync(resolve(folder, filename), "utf8");
    const number = Number(filename.match(/c(\d+)\.cfg/)?.[1]);
    const peers = [
      ...content.matchAll(/ip address (172\.20\.\d+\.[12]) /g),
    ].map((match) =>
      match[1].replace(/\.[12]$/, (end) => (end === ".1" ? ".2" : ".1")),
    );
    const bgp =
      `router bgp 65000\n bgp router-id 10.64.0.${number}\n` +
      peers
        .map(
          (peer) =>
            ` neighbor ${peer} remote-as ${number === 1 && peer === "172.20.12.2" ? 65001 : 65000}\n`,
        )
        .join("");
    content = content.replace("end", `${bgp}!\nend`);
    return {
      name: filename,
      mimeType: "text/plain",
      buffer: Buffer.from(content),
    };
  });
  await page.getByLabel("选择配置文件", { exact: true }).setInputFiles(files);
  await page.getByRole("button", { name: "上传并校验", exact: true }).click();
  await expect(page.getByText(/文件校验完成.*尚未初始化/)).toBeVisible();
  await page.getByLabel("快照名称", { exact: true }).fill("BGP 样本");
  await page.getByRole("button", { name: "提交初始化", exact: true }).click();
  const row = page.getByRole("row").filter({ hasText: "BGP 样本" });
  await expect(row.getByText(/^就绪/)).toBeVisible({ timeout: 90000 });
  await row.getByRole("button", { name: "选择快照", exact: true }).click();
  await page.getByRole("link", { name: "BGP 会话", exact: true }).click();
  await expect(page.getByRole("heading", { name: "BGP 会话" })).toBeVisible();
  await page
    .getByRole("button", { name: "分析 BGP 会话", exact: true })
    .click();
  await expect(page.getByText("已完成", { exact: true })).toBeVisible({
    timeout: 90000,
  });
  await page.getByRole("button", { name: "查看分析结果", exact: true }).click();
  const statusUrl = page.url();
  await expect(
    page.getByText(/模型计算，非实时设备状态/).first(),
  ).toBeVisible();
  await expect(
    page.getByText("NOT_COMPATIBLE", { exact: true }).first(),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "查看会话详情" })
    .first()
    .scrollIntoViewIfNeeded();
  await expect(
    page.getByRole("button", { name: "查看会话详情" }).first(),
  ).toBeInViewport();
  await page.evaluate(() => window.scrollTo(0, 0));
  for (const theme of ["深色主题", "浅色主题"]) {
    await page.getByRole("button", { name: theme, exact: true }).click();
    await expect(page.locator("html")).toHaveAttribute(
      "data-theme",
      theme === "深色主题" ? "dark" : "light",
    );
    await page.waitForTimeout(150);
    await page.screenshot({
      path: info.outputPath(`bgp-${theme}.png`),
      fullPage: true,
      animations: "disabled",
    });
  }
  await page
    .getByRole("textbox", { name: "原始状态筛选" })
    .fill("NOT_COMPATIBLE");
  await page.getByRole("button", { name: "应用状态筛选" }).click();
  await expect(page.getByText("生效状态：NOT_COMPATIBLE")).toBeVisible();
  await page.getByRole("button", { name: "查看会话详情" }).first().click();
  const detail = page.getByRole("dialog", { name: "BGP 会话详情" });
  await expect(detail).toBeVisible();
  await expect(detail.getByText("本地 / 远端 AS")).toBeVisible();
  await expect(
    detail.getByRole("button", { name: "查询本地设备路由" }),
  ).toBeVisible();
  await detail.getByRole("button", { name: "查询本地设备路由" }).click();
  await expect(page).toHaveURL(/\/analysis\/routes$/);
  await expect(
    page
      .locator(".selector-field .ant-select-selection-item")
      .filter({ hasText: "c1" }),
  ).toBeVisible();
  await page.goto(statusUrl);
  await page
    .getByText("切换分析模式或高级条件（生成新结果）", { exact: true })
    .click();
  await page.getByRole("combobox", { name: "BGP 分析模式" }).click();
  await page.getByRole("option", { name: "配置兼容性" }).click();
  await page
    .getByRole("button", { name: "分析 BGP 会话", exact: true })
    .click();
  await expect(page.getByText("已完成", { exact: true })).toBeVisible({
    timeout: 90000,
  });
  await page.getByRole("button", { name: "查看分析结果", exact: true }).click();
  await expect(
    page.getByText("BGP 配置兼容性分析", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("columnheader", { name: "原始兼容状态" }),
  ).toBeVisible();
  expect(page.url()).not.toBe(statusUrl);
});

test("Huawei/H3C config with no modeled BGP rows remains an explained empty result", async ({
  page,
}) => {
  test.setTimeout(180000);
  await loginAdmin(page);
  await page.getByRole("link", { name: "网络与快照", exact: true }).click();
  await page.getByRole("button", { name: "创建网络", exact: true }).click();
  const network = `BGP-empty-${randomUUID().slice(0, 6)}`;
  const dialog = page.getByRole("dialog", { name: "创建网络" });
  await dialog.getByLabel("网络名称", { exact: true }).fill(network);
  await dialog.getByRole("button", { name: "创建", exact: true }).click();
  await expect(page.getByRole("heading", { name: network })).toBeVisible();
  const folder = resolve("../backend/tests/fixtures/small_network/configs");
  await page
    .getByLabel("选择配置文件", { exact: true })
    .setInputFiles(
      readdirSync(folder).map((filename) => resolve(folder, filename)),
    );
  await page.getByRole("button", { name: "上传并校验", exact: true }).click();
  await expect(page.getByText(/文件校验完成.*尚未初始化/)).toBeVisible();
  await page.getByLabel("快照名称", { exact: true }).fill("BGP 空会话样本");
  await page.getByRole("button", { name: "提交初始化", exact: true }).click();
  const row = page.getByRole("row").filter({ hasText: "BGP 空会话样本" });
  await expect(row.getByText(/^就绪/)).toBeVisible({ timeout: 90000 });
  await row.getByRole("button", { name: "选择快照", exact: true }).click();
  await page.getByRole("link", { name: "BGP 会话", exact: true }).click();
  await page
    .getByRole("button", { name: "分析 BGP 会话", exact: true })
    .click();
  await expect(page.getByText("已完成", { exact: true })).toBeVisible({
    timeout: 90000,
  });
  await page.getByRole("button", { name: "查看分析结果", exact: true }).click();
  await expect(page.getByText(/此快照没有匹配的 BGP 会话/)).toBeVisible();
  await expect(
    page.getByText(/IPv6 BGP session behavior is not modeled/),
  ).toBeVisible();
});
