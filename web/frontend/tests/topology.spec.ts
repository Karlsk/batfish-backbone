import { test, expect } from "@playwright/test";
import { randomUUID } from "node:crypto";
import { readdirSync } from "node:fs";
import { resolve } from "node:path";
import { loginAdmin } from "./auth-helpers";
for (const fixture of ["small_network", "cisco_four"]) {
  test(`actual ${fixture} topology focus, interfaces, model view and route context`, async ({
    page,
  }, info) => {
    test.setTimeout(180000);
    await page.setViewportSize({ width: 1440, height: 1000 });
    await loginAdmin(page);
    await page.getByRole("link", { name: "网络与快照", exact: true }).click();
    await page.getByRole("button", { name: "创建网络", exact: true }).click();
    const dialog = page.getByRole("dialog", { name: "创建网络" }),
      name = `拓扑-${fixture}-${randomUUID().slice(0, 6)}`;
    await dialog.getByLabel("网络名称", { exact: true }).fill(name);
    await dialog.getByRole("button", { name: "创建", exact: true }).click();
    await expect(
      page.getByRole("heading", { name, exact: true }),
    ).toBeVisible();
    const folder = resolve(`../backend/tests/fixtures/${fixture}/configs`);
    await page
      .getByLabel("选择配置文件", { exact: true })
      .setInputFiles(readdirSync(folder).map((n) => resolve(folder, n)));
    await page.getByRole("button", { name: "上传并校验", exact: true }).click();
    await expect(page.getByText(/文件校验完成.*尚未初始化/)).toBeVisible();
    await page.getByLabel("快照名称", { exact: true }).fill("拓扑样本");
    const createdResponse = page.waitForResponse(
      (r) =>
        r.request().method() === "POST" &&
        /\/snapshots$/.test(new URL(r.url()).pathname),
    );
    await page.getByRole("button", { name: "提交初始化", exact: true }).click();
    const created = await (await createdResponse).json();
    const row = page.getByRole("row").filter({ hasText: "拓扑样本" });
    await expect(row.getByText(/^就绪/)).toBeVisible({ timeout: 90000 });
    await row.getByRole("button", { name: "选择快照", exact: true }).click();
    await page.getByRole("link", { name: "网络拓扑", exact: true }).click();
    await page.getByRole("button", { name: "生成拓扑", exact: true }).click();
    await expect(page.getByText("已完成", { exact: true })).toBeVisible({
      timeout: 90000,
    });
    await page
      .getByRole("button", { name: "查看分析结果", exact: true })
      .click();
    const node = fixture === "small_network" ? "r1" : "c1",
      other = fixture === "small_network" ? "r2" : "c4";
    await expect(
      page.getByText(new RegExp(`${node} 的 1 跳邻域`)),
    ).toBeVisible();
    await expect(page.locator(".topology-canvas canvas").first()).toBeVisible();
    await expect(
      page.getByText(`来源快照：${created.snapshot_id}`, { exact: true }),
    ).toBeVisible();
    for (const theme of ["深色主题", "浅色主题"]) {
      await page.getByRole("button", { name: theme, exact: true }).click();
      await expect(
        page.locator(".topology-canvas canvas").first(),
      ).toBeVisible();
      await page.screenshot({
        path: info.outputPath(`${fixture}-${theme}.png`),
        fullPage: true,
      });
    }
    await page
      .getByRole("button", { name: new RegExp(`^关系详情 ${node} `) })
      .first()
      .click();
    await expect(
      page.getByRole("dialog", { name: "关系与接口证据" }),
    ).toBeVisible();
    await page.getByRole("button", { name: "关闭", exact: true }).click();
    await page
      .getByRole("combobox", { name: "聚焦设备", exact: true })
      .fill(other);
    await page.getByRole("button", { name: "查看邻域", exact: true }).click();
    await expect(
      page.getByText(new RegExp(`${other} 的 1 跳邻域`)),
    ).toBeVisible();
    const resultUrl = page.url();
    await page.reload();
    await expect(
      page.getByRole("button", { name: `设备详情 ${node}`, exact: true }),
    ).toBeVisible();
    await page
      .getByRole("button", { name: `设备详情 ${node}`, exact: true })
      .focus();
    await page.keyboard.press("Enter");
    await page
      .getByRole("button", { name: "查询该设备路由", exact: true })
      .click();
    await expect(page).toHaveURL(/\/analysis\/routes$/);
    await expect(
      page
        .locator(".selector-field .ant-select-selection-item")
        .filter({ hasText: node }),
    ).toBeVisible();
    await page.getByRole("button", { name: "执行查询", exact: true }).click();
    await expect(page.getByText("已完成", { exact: true })).toBeVisible({
      timeout: 90000,
    });
    await page
      .getByRole("button", { name: "查看分析结果", exact: true })
      .click();
    await expect(
      page.getByText(`来源快照：${created.snapshot_id}`, { exact: true }),
    ).toBeVisible();
    await page.goto(resultUrl);
    await page.getByText("切换关系视图或计算筛选条件", { exact: true }).click();
    await page.getByRole("combobox", { name: "关系视图", exact: true }).click();
    await page.getByRole("option", { name: "BGP 关系", exact: true }).click();
    await page.getByRole("button", { name: "生成拓扑", exact: true }).click();
    await expect(page.getByText("已完成", { exact: true })).toBeVisible({
      timeout: 90000,
    });
    await page
      .getByRole("button", { name: "查看分析结果", exact: true })
      .click();
    await expect(
      page.getByText(
        "此范围没有该类型关系，已保留孤立设备；缺少边不能证明物理断线。",
        { exact: true },
      ),
    ).toBeVisible();
    await expect(
      page.getByRole("button", { name: `设备详情 ${node}`, exact: true }),
    ).toBeVisible();
  });
}
