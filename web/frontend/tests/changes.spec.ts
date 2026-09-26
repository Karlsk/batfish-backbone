import { test, expect } from "@playwright/test";
import { randomUUID } from "node:crypto";
import { readdirSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { loginAdmin } from "./auth-helpers";

test("real Cisco snapshot comparison shows fixed direction and progressive evidence", async ({
  page,
}, info) => {
  test.setTimeout(300000);
  await page.setViewportSize({ width: 1440, height: 1000 });
  await loginAdmin(page);
  await page.getByRole("link", { name: "网络与快照", exact: true }).click();
  await page.getByRole("button", { name: "创建网络", exact: true }).click();
  const network = `Change-${randomUUID().slice(0, 6)}`;
  const dialog = page.getByRole("dialog", { name: "创建网络" });
  await dialog.getByLabel("网络名称", { exact: true }).fill(network);
  await dialog.getByRole("button", { name: "创建", exact: true }).click();
  const folder = resolve("../backend/tests/fixtures/cisco_four/configs");
  async function snapshot(label: string, candidate: boolean) {
    const files = readdirSync(folder).map((filename) => {
      let content = readFileSync(resolve(folder, filename), "utf8");
      if (filename === "c1.cfg") {
        content = content.replace(
          "end",
          `ip route ${candidate ? "203.0.113.0" : "198.51.100.0"} 255.255.255.0 Null0\nend`,
        );
        if (candidate)
          content = content.replace(
            "end",
            "ip access-list extended BLOCK-TO-C4\n deny ip any host 10.64.0.4\n permit ip any any\n!\ninterface GigabitEthernet0/0\n ip access-group BLOCK-TO-C4 out\n!\ninterface GigabitEthernet0/1\n ip access-group BLOCK-TO-C4 out\n!\nend",
          );
      }
      return {
        name: filename,
        mimeType: "text/plain",
        buffer: Buffer.from(content),
      };
    });
    await page.getByLabel("选择配置文件", { exact: true }).setInputFiles(files);
    await page.getByRole("button", { name: "上传并校验", exact: true }).click();
    await expect(page.getByText(/文件校验完成.*尚未初始化/)).toBeVisible();
    await page.getByLabel("快照名称", { exact: true }).fill(label);
    await page.getByRole("button", { name: "提交初始化", exact: true }).click();
    await expect(
      page.getByRole("row").filter({ hasText: label }).getByText(/^就绪/),
    ).toBeVisible({ timeout: 90000 });
  }
  await snapshot("变更前", false);
  await page.getByRole("button", { name: "创建另一份快照" }).click();
  await snapshot("变更后", true);
  await page.getByRole("link", { name: "变更对比", exact: true }).click();
  await expect(page.getByRole("heading", { name: "变更对比" })).toBeVisible();
  await page.getByRole("combobox", { name: "基线快照" }).click();
  await page.getByRole("option", { name: "变更前" }).click();
  await page.getByRole("combobox", { name: "候选快照" }).click();
  await page.getByRole("option", { name: "变更后" }).last().click();
  await page.getByRole("button", { name: "创建比较" }).click();
  await expect(page.getByText("基线：变更前")).toBeVisible();
  await expect(page.getByText("候选：变更后")).toBeVisible();
  await page.getByRole("button", { name: "分析配置文件差异" }).click();
  await expect(page.getByText("configs/c1.cfg")).toBeVisible({
    timeout: 90000,
  });
  await page.getByRole("button", { name: "查看两侧文本" }).click();
  await expect(page.getByText(/ip route 198\.51\.100\.0/)).toBeVisible();
  await expect(page.getByText(/ip route 203\.0\.113\.0/)).toBeVisible();
  for (const theme of ["深色主题", "浅色主题"]) {
    await page.getByRole("button", { name: theme, exact: true }).click();
    await page.screenshot({
      path: info.outputPath(`change-${theme}.png`),
      fullPage: true,
      animations: "disabled",
    });
  }
  await page.getByRole("tab", { name: "路由变化" }).click();
  await page.getByRole("button", { name: "分析路由变化" }).click();
  await expect(page.getByText("候选新增")).toBeVisible({ timeout: 90000 });
  await expect(page.getByText("候选消失")).toBeVisible();
  await page.getByRole("tab", { name: "可达性变化" }).click();
  await expect(
    page.getByRole("button", { name: "分析可达性变化" }),
  ).toBeDisabled();
  await page.getByRole("textbox", { name: "目的 IPv4 范围" }).fill("10.64.0.4");
  await page.getByRole("textbox", { name: "起点设备或接口" }).fill("c1");
  await page
    .getByRole("button", { name: /高级参数/ })
    .last()
    .click();
  await page.getByRole("textbox", { name: "源 IPv4 范围" }).fill("10.64.0.1");
  await page.getByRole("button", { name: "分析可达性变化" }).click();
  await expect(page.getByText("候选消失").last()).toBeVisible({
    timeout: 90000,
  });
  await expect(
    page.getByText("基线（左）", { exact: true }).last(),
  ).toBeVisible();
  await expect(
    page.getByText("候选（右）", { exact: true }).last(),
  ).toBeVisible();
  await page.screenshot({
    path: info.outputPath("change-reachability.png"),
    fullPage: true,
    animations: "disabled",
  });
});
