import { test, expect } from "@playwright/test";
import { loginAdmin } from "./auth-helpers";

test("theme persists and system preference resumes without losing login input", async ({
  page,
}) => {
  await page.emulateMedia({ colorScheme: "dark" });
  await page.goto("/");
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await page.getByLabel("用户名", { exact: true }).fill("appearance-draft");
  await page.getByRole("button", { name: "浅色主题" }).click();
  await expect(page.getByLabel("用户名", { exact: true })).toHaveValue(
    "appearance-draft",
  );
  await page.reload();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  await page.getByRole("button", { name: "跟随系统" }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await page.emulateMedia({ colorScheme: "light" });
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
});

test("pre-app background respects saved dark mode before the bundle loads", async ({
  page,
}) => {
  await page.addInitScript(() =>
    localStorage.setItem("batfish-theme-preference", "dark"),
  );
  await page.route("**/src/main.tsx*", (route) => route.abort());
  await page.goto("/");
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await expect(page.locator("html")).toHaveCSS(
    "background-color",
    "rgb(10, 17, 30)",
  );
  await expect(page.locator("#root")).toBeEmpty();
});

test("blocked storage still allows theme changes", async ({ page }) => {
  await page.addInitScript(() => {
    Storage.prototype.getItem = () => {
      throw new Error("storage disabled");
    };
    Storage.prototype.setItem = () => {
      throw new Error("storage disabled");
    };
  });
  await page.goto("/");
  await page.getByRole("button", { name: "深色主题" }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await expect(page.getByRole("heading", { name: "登录工作台" })).toBeVisible();
});

test("workspace forms and portal surfaces follow both themes", async ({
  page,
}, info) => {
  await loginAdmin(page);
  await page.goto("/tests/harness.html");
  await page.getByRole("button", { name: /高级参数/ }).click();
  await page.getByLabel("源地址", { exact: true }).fill("10.0.0.1");
  for (const [label, mode, background] of [
    ["深色主题", "dark", "rgb(25, 39, 59)"],
    ["浅色主题", "light", "rgb(246, 248, 252)"],
  ] as const) {
    await page.getByRole("button", { name: label }).click();
    await expect(page.locator("html")).toHaveAttribute("data-theme", mode);
    await expect(page.getByLabel("源地址", { exact: true })).toHaveValue(
      "10.0.0.1",
    );
    await expect(
      page.getByText("华东区域核心网络与跨数据中心测试环境中文长名称"),
    ).toBeVisible();
    await page.getByRole("button", { name: "查看详情" }).click();
    await expect(page.getByRole("dialog")).toHaveCSS(
      "background-color",
      background,
    );
    await expect(page.getByText(/"source_ip": "10.0.0.1"/)).toBeVisible();
    await page.screenshot({
      path: info.outputPath(`drawer-${mode}.png`),
      animations: "disabled",
    });
    await page.getByRole("button", { name: "关闭" }).click();
  }
  for (const width of [1440, 768, 390]) {
    await page.setViewportSize({ width, height: 1000 });
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
  }
});
