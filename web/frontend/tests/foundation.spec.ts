import { loginAdmin } from "./auth-helpers";
import { test, expect } from "@playwright/test";
for (const width of [1280, 1920]) {
  test(`workbench and progressive controls at ${width}`, async ({
    page,
  }, testInfo) => {
    await page.setViewportSize({ width, height: 1000 });
    const errors: string[] = [];
    page.on("pageerror", (error) => errors.push(error.message));
    await loginAdmin(page);
    await expect(page.getByText("服务就绪")).toBeVisible();
    await expect(
      page.getByRole("heading", { name: "网络分析，从一份配置开始" }),
    ).toBeVisible();
    await page.screenshot({
      path: testInfo.outputPath(`overview-${width}.png`),
      fullPage: true,
    });
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth,
      ),
    ).toBe(true);
    await page.getByRole("link", { name: "Batfish 网络分析工作台" }).focus();
    await expect(
      page.getByRole("link", { name: "Batfish 网络分析工作台" }),
    ).toBeFocused();
    await page.goto("/tests/harness.html");
    await expect(
      page.getByText("华东区域核心网络与跨数据中心测试环境中文长名称"),
    ).toBeVisible();
    await page.getByRole("button", { name: /高级参数/ }).focus();
    await page.keyboard.press("Enter");
    await page.getByLabel("源地址", { exact: true }).fill("10.0.0.1");
    await page.getByRole("button", { name: /高级参数/ }).click();
    await expect(page.getByText("已生效 1 项")).toBeVisible();
    await page.getByRole("button", { name: /高级参数/ }).click();
    await expect(page.getByLabel("源地址", { exact: true })).toHaveValue(
      "10.0.0.1",
    );
    await expect(page.getByLabel("源地址", { exact: true })).toBeVisible();
    await page.screenshot({
      animations: "disabled",
      path: testInfo.outputPath(`components-${width}.png`),
      fullPage: true,
    });
    await page.getByRole("button", { name: "查看详情" }).click();
    await expect(page.getByText(/"source_ip": "10.0.0.1"/)).toBeVisible();
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth,
      ),
    ).toBe(true);
    await page.getByRole("button", { name: "关闭" }).click();
    await expect(page.getByRole("dialog")).toBeHidden();
    await page.evaluate(() => window.scrollTo(0, 700));
    expect(await page.evaluate(() => window.scrollY)).toBeGreaterThan(0);
    const header = await page.locator(".topbar").boundingBox();
    expect(header?.y).toBe(0);
    expect(errors).toEqual([]);
  });
}
