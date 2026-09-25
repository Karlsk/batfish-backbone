import { randomUUID } from "node:crypto";
import { spawn } from "node:child_process";
import { resolve } from "node:path";
import { test, expect } from "@playwright/test";
import { loginAdmin } from "./auth-helpers";

async function pauseWorker() {
  const child = spawn(
    "../backend/.venv/bin/python",
    ["tests/pause-worker.py"],
    { stdio: ["pipe", "pipe", "pipe"] },
  );
  const exited = new Promise<void>((resolve, reject) => {
    child.once("error", reject);
    child.once("exit", (code) =>
      code === 0
        ? resolve()
        : reject(new Error(`Worker pause helper exited ${code}`)),
    );
  });
  await new Promise<void>((resolve, reject) => {
    const timer = setTimeout(() => {
      child.stdin.end();
      reject(new Error("Worker pause timeout"));
    }, 55000);
    child.stdout.on("data", (chunk) => {
      if (String(chunk).includes("READY")) {
        clearTimeout(timer);
        resolve();
      }
    });
    exited.then(() => {
      clearTimeout(timer);
      reject(new Error("Pause ended before acknowledgment"));
    }, reject);
  });
  return async () => {
    child.stdin.end("resume\n");
    await exited;
  };
}

test("queued cancellation and immutable initialization retry in real worker", async ({
  page,
}, testInfo) => {
  test.setTimeout(180000);
  await loginAdmin(page);
  await page.getByRole("link", { name: "网络与快照", exact: true }).click();
  await page.getByRole("button", { name: "创建网络", exact: true }).click();
  const dialog = page.getByRole("dialog", { name: "创建网络" });
  const name = `重试-${randomUUID().slice(0, 6)}`;
  await dialog.getByLabel("网络名称", { exact: true }).fill(name);
  await dialog.getByRole("button", { name: "创建", exact: true }).click();
  await expect(page.getByRole("heading", { name, exact: true })).toBeVisible();
  await page
    .getByLabel("选择配置文件", { exact: true })
    .setInputFiles(
      ["r1.cfg", "r2.cfg"].map((n) =>
        resolve("../backend/tests/fixtures/small_network/configs", n),
      ),
    );
  await page.getByRole("button", { name: "上传并校验" }).click();
  await expect(page.getByText(/文件校验完成.*尚未初始化/)).toBeVisible();
  await page.getByLabel("快照名称", { exact: true }).fill("排队取消后重试");
  const resume = await pauseWorker();
  let oldUrl = "";
  try {
    await page.getByRole("button", { name: "提交初始化", exact: true }).click();
    await page.getByRole("link", { name: "查看初始化任务" }).click();
    oldUrl = page.url();
    await page.getByRole("button", { name: "取消排队", exact: true }).click();
    await expect(
      page.getByText("已取消", { exact: true }).first(),
    ).toBeVisible();
    await page
      .getByRole("button", { name: "新建重试任务", exact: true })
      .click();
    await expect(
      page.getByText("这是一个新建的重试任务，旧快照状态保持不变"),
    ).toBeVisible();
    expect(page.url()).not.toBe(oldUrl);
    await expect(page.getByText(/^旧快照：/)).not.toContainText("读取中");
    const oldSnapshot = await page.getByText(/^旧快照：/).textContent();
    const newSnapshot = await page.getByText(/^新快照：/).textContent();
    for (const value of [oldSnapshot, newSnapshot])
      expect(value?.split("：")[1]?.trim()).toMatch(
        /^[0-9a-f]{8}-[0-9a-f-]{27}$/,
      );
    expect(oldSnapshot?.split("：")[1]).not.toBe(newSnapshot?.split("：")[1]);
    await page.screenshot({
      path: testInfo.outputPath("immutable-retry.png"),
      fullPage: true,
    });
  } finally {
    await resume();
  }
  await expect(page.getByText("已完成", { exact: true })).toBeVisible({
    timeout: 90000,
  });
  await page.getByRole("link", { name: "查看旧任务", exact: true }).click();
  expect(page.url()).toBe(oldUrl);
  await expect(page.getByText("已取消", { exact: true }).first()).toBeVisible();
  await page.getByRole("button", { name: "全部任务", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "任务中心", exact: true }),
  ).toBeVisible();
  await page.getByRole("checkbox", { name: "仅当前网络", exact: true }).check();
  await expect(page.getByRole("link", { name: /^初始化 ·/ })).toHaveCount(2);
});
