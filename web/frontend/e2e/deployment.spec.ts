import { readFileSync } from "node:fs";
import { test, expect } from "@playwright/test";
import { login } from "../tests/auth-helpers";

test("dark controls preserve readable hover, active and checked states", async ({
  page,
}) => {
  const report = JSON.parse(
    readFileSync(process.env.BFW_DEPLOYMENT_EVIDENCE!, "utf8"),
  );
  const credentials = JSON.parse(
    readFileSync(`${report.state.state_dir}/auth.json`, "utf8"),
  );
  await login(page, credentials.username, credentials.password);
  await expect(
    page.getByRole("heading", { name: "网络分析，从一份配置开始" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "深色主题" }).click();
  await page.getByRole("link", { name: "任务中心", exact: true }).click();
  const button = page.getByRole("button", { name: "刷新", exact: true });
  const contrast = (colors: string[]) => {
    const values = colors
      .map((color) => {
        const rgb = color
          .match(/[\d.]+/g)!
          .slice(0, 3)
          .map(Number)
          .map((v) => v / 255)
          .map((v) =>
            v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4,
          );
        return rgb[0] * 0.2126 + rgb[1] * 0.7152 + rgb[2] * 0.0722;
      })
      .sort((a, b) => a - b);
    return (values[1] + 0.05) / (values[0] + 0.05);
  };
  await page.emulateMedia({ reducedMotion: "reduce" });
  const soft = expect.configure({ soft: true });
  await button.hover();
  await button.evaluate(async (el) => {
    await Promise.all(el.getAnimations().map((a) => a.finished));
  });
  await soft
    .poll(async () =>
      contrast(
        await button.evaluate((el) => [
          getComputedStyle(el).color,
          getComputedStyle(document.body).backgroundColor,
        ]),
      ),
    )
    .toBeGreaterThanOrEqual(4.5);
  await page.mouse.down();
  await button.evaluate(async (el) => {
    await Promise.all(el.getAnimations().map((a) => a.finished));
  });
  try {
    await soft
      .poll(async () =>
        contrast(
          await button.evaluate((el) => [
            getComputedStyle(el).color,
            getComputedStyle(document.querySelector(".ant-card")!)
              .backgroundColor,
          ]),
        ),
      )
      .toBeGreaterThanOrEqual(4.5);
  } finally {
    await page.mouse.up();
  }
  await page.getByRole("checkbox", { name: "仅我发起" }).check();
  const check = page.locator(".ant-checkbox-checked").first();
  await soft
    .poll(async () =>
      contrast(
        await check.evaluate((el) => [
          getComputedStyle(el, "::after").borderRightColor,
          getComputedStyle(el).backgroundColor,
        ]),
      ),
    )
    .toBeGreaterThanOrEqual(3);
});

test("restored HTTPS production bundle retains results and role controls", async ({
  page,
}, info) => {
  const evidence = process.env.BFW_DEPLOYMENT_EVIDENCE;
  if (!evidence)
    throw new Error(
      "BFW_DEPLOYMENT_EVIDENCE must identify the completed deployment verification",
    );
  const report = JSON.parse(readFileSync(evidence, "utf8"));
  expect(report.status).toBe("passed");
  const credentials = JSON.parse(
    readFileSync(`${report.state.state_dir}/auth.json`, "utf8"),
  );
  await login(page, credentials.username, credentials.password);
  await expect(
    page.getByRole("heading", { name: "网络分析，从一份配置开始" }),
  ).toBeVisible();
  await expect(page.getByText("服务就绪", { exact: true })).toBeVisible({
    timeout: 60000,
  });
  const mode = info.project.use.colorScheme === "dark" ? "dark" : "light";
  await expect(page.locator("html")).toHaveAttribute("data-theme", mode);
  const opposite = mode === "dark" ? "light" : "dark";
  await page
    .getByRole("button", {
      name: opposite === "dark" ? "深色主题" : "浅色主题",
    })
    .click();
  await page.reload();
  await expect(page.locator("html")).toHaveAttribute("data-theme", opposite);
  await page.getByRole("button", { name: "跟随系统" }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", mode);
  for (const sample of report.samples) {
    await page.goto(`/results/${sample.result_id}`);
    await expect(
      page.getByRole("heading", { name: "分析结果", exact: true }),
    ).toBeVisible();
    await expect(
      page.getByText(`来源快照：${sample.snapshot_id}`, { exact: true }),
    ).toBeVisible();
    await expect(
      page
        .getByRole("cell", {
          name: sample.fixture === "small_network" ? "r1" : "c1",
          exact: true,
        })
        .first(),
    ).toBeVisible();
    await page.reload();
    await expect(
      page.getByRole("button", { name: "下载 JSON", exact: true }),
    ).toBeVisible();
  }
  await page.getByRole("button", { name: "有效参数与来源" }).click();
  await expect(page.getByRole("dialog")).toHaveCSS(
    "background-color",
    mode === "dark" ? "rgb(25, 39, 59)" : "rgb(246, 248, 252)",
  );
  await expect(page.locator(".raw-detail")).toContainText(
    "effective_parameters",
  );
  await page.screenshot({
    path: info.outputPath("https-result-drawer.png"),
    animations: "disabled",
  });
  await page.getByRole("button", { name: "关闭", exact: true }).click();
  await expect(page.getByRole("dialog")).toBeHidden();
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({
    path: info.outputPath("https-restored-result.png"),
    animations: "disabled",
  });
  await page.getByRole("link", { name: "网络与快照", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "删除网络", exact: true }).first(),
  ).toBeVisible();
  await page.getByRole("button", { name: "退出登录", exact: true }).click();
  await expect(page.getByRole("heading", { name: "登录工作台" })).toBeVisible();
});

test("production first paint applies preference before any app bundle", async ({
  page,
}) => {
  await page.addInitScript(() =>
    localStorage.setItem("batfish-theme-preference", "dark"),
  );
  await page.route(/\/assets\/.*\.js(?:\?.*)?$/, (route) => route.abort());
  await page.goto("/");
  await expect(page.locator("#root")).toBeEmpty();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await expect(page.locator("html")).toHaveCSS(
    "background-color",
    "rgb(10, 17, 30)",
  );
});
