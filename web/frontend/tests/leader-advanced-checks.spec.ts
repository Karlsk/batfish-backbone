import { expect, test, type Page } from "@playwright/test";
import { randomUUID } from "node:crypto";
import { readdirSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { loginAdmin } from "./auth-helpers";

async function selectCisco(page: Page) {
  const response = await page.request.get("/api/v1/leader/overview?limit=200");
  expect(response.ok()).toBe(true);
  const card = (await response.json()).items.find(
    (item: { latest_ready_snapshot?: { display_name: string } }) =>
      item.latest_ready_snapshot?.display_name === "cisco_four",
  );
  expect(card).toBeTruthy();
  await page.getByLabel("检查网络").click();
  await page
    .locator('.ant-select-dropdown:visible [role="option"]')
    .filter({ hasText: card.network_id.slice(0, 8) })
    .click();
  await page.getByLabel("配置快照").click();
  await page
    .locator('.ant-select-dropdown:visible [role="option"]')
    .filter({ hasText: card.latest_ready_snapshot.id.slice(0, 8) })
    .click();
}

test("leader sees registered ADV checks and a focused saved topology", async ({
  page,
}, testInfo) => {
  test.setTimeout(120000);
  await loginAdmin(page);
  await page.goto("/leader/checks");
  await selectCisco(page);
  await expect(page.getByRole("button", { name: /网络拓扑/ })).toBeVisible();
  await expect(page.getByRole("button", { name: /BGP 会话/ })).toBeVisible();
  await expect(
    page.getByRole("button", { name: /ACL 流量检查/ }),
  ).toBeVisible();
  await page.getByRole("button", { name: /网络拓扑/ }).click();
  await page.getByRole("button", { name: "开始检查" }).click();
  await expect(page.getByText(/已保存 4 台设备/)).toBeVisible({
    timeout: 90000,
  });
  await expect(page.getByText(/不能证明物理链路/)).toBeVisible();
  await expect(page.getByLabel("配置模型关系图")).toBeVisible();
  await page.getByLabel("聚焦设备").click();
  await page.getByRole("option", { name: "c1" }).click();
  await expect(page.getByText(/c1.*跳/)).toBeVisible();
  await page.screenshot({
    path: testInfo.outputPath("leader-topology.png"),
    fullPage: true,
    animations: "disabled",
  });
});

test("BGP empty model evidence stays distinct from live health and expert list is registered", async ({
  page,
}) => {
  test.setTimeout(120000);
  await loginAdmin(page);
  await page.goto("/leader/checks");
  await selectCisco(page);
  await expect(page.getByText("更多专家能力")).toBeVisible();
  await expect(page.getByText("test-filters")).toBeVisible();
  await page.getByRole("button", { name: /BGP 会话/ }).click();
  await page.getByRole("button", { name: "开始检查" }).click();
  await expect(page.getByText(/BGP 模型会话/).first()).toBeVisible({
    timeout: 90000,
  });
  await expect(page.getByText(/不代表设备实时会话健康/)).toBeVisible();
  await expect(
    page.getByRole("link", { name: /查看完整结果与导出/ }),
  ).toBeVisible();
});

test("ACL requires explicit flow and filter before a run", async ({ page }) => {
  await loginAdmin(page);
  await page.goto("/leader/checks");
  await selectCisco(page);
  await page.getByRole("button", { name: /ACL 流量检查/ }).click();
  await page.getByRole("button", { name: "开始检查" }).click();
  await expect(page.getByText("请填写流量源地址")).toBeVisible();
  await page.getByLabel("流量源地址").fill("10.64.0.1");
  await page.getByLabel("流量目的地址").fill("10.64.0.4");
  await page.getByRole("button", { name: "开始检查" }).click();
  await expect(page.getByText("请填写要检查的 ACL 名称")).toBeVisible();
});

test("leader reads real BGP mismatch and all three ACL decisions from one synthetic Cisco snapshot", async ({
  page,
}) => {
  test.setTimeout(300000);
  await loginAdmin(page);
  await page.getByRole("link", { name: "网络与快照", exact: true }).click();
  await page.getByRole("button", { name: "创建网络", exact: true }).click();
  const dialog = page.getByRole("dialog", { name: "创建网络" });
  await dialog
    .getByLabel("网络名称", { exact: true })
    .fill(`领导ADV-${randomUUID().slice(0, 6)}`);
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
  await page.getByLabel("选择配置文件", { exact: true }).setInputFiles(files);
  await page.getByRole("button", { name: "上传并校验", exact: true }).click();
  await expect(page.getByText(/文件校验完成.*尚未初始化/)).toBeVisible();
  const snapshotName = `领导ADV快照-${randomUUID().slice(0, 6)}`;
  await page.getByLabel("快照名称", { exact: true }).fill(snapshotName);
  const createdResponse = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      /\/snapshots$/.test(new URL(response.url()).pathname),
  );
  await page.getByRole("button", { name: "提交初始化", exact: true }).click();
  const snapshotId = (await (await createdResponse).json()).snapshot_id;
  expect(snapshotId).toMatch(/^[0-9a-f-]{36}$/);
  const row = page.getByRole("row").filter({ hasText: snapshotName });
  await expect(row.getByText(/^就绪/)).toBeVisible({ timeout: 90000 });
  await row.getByRole("button", { name: "选择快照", exact: true }).click();
  await page.getByRole("link", { name: "领导视图" }).click();
  await page.getByRole("link", { name: "自主检查" }).click();
  await expect(page.getByText(snapshotName, { exact: true })).toBeVisible();

  async function openCheck(template: string) {
    if (!page.url().endsWith("/leader/checks"))
      await page.getByRole("link", { name: "返回自主检查" }).click();
    await expect(page.getByText(snapshotName, { exact: true })).toBeVisible();
    await page.getByRole("button", { name: new RegExp(template) }).click();
  }

  await openCheck("BGP 会话");
  await page.getByRole("button", { name: "开始检查" }).click();
  await expect(page.getByText("NOT_COMPATIBLE").first()).toBeVisible({
    timeout: 90000,
  });
  await expect(page.getByText(/不代表设备实时会话健康/)).toBeVisible();

  for (const [destination, conclusion] of [
    ["10.64.0.2", /ACL 局部放行/],
    ["10.64.0.4", /ACL 拒绝/],
    ["10.64.0.3", /隐式拒绝/],
  ] as const) {
    await openCheck("ACL 流量检查");
    await page.getByLabel("流量源地址").fill("10.64.0.1");
    await page.getByLabel("流量目的地址").fill(destination);
    await page.getByLabel("要检查的 ACL 名称").fill("WEB-TEST");
    await page.getByRole("button", { name: "开始检查" }).click();
    await expect(page.getByRole("heading", { name: conclusion })).toBeVisible({
      timeout: 90000,
    });
    await expect(page.getByText(/不代表端到端可达/)).toBeVisible();
  }
});
