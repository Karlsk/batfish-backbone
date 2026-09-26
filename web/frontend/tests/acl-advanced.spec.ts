import { test, expect } from "@playwright/test";
import { randomUUID } from "node:crypto";
import { readdirSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { loginAdmin } from "./auth-helpers";

test("Cisco ACL search witness, exact-flow retest and two unreachable reasons", async ({
  page,
}, info) => {
  test.setTimeout(240000);
  const blockerWarnings: string[] = [];
  page.on("console", (message) => {
    if (message.text().includes("A router only supports one blocker"))
      blockerWarnings.push(message.text());
  });
  await page.setViewportSize({ width: 1440, height: 1000 });
  await loginAdmin(page);
  await page.getByRole("link", { name: "网络与快照", exact: true }).click();
  await page.getByRole("button", { name: "创建网络", exact: true }).click();
  const name = "ACL-advanced-" + randomUUID().slice(0, 6);
  const dialog = page.getByRole("dialog", { name: "创建网络" });
  await dialog.getByLabel("网络名称", { exact: true }).fill(name);
  await dialog.getByRole("button", { name: "创建", exact: true }).click();
  const folder = resolve("../backend/tests/fixtures/cisco_four/configs");
  const files = readdirSync(folder).map((filename) => {
    let content = readFileSync(resolve(folder, filename), "utf8");
    if (filename === "c2.cfg")
      content = content.replace(
        "end",
        "object-group network EMPTY-GROUP\n!\nip access-list extended WEB-SEARCH\n permit ip host 10.64.0.1 host 10.64.0.2\n deny ip any any\n permit ip object-group EMPTY-GROUP any\n permit ip host 10.64.0.1 host 10.64.0.4\n!\nend",
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
  await page.getByLabel("快照名称", { exact: true }).fill("ACL 高级样本");
  await page.getByRole("button", { name: "提交初始化", exact: true }).click();
  const snapshot = page.getByRole("row").filter({ hasText: "ACL 高级样本" });
  await expect(snapshot.getByText(/^就绪/)).toBeVisible({ timeout: 90000 });
  await snapshot.getByRole("button", { name: "选择快照", exact: true }).click();

  await page.getByRole("link", { name: "ACL 流量测试", exact: true }).click();
  await page.getByRole("tab", { name: "条件搜索" }).click();
  await page.getByRole("combobox", { name: "设备范围" }).fill("c2");
  await page.getByRole("combobox", { name: "设备范围" }).press("Enter");
  await page.getByRole("combobox", { name: "ACL 范围" }).fill("WEB-SEARCH");
  await page.getByRole("combobox", { name: "ACL 范围" }).press("Enter");
  await page
    .getByRole("textbox", { name: "搜索源 IPv4 地址" })
    .fill("10.64.0.1");
  await page
    .getByRole("textbox", { name: "搜索目标 IPv4 地址" })
    .fill("10.64.0.2");
  await page
    .getByRole("tabpanel", { name: "条件搜索" })
    .getByRole("button", { name: /高级参数/ })
    .click();
  await page.getByRole("combobox", { name: "搜索 IP 协议" }).click();
  await page.getByText("TCP", { exact: true }).click();
  await page.getByRole("textbox", { name: "搜索源端口" }).fill("12345");
  await page.getByRole("textbox", { name: "搜索目标端口" }).fill("443");
  await page.getByRole("button", { name: "寻找示例流量" }).click();
  await expect(page.getByText("已完成", { exact: true })).toBeVisible({
    timeout: 90000,
  });
  await page.getByRole("button", { name: "查看分析结果" }).click();
  await expect(page.getByText(/找到所选范围内的示例流量/)).toBeVisible();
  await page.getByRole("button", { name: "查看证据" }).click();
  await expect(
    page.getByRole("dialog", { name: "搜索示例详情" }).getByText("12345"),
  ).toBeVisible();
  await page
    .getByRole("dialog", { name: "搜索示例详情" })
    .getByRole("button", { name: "关闭", exact: true })
    .click();
  await page.getByRole("button", { name: "用此 Flow 测试 ACL" }).click();
  await expect(page).toHaveURL(/\/acl$/);
  await expect(page.getByRole("textbox", { name: "源 IPv4 地址" })).toHaveValue(
    "10.64.0.1",
  );
  await expect(
    page.getByRole("textbox", { name: "目标 IPv4 地址" }),
  ).toHaveValue("10.64.0.2");
  await page
    .getByRole("tabpanel", { name: "流量测试" })
    .getByRole("button", { name: /高级参数/ })
    .click();
  await expect(page.getByRole("textbox", { name: "源端口" })).toHaveValue(
    "12345",
  );
  await expect(page.getByRole("textbox", { name: "目标端口" })).toHaveValue(
    "443",
  );
  await page.getByRole("button", { name: "测试 ACL 流量" }).click();
  await expect(page.getByText("已完成", { exact: true })).toBeVisible({
    timeout: 90000,
  });
  await page.getByRole("button", { name: "查看分析结果" }).click();
  await expect(
    page.getByText("ACL 局部放行", { exact: true }).first(),
  ).toBeVisible();

  await page.getByRole("link", { name: "ACL 流量测试", exact: true }).click();
  await page.getByRole("tab", { name: "规则诊断" }).click();
  await page.getByRole("combobox", { name: "设备范围" }).fill("c2");
  await page.getByRole("combobox", { name: "设备范围" }).press("Enter");
  await page.getByRole("combobox", { name: "ACL 范围" }).fill("WEB-SEARCH");
  await page.getByRole("combobox", { name: "ACL 范围" }).press("Enter");
  await page.getByRole("button", { name: "诊断不可达规则" }).click();
  await expect(page.getByText("已完成", { exact: true })).toBeVisible({
    timeout: 90000,
  });
  await page.getByRole("button", { name: "查看分析结果" }).click();
  await expect(page.getByText("被前序规则阻挡")).toBeVisible();
  await expect(page.getByText("匹配条件本身为空")).toBeVisible();
  for (const theme of ["深色主题", "浅色主题"]) {
    await page.getByRole("button", { name: theme, exact: true }).click();
    await page.screenshot({
      path: info.outputPath("acl-advanced-" + theme + ".png"),
      fullPage: true,
      animations: "disabled",
    });
  }
  await page
    .getByRole("row")
    .filter({ hasText: "匹配条件本身为空" })
    .getByRole("button", { name: "查看证据" })
    .click();
  const evidence = page.getByRole("dialog", { name: "规则诊断详情" });
  await expect(evidence.getByText("没有阻挡规则证据")).toBeVisible();
  await evidence.getByText("原始 SDK 证据").click();
  await expect(evidence.getByText(/INDEPENDENTLY_UNMATCHABLE/)).toBeVisible();
  expect(blockerWarnings).toEqual([]);
});
