import { readFileSync } from "node:fs";
import { test, expect } from "@playwright/test";
import { login } from "../tests/auth-helpers";

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
