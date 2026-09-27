import { expect, test, type Page } from "@playwright/test";
import { randomUUID } from "node:crypto";
import { readdirSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { loginAdmin } from "./auth-helpers";

test("leader fixes baseline-to-candidate changes and gates fault impact on a ready derived snapshot", async ({
  page,
}: {
  page: Page;
}, testInfo) => {
  test.setTimeout(300000);
  await loginAdmin(page);
  await page.getByRole("link", { name: "网络与快照", exact: true }).click();
  await page.getByRole("button", { name: "创建网络", exact: true }).click();
  const dialog = page.getByRole("dialog", { name: "创建网络" });
  await dialog
    .getByLabel("网络名称", { exact: true })
    .fill(`领导变更-${randomUUID().slice(0, 6)}`);
  await dialog.getByRole("button", { name: "创建", exact: true }).click();
  const folder = resolve("../backend/tests/fixtures/cisco_four/configs");
  async function createSnapshot(name: string, candidate: boolean) {
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
    await page.getByLabel("快照名称", { exact: true }).fill(name);
    const response = page.waitForResponse(
      (item) =>
        item.request().method() === "POST" &&
        /\/snapshots$/.test(new URL(item.url()).pathname),
    );
    await page.getByRole("button", { name: "提交初始化", exact: true }).click();
    const id = (await (await response).json()).snapshot_id as string;
    const row = page.getByRole("row").filter({ hasText: name });
    await expect(row.getByText(/^就绪/)).toBeVisible({ timeout: 90000 });
    return { id, row };
  }
  const baseline = await createSnapshot("领导基线", false);
  await page.getByRole("button", { name: "创建另一份快照" }).click();
  const candidate = await createSnapshot("领导候选", true);
  await candidate.row.getByRole("button", { name: "选择快照" }).click();
  await page.getByRole("link", { name: "领导视图" }).click();
  await page.getByRole("link", { name: "变更与故障" }).click();
  await page.getByLabel("左侧基线快照").fill("领导基线");
  await page.getByLabel("左侧基线快照").press("Enter");
  await page.getByLabel("右侧候选快照").fill("领导候选");
  await page.getByLabel("右侧候选快照").press("Enter");
  await expect(page.getByText(/基线（左） → 候选（右）/)).toBeVisible();
  await page.getByRole("button", { name: "创建固定比较" }).click();
  await expect(page.getByText(baseline.id)).toBeVisible();
  await expect(page.getByText(candidate.id)).toBeVisible();
  await page.screenshot({
    path: testInfo.outputPath("leader-fixed-comparison.png"),
    fullPage: true,
    animations: "disabled",
  });
  await page.getByRole("button", { name: "开始比较检查" }).click();
  await expect(page.getByText(/已发现 1 个配置文件变化/)).toBeVisible({
    timeout: 90000,
  });
  await expect(page.getByText("configs/c1.cfg")).toBeVisible();
  await expect(page.getByText(/配置文本变化不等于网络行为变化/)).toBeVisible();
  await page.goBack();
  await page.getByRole("button", { name: /路由变化/ }).click();
  await page.getByLabel("要比较的 IPv4 网段").fill("198.51.100.0/24");
  await page.getByRole("button", { name: "开始比较检查" }).click();
  await expect(page.getByText(/模型路由变化/).first()).toBeVisible({
    timeout: 90000,
  });
  await expect(page.getByText(/只检查明确网段/)).toBeVisible();
  await page.goBack();
  await page.getByRole("button", { name: /可达性变化/ }).click();
  await page.getByLabel("变更流量起点").fill("c1");
  await page.getByLabel("变更流量目的").fill("10.64.0.4");
  await page.getByRole("button", { name: "开始比较检查" }).click();
  await expect(page.getByText(/可达性变化样本/).first()).toBeVisible({
    timeout: 90000,
  });
  await expect(page.getByText(/不能推断全部业务影响/)).toBeVisible();

  await page.getByRole("link", { name: "变更与故障" }).click();
  await page.getByRole("link", { name: /模拟设备或接口故障/ }).click();
  await page.getByLabel("故障基线快照").fill("领导基线");
  await page.getByLabel("故障基线快照").press("Enter");
  await page.getByRole("button", { name: "加载设备与接口候选" }).click();
  await expect(page.getByText(/已加载 4 台设备的候选值/)).toBeVisible({
    timeout: 90000,
  });
  await page.getByLabel("故障停用设备").click();
  await page.getByRole("option", { name: "c2", exact: true }).click();
  await page.getByLabel("故障方案名称").fill("领导 c2 故障");
  await expect(page.getByText(/原始基线.*保持不变/)).toBeVisible();
  await page.getByRole("button", { name: "创建派生快照" }).click();
  await expect(
    page.getByRole("link", { name: /使用原始基线与派生快照创建固定比较/ }),
  ).toBeVisible({ timeout: 120000 });
  const faultRunUrl = page.url();
  await page.screenshot({
    path: testInfo.outputPath("leader-derived-ready.png"),
    fullPage: true,
    animations: "disabled",
  });
  const link = page.getByRole("link", {
    name: /使用原始基线与派生快照创建固定比较/,
  });
  const destination = new URL((await link.getAttribute("href"))!, page.url());
  const derivedId = destination.searchParams.get("candidate")!;
  const networkId = destination.searchParams.get("network")!;
  await link.click();
  await expect(page).toHaveURL(
    new RegExp(`baseline=${baseline.id}.*candidate=`),
  );
  await expect(
    page.getByRole("button", { name: "创建固定比较" }),
  ).toBeEnabled();
  await page.getByRole("button", { name: "创建固定比较" }).click();
  await expect(page.getByText(baseline.id)).toBeVisible();
  await page.route(
    `**/api/v1/networks/${networkId}/snapshots/${derivedId}`,
    async (route) => {
      const response = await route.fetch();
      await route.fulfill({
        response,
        json: { ...(await response.json()), status: "failed" },
      });
    },
  );
  await page.goto(faultRunUrl);
  await expect(page.getByText("派生初始化失败，不能进入比较。")).toBeVisible();
  await expect(
    page.getByRole("link", { name: /使用原始基线与派生快照创建固定比较/ }),
  ).toHaveCount(0);
});
