import { test, expect } from "@playwright/test";
import { randomUUID } from "node:crypto";
import { readdirSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { loginAdmin } from "./auth-helpers";

test("phase two keeps one snapshot and clear model limits across workbenches", async ({
  page,
}) => {
  test.setTimeout(300000);
  await loginAdmin(page);
  await page.getByRole("link", { name: "网络与快照", exact: true }).click();
  await page.getByRole("button", { name: "创建网络", exact: true }).click();
  const network = `阶段二-${randomUUID().slice(0, 6)}`;
  const dialog = page.getByRole("dialog", { name: "创建网络" });
  await dialog.getByLabel("网络名称", { exact: true }).fill(network);
  await dialog.getByRole("button", { name: "创建", exact: true }).click();
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
  files.push({
    name: "isolated.cfg",
    mimeType: "text/plain",
    buffer: Buffer.from(
      "hostname isolated\ninterface Loopback0\n ip address 10.255.255.1 255.255.255.255\n!\n",
    ),
  });
  await page.getByLabel("选择配置文件", { exact: true }).setInputFiles(files);
  await page.getByRole("button", { name: "上传并校验", exact: true }).click();
  await expect(page.getByText(/文件校验完成.*尚未初始化/)).toBeVisible();
  await page.getByLabel("快照名称", { exact: true }).fill("阶段二样本");
  const createdResponse = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      /\/snapshots$/.test(new URL(response.url()).pathname),
  );
  await page.getByRole("button", { name: "提交初始化", exact: true }).click();
  const created = await (await createdResponse).json();
  const snapshot = page.getByRole("row").filter({ hasText: "阶段二样本" });
  await expect(snapshot.getByText(/^就绪/)).toBeVisible({ timeout: 90000 });
  await snapshot.getByRole("button", { name: "选择快照", exact: true }).click();

  await page.getByRole("link", { name: "网络拓扑", exact: true }).click();
  await page.getByRole("button", { name: "生成拓扑", exact: true }).click();
  await expect(page.getByText("已完成", { exact: true })).toBeVisible({
    timeout: 90000,
  });
  await page.getByRole("button", { name: "查看分析结果" }).click();
  await expect(
    page.getByText(`来源快照：${created.snapshot_id}`),
  ).toBeVisible();
  await page
    .getByRole("combobox", { name: "聚焦设备", exact: true })
    .fill("isolated");
  await page.getByRole("button", { name: "查看邻域", exact: true }).click();
  await expect(page.getByText(/isolated 的 1 跳邻域/)).toBeVisible();
  await expect(
    page.getByRole("button", { name: "设备详情 isolated" }),
  ).toBeVisible();

  await page.getByRole("link", { name: "BGP 会话", exact: true }).click();
  await page
    .getByRole("button", { name: "分析 BGP 会话", exact: true })
    .click();
  await expect(page.getByText("已完成", { exact: true })).toBeVisible({
    timeout: 90000,
  });
  await page.getByRole("button", { name: "查看分析结果" }).click();
  await expect(
    page.getByText(`来源快照：${created.snapshot_id}`),
  ).toBeVisible();
  await expect(
    page.getByText("NOT_COMPATIBLE", { exact: true }).first(),
  ).toBeVisible();
  await expect(
    page.getByText(/模型计算，非实时设备状态/).first(),
  ).toBeVisible();

  await page.getByRole("link", { name: "ACL 流量测试", exact: true }).click();
  await page.getByRole("button", { name: "加载设备与接口候选" }).click();
  await page.getByRole("combobox", { name: "设备", exact: true }).click();
  await page.getByRole("option", { name: "c2", exact: true }).click();
  await page.getByRole("button", { name: "加载此设备 ACL" }).click();
  await page.getByRole("combobox", { name: "ACL", exact: true }).click();
  await page.getByRole("option", { name: "WEB-TEST", exact: true }).click();
  await page.getByRole("textbox", { name: "源 IPv4 地址" }).fill("10.64.0.1");
  await page.getByRole("textbox", { name: "目标 IPv4 地址" }).fill("10.64.0.3");
  await page.getByRole("button", { name: "测试 ACL 流量" }).click();
  await expect(page.getByText("已完成", { exact: true })).toBeVisible({
    timeout: 90000,
  });
  await page.getByRole("button", { name: "查看分析结果" }).click();
  await expect(
    page.getByText(`来源快照：${created.snapshot_id}`),
  ).toBeVisible();
  await expect(
    page.getByText("隐式拒绝", { exact: true }).first(),
  ).toBeVisible();

  await page.getByRole("link", { name: "专家查询", exact: true }).click();
  await page.getByRole("combobox", { name: "专家能力" }).click();
  await page.getByRole("option", { name: /Devices · nodes/ }).click();
  await page.getByRole("button", { name: "运行专家查询" }).click();
  await expect(page.getByText("已完成", { exact: true })).toBeVisible({
    timeout: 90000,
  });
  await page.getByRole("button", { name: "查看分析结果" }).click();
  await expect(
    page.getByText(`来源快照：${created.snapshot_id}`),
  ).toBeVisible();
  await expect(
    page.getByText("isolated", { exact: true }).first(),
  ).toBeVisible();
});
