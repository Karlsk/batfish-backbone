import { randomUUID } from "node:crypto";
import { resolve } from "node:path";
import { readdirSync, readFileSync } from "node:fs";
import { test, expect, type Page } from "@playwright/test";
import { loginAdmin } from "./auth-helpers";
async function run(
  page: Page,
  node: string,
  destination: string,
  options?: { max?: number; ignore?: boolean; expert?: string; iface?: string },
) {
  await page.getByRole("link", { name: "网络分析", exact: true }).click();
  await page
    .getByRole("link", { name: "虚拟 traceroute", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "虚拟 traceroute", exact: true }),
  ).toBeVisible();
  if (options?.expert) {
    await page.getByRole("radio", { name: "专家表达式", exact: true }).check();
    await page
      .getByRole("textbox", { name: "起点表达式", exact: true })
      .fill(options.expert);
  } else {
    await page
      .getByRole("button", { name: "加载设备与接口候选", exact: true })
      .click();
    await expect(page.getByText(/已加载 .* 台设备的候选值/)).toBeVisible({
      timeout: 90000,
    });
    await page.getByRole("combobox", { name: "起点设备", exact: true }).click();
    await page.getByRole("option", { name: node, exact: true }).click();
    if (options?.iface) {
      await page
        .getByRole("combobox", { name: "起点接口", exact: true })
        .click();
      await page
        .getByRole("option", { name: options.iface, exact: true })
        .click();
    }
  }
  await page
    .getByRole("textbox", { name: "目标 IPv4 地址", exact: true })
    .fill(destination);
  if (options?.max || options?.ignore) {
    await page.getByText("高级参数", { exact: false }).first().click();
    if (options.max)
      await page
        .getByRole("spinbutton", { name: "最多路径数", exact: true })
        .fill(String(options.max));
    if (options.ignore)
      await page
        .getByRole("checkbox", { name: "忽略 ACL 过滤规则", exact: true })
        .check();
  }
  await page.getByRole("button", { name: "推演路径", exact: true }).click();
  await expect(page.getByText("已完成", { exact: true })).toBeVisible({
    timeout: 90000,
  });
  await page.getByRole("button", { name: "查看分析结果", exact: true }).click();
  await expect(
    page.getByText("单向配置模型推演；不是在线探测，也不证明回程连通。", {
      exact: true,
    }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Flow 0", exact: true }),
  ).toBeVisible();
}
for (const topology of ["small_network", "cisco_four"]) {
  test(`actual ${topology} virtual traces and path evidence`, async ({
    page,
  }, testInfo) => {
    test.setTimeout(300000);
    await page.setViewportSize({ width: 1280, height: 1000 });
    await loginAdmin(page);
    await page.getByRole("link", { name: "网络与快照", exact: true }).click();
    await page.getByRole("button", { name: "创建网络", exact: true }).click();
    const dialog = page.getByRole("dialog", { name: "创建网络" });
    const name = `路径-${topology}-${randomUUID().slice(0, 6)}`;
    await dialog.getByLabel("网络名称", { exact: true }).fill(name);
    await dialog.getByRole("button", { name: "创建", exact: true }).click();
    await expect(
      page.getByRole("heading", { name, exact: true }),
    ).toBeVisible();
    const folder = resolve(`../backend/tests/fixtures/${topology}/configs`);
    const files = readdirSync(folder).map((name) => {
      let source = readFileSync(resolve(folder, name), "utf8");
      if (topology === "cisco_four" && name === "c2.cfg")
        source = source.replace(
          "end",
          "ip access-list extended BLOCK-TRACE\n deny ip any host 10.64.0.4\n permit ip any any\n!\ninterface GigabitEthernet0/0\n ip access-group BLOCK-TRACE in\n!\nend",
        );
      return { name, mimeType: "text/plain", buffer: Buffer.from(source) };
    });
    await page.getByLabel("选择配置文件", { exact: true }).setInputFiles(files);
    await page.getByRole("button", { name: "上传并校验", exact: true }).click();
    await expect(page.getByText(/文件校验完成.*尚未初始化/)).toBeVisible();
    await page.getByLabel("快照名称", { exact: true }).fill("路径样本");
    await page.getByRole("button", { name: "提交初始化", exact: true }).click();
    const row = page.getByRole("row").filter({ hasText: "路径样本" });
    await expect(row.getByText(/^就绪/)).toBeVisible({ timeout: 90000 });
    await row.getByRole("button", { name: "选择快照", exact: true }).click();
    const node = topology === "small_network" ? "r1" : "c1",
      dst = topology === "small_network" ? "10.0.0.2" : "10.64.0.4";
    await run(page, node, dst, {
      iface: topology === "small_network" ? "LoopBack0" : "Loopback0",
    });
    await expect(
      page.getByRole("radio", { name: /路径 .*ACCEPTED/ }).first(),
    ).toBeVisible();
    if (topology === "cisco_four") {
      await expect(
        page.getByRole("radio", { name: /路径 .*DENIED_IN/ }),
      ).toBeVisible();
      await page.getByRole("radio", { name: /路径 .*DENIED_IN/ }).check();
      await expect(
        page.getByRole("heading", {
          name: "入方向 ACL 拒绝（DENIED_IN）",
          exact: true,
        }),
      ).toBeVisible();
    }
    await page
      .getByRole("button", { name: "路径原始详情", exact: true })
      .click();
    await expect(
      page.getByRole("dialog", { name: "路径原始详情" }),
    ).toBeVisible();
    await page
      .getByRole("dialog")
      .getByRole("button", { name: "关闭", exact: true })
      .click();
    await page.screenshot({
      path: testInfo.outputPath(`${topology}-trace.png`),
      fullPage: true,
      animations: "disabled",
    });
    await run(page, node, "203.0.113.254");
    await expect(
      page.getByRole("radio", { name: /路径 .*NO_ROUTE/ }).first(),
    ).toBeVisible();
    if (topology === "cisco_four") {
      await run(page, node, dst, { max: 1 });
      await expect(page.getByText(/路径未全部保存：/)).toBeVisible();
      await expect(page.getByText(/结果已截断：trace_limit/)).toBeVisible();
      await run(page, node, dst, { ignore: true, expert: "c1,c2" });
      await expect(
        page.getByText("本次推演忽略了 ACL 过滤规则。", { exact: true }),
      ).toBeVisible();
      expect(
        await page.getByRole("button", { name: /^Flow \d+$/ }).count(),
      ).toBeGreaterThan(1);
      await page.getByRole("button", { name: "Flow 1", exact: true }).click();
      await expect(
        page.getByText("Flow 1 · 路径证据", { exact: true }),
      ).toBeVisible();
      await page.screenshot({
        path: testInfo.outputPath("cisco-multi-flow.png"),
        fullPage: true,
        animations: "disabled",
      });
    }
  });
}
