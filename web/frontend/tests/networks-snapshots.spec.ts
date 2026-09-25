import { randomUUID } from "node:crypto";
import { execFileSync } from "node:child_process";
import { resolve } from "node:path";
import { test, expect, type Page } from "@playwright/test";
import { loginAdmin } from "./auth-helpers";
async function createNetwork(page: Page, name: string) {
  await page.getByRole("link", { name: "网络与快照", exact: true }).click();
  await page.getByRole("button", { name: "创建网络", exact: true }).click();
  const dialog = page.getByRole("dialog", { name: "创建网络" });
  await dialog.getByLabel("网络名称", { exact: true }).fill(name);
  await dialog.getByRole("button", { name: "创建", exact: true }).click();
  await expect(page.getByRole("heading", { name, exact: true })).toBeVisible();
}
for (const topology of ["small_network", "cisco_four"]) {
  test(`actual ${topology} upload initialization and context isolation`, async ({
    page,
  }, testInfo) => {
    test.setTimeout(120000);
    await page.setViewportSize({ width: 1280, height: 1000 });
    await loginAdmin(page);
    const networkName = `拓扑-${topology}-${randomUUID().slice(0, 6)}`;
    await createNetwork(page, networkName);
    await expect(page.getByText(/服务端限额/)).toBeVisible();
    let submissions = 0;
    page.on("request", (request) => {
      if (
        request.method() === "POST" &&
        /\/snapshots$/.test(new URL(request.url()).pathname)
      )
        submissions++;
    });
    if (topology === "small_network") {
      await page.getByRole("radio", { name: "ZIP压缩包" }).check();
      await page.getByLabel("选择ZIP文件", { exact: true }).setInputFiles({
        name: "invalid.zip",
        mimeType: "application/octet-stream",
        buffer: Buffer.from([0, 0, 0]),
      });
      await page.getByRole("button", { name: "上传并校验" }).click();
      await expect(page.getByText("请检查填写的参数。")).toBeVisible();
      expect(submissions).toBe(0);
      await expect(
        page.getByRole("heading", { name: networkName, exact: true }),
      ).toBeVisible();
      await page.getByRole("radio", { name: "配置文件", exact: true }).check();
      await page
        .getByLabel("选择配置文件", { exact: true })
        .setInputFiles(
          ["r1.cfg", "r2.cfg"].map((name) =>
            resolve("../backend/tests/fixtures/small_network/configs", name),
          ),
        );
    } else {
      await page.getByRole("radio", { name: "ZIP压缩包" }).check();
      const zip = testInfo.outputPath("cisco-four.zip");
      execFileSync("../backend/.venv/bin/python", [
        "-c",
        "import pathlib,sys,zipfile\nroot=pathlib.Path(sys.argv[1])\nwith zipfile.ZipFile(sys.argv[2],'w') as archive:\n for path in sorted(root.glob('configs/*')): archive.write(path,path.relative_to(root))",
        resolve("../backend/tests/fixtures/cisco_four"),
        zip,
      ]);
      await page.getByLabel("选择ZIP文件", { exact: true }).setInputFiles(zip);
    }
    await page.getByRole("button", { name: "上传并校验" }).click();
    await expect(page.getByText(/文件校验完成.*尚未初始化/)).toBeVisible();
    expect(submissions).toBe(0);
    const snapshotName = `快照-${topology}`;
    await page.getByLabel("快照名称", { exact: true }).fill(snapshotName);
    await page
      .getByRole("button", { name: "返回网络列表", exact: true })
      .click();
    await expect(
      page.getByRole("dialog", { name: "放弃未完成的快照向导？", exact: true }),
    ).toBeVisible();
    await page.getByRole("button", { name: "继续填写", exact: true }).click();
    await expect(
      page.getByRole("dialog", { name: "放弃未完成的快照向导？", exact: true }),
    ).toBeHidden();
    await expect(page.getByLabel("快照名称", { exact: true })).toHaveValue(
      snapshotName,
    );

    await page
      .getByRole("button", { name: "提交初始化", exact: true })
      .dblclick();
    await expect(
      page.getByText("初始化任务已提交", { exact: true }),
    ).toBeVisible();
    expect(submissions).toBe(1);
    const row = page.getByRole("row").filter({ hasText: snapshotName });
    await expect(row.getByText(/^就绪/)).toBeVisible({ timeout: 90000 });
    await row.getByRole("button", { name: "选择快照" }).click();
    await expect(row.getByRole("button", { name: "当前快照" })).toBeVisible();
    await page.screenshot({
      path: testInfo.outputPath(`${topology}-ready.png`),
      fullPage: true,
    });
    await page.getByRole("link", { name: "查看初始化任务" }).click();
    await expect(page.getByText("已完成", { exact: true })).toBeVisible();
    await page.reload();
    await expect(page.getByText("已完成", { exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: "取消排队" })).toHaveCount(0);
    await page.getByRole("button", { name: "查看解析诊断" }).click();
    await expect(
      page.getByText(
        "解析完成不等于全部网络能力已被模拟；请结合下方诊断和模型限制判断。",
      ),
    ).toBeVisible();
    await expect(
      page.getByRole("button", { name: "查看文件", exact: true }),
    ).toHaveCount(topology === "small_network" ? 2 : 4);
    await page.screenshot({
      path: testInfo.outputPath(`${topology}-diagnostics.png`),
      fullPage: true,
    });
    await page
      .getByRole("button", { name: "查看文件", exact: true })
      .first()
      .click();
    const source = page.getByRole("dialog");
    await expect(
      source.getByText("诊断未提供行号，仅展示原始文件，不高亮推测位置。"),
    ).toBeVisible();
    await expect(source.locator('[data-line="1"]')).toBeVisible();
    expect(await source.locator(".source-line").count()).toBeGreaterThan(1);
    await expect(source.locator('[data-highlight="true"]')).toHaveCount(0);
    await expect(source).toHaveCSS("width", "760px");
    await page.screenshot({
      animations: "disabled",
      path: testInfo.outputPath(`${topology}-source.png`),
      fullPage: false,
    });
    await source.getByRole("button", { name: "关闭", exact: true }).click();
    await page.getByRole("button", { name: "初始化任务", exact: true }).click();
    await page.getByRole("button", { name: "返回快照列表" }).click();
    const other = `空网络-${randomUUID().slice(0, 6)}`;
    await createNetwork(page, other);
    await expect(page.getByText("暂无快照，请先上传配置。")).toBeVisible();
    await page.getByRole("combobox", { name: "当前快照", exact: true }).click();
    await expect(page.getByText(snapshotName, { exact: false })).toHaveCount(0);
    await page.keyboard.press("Escape");
    await page
      .getByLabel("选择配置文件", { exact: true })
      .setInputFiles(
        resolve("../backend/tests/fixtures/small_network/configs/r1.cfg"),
      );
    const networkPicker = page.getByRole("combobox", {
      name: "当前网络",
      exact: true,
    });
    await networkPicker.fill(networkName);
    await networkPicker.press("Enter");
    await expect(
      page.getByRole("dialog", { name: "放弃未完成的快照向导？", exact: true }),
    ).toBeVisible();
    await page.getByRole("button", { name: "继续填写", exact: true }).click();
    await expect(
      page.getByRole("dialog", { name: "放弃未完成的快照向导？", exact: true }),
    ).toBeHidden();
    await expect(
      page.getByRole("heading", { name: other, exact: true }),
    ).toBeVisible();
    await networkPicker.fill(networkName);
    await networkPicker.press("Enter");
    await page.getByRole("button", { name: "放弃并切换", exact: true }).click();
    await expect(
      page.getByRole("heading", { name: networkName, exact: true }),
    ).toBeVisible();
    await expect(
      page.getByRole("row").filter({ hasText: snapshotName }),
    ).toBeVisible();
  });
}
