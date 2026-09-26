import { test, expect } from "@playwright/test";
import { randomUUID } from "node:crypto";
import { readdirSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { loginAdmin } from "./auth-helpers";

test("Cisco ACL candidate, permit, implicit deny, evidence and trace handoff", async ({
  page,
}, info) => {
  test.setTimeout(240000);
  await page.setViewportSize({ width: 1440, height: 1000 });
  await loginAdmin(page);
  await page.getByRole("link", { name: "网络与快照", exact: true }).click();
  await page.getByRole("button", { name: "创建网络", exact: true }).click();
  const network = `ACL-${randomUUID().slice(0, 6)}`;
  const dialog = page.getByRole("dialog", { name: "创建网络" });
  await dialog.getByLabel("网络名称", { exact: true }).fill(network);
  await dialog.getByRole("button", { name: "创建", exact: true }).click();
  const folder = resolve("../backend/tests/fixtures/cisco_four/configs");
  const files = readdirSync(folder).map((filename) => {
    let content = readFileSync(resolve(folder, filename), "utf8");
    if (filename === "c2.cfg")
      content = content.replace(
        "end",
        "ip access-list extended WEB-TEST\n permit ip host 10.64.0.1 host 10.64.0.2\n deny ip host 10.64.0.1 host 10.64.0.4\n!\nend",
      );
    return {
      name: filename,
      mimeType: "text/plain",
      buffer: Buffer.from(content),
    };
  });
  await page.getByLabel("选择配置文件", { exact: true }).setInputFiles(files);
  await page.getByRole("button", { name: "上传并校验", exact: true }).click();
  await expect(page.getByText(/文件校验完成.*尚未初始化/)).toBeVisible();
  await page.getByLabel("快照名称", { exact: true }).fill("ACL 样本");
  await page.getByRole("button", { name: "提交初始化", exact: true }).click();
  const snapshot = page.getByRole("row").filter({ hasText: "ACL 样本" });
  await expect(snapshot.getByText(/^就绪/)).toBeVisible({ timeout: 90000 });
  await snapshot.getByRole("button", { name: "选择快照", exact: true }).click();

  async function selectAcl() {
    await page.getByRole("link", { name: "ACL 流量测试", exact: true }).click();
    await page.getByRole("button", { name: "加载设备与接口候选" }).click();
    await page.getByRole("combobox", { name: "设备", exact: true }).click();
    await page.getByRole("option", { name: "c2", exact: true }).click();
    await page.getByRole("button", { name: "加载此设备 ACL" }).click();
    await page.getByRole("combobox", { name: "ACL", exact: true }).click();
    await page.getByRole("option", { name: "WEB-TEST", exact: true }).click();
    await page.getByRole("textbox", { name: "源 IPv4 地址" }).fill("10.64.0.1");
  }

  await selectAcl();
  await page.getByRole("textbox", { name: "目标 IPv4 地址" }).fill("10.64.0.2");
  await page.getByRole("button", { name: "测试 ACL 流量" }).click();
  await expect(page.getByText("已完成", { exact: true })).toBeVisible({
    timeout: 90000,
  });
  await page.getByRole("button", { name: "查看分析结果" }).click();
  await expect(
    page.getByText("ACL 局部放行", { exact: true }).first(),
  ).toBeVisible();
  await expect(page.getByText(/permit ip host 10\.64\.0\.1/)).toBeVisible();
  for (const theme of ["深色主题", "浅色主题"]) {
    await page.getByRole("button", { name: theme, exact: true }).click();
    await page.screenshot({
      path: info.outputPath(`acl-${theme}.png`),
      fullPage: true,
      animations: "disabled",
    });
  }
  await page.getByRole("button", { name: "查看证据" }).click();
  const detail = page.getByRole("dialog", { name: "ACL 命中详情" });
  await expect(detail.getByText("实际 Flow")).toBeVisible();
  await expect(detail.getByText(/configs\/c2\.cfg/)).toBeVisible();
  await detail.getByRole("button", { name: "关闭", exact: true }).click();
  await page
    .getByRole("button", { name: "继续分析路径（需选择起点）" })
    .click();
  await expect(page).toHaveURL(/\/traceroute$/);
  await expect(
    page.getByRole("textbox", { name: "目标 IPv4 地址" }),
  ).toHaveValue("10.64.0.2");
  await expect(page.getByRole("combobox", { name: "起点设备" })).toBeEmpty();

  await page.getByRole("link", { name: "ACL 流量测试", exact: true }).click();
  await page.getByRole("button", { name: "放弃并切换" }).click();
  await selectAcl();
  await page.getByRole("textbox", { name: "目标 IPv4 地址" }).fill("10.64.0.3");
  await page.getByRole("button", { name: "测试 ACL 流量" }).click();
  await expect(page.getByText("已完成", { exact: true })).toBeVisible({
    timeout: 90000,
  });
  await page.getByRole("button", { name: "查看分析结果" }).click();
  await expect(
    page.getByText("隐式拒绝", { exact: true }).first(),
  ).toBeVisible();
  await expect(page.getByText("没有匹配规则（隐式拒绝）")).toBeVisible();
  await page.getByRole("button", { name: "查看证据" }).click();
  await expect(
    page
      .getByRole("dialog", { name: "ACL 命中详情" })
      .getByText("没有可用来源引用"),
  ).toBeVisible();
});

test("unsupported Huawei/H3C ACL model never shows a permit", async ({
  page,
}) => {
  test.setTimeout(180000);
  await loginAdmin(page);
  await page.getByRole("link", { name: "网络与快照", exact: true }).click();
  await page.getByRole("button", { name: "创建网络", exact: true }).click();
  const network = `ACL-vendor-${randomUUID().slice(0, 6)}`;
  const dialog = page.getByRole("dialog", { name: "创建网络" });
  await dialog.getByLabel("网络名称", { exact: true }).fill(network);
  await dialog.getByRole("button", { name: "创建", exact: true }).click();
  const folder = resolve("../backend/tests/fixtures/small_network/configs");
  await page
    .getByLabel("选择配置文件", { exact: true })
    .setInputFiles(
      readdirSync(folder).map((filename) => resolve(folder, filename)),
    );
  await page.getByRole("button", { name: "上传并校验", exact: true }).click();
  await expect(page.getByText(/文件校验完成.*尚未初始化/)).toBeVisible();
  await page.getByLabel("快照名称", { exact: true }).fill("厂商 ACL 样本");
  await page.getByRole("button", { name: "提交初始化", exact: true }).click();
  const snapshot = page.getByRole("row").filter({ hasText: "厂商 ACL 样本" });
  await expect(snapshot.getByText(/^就绪/)).toBeVisible({ timeout: 90000 });
  await snapshot.getByRole("button", { name: "选择快照", exact: true }).click();
  await page.getByRole("link", { name: "ACL 流量测试", exact: true }).click();
  await page.getByText("高级参数").click();
  await page
    .getByRole("radiogroup", { name: "设备选择方式" })
    .getByText("专家表达式")
    .click();
  await page.getByRole("textbox", { name: "设备表达式" }).fill("r1");
  await page
    .getByRole("radiogroup", { name: "ACL 选择方式" })
    .getByText("专家表达式")
    .click();
  await page.getByRole("textbox", { name: "ACL 表达式" }).fill("TEST-ACL");
  await page.getByRole("textbox", { name: "源 IPv4 地址" }).fill("10.0.0.1");
  await page.getByRole("textbox", { name: "目标 IPv4 地址" }).fill("10.0.0.2");
  await page.getByRole("button", { name: "测试 ACL 流量" }).click();
  await expect(page.getByText(/ACL 模型暂不支持验证/)).toBeVisible();
  await expect(page.getByText("ACL 局部放行", { exact: true })).toHaveCount(0);
});
