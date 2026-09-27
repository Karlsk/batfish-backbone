import { expect, type Page, type TestInfo } from "@playwright/test";
async function loadNetwork(page: Page, name: string) {
  const row = page.getByRole("row").filter({ hasText: name });
  await expect(
    page.getByRole("heading", { name: "网络与快照", exact: true }),
  ).toBeVisible();
  await expect(page.locator(".ant-spin-spinning")).toHaveCount(0);
  const more = page.getByRole("button", { name: /加载更多网络/ });
  while (!(await row.count()) && (await more.count())) {
    await expect(more).toBeEnabled();
    const count = await page.getByRole("row").count();
    await more.click();
    await expect
      .poll(() => page.getByRole("row").count())
      .toBeGreaterThan(count);
  }
  await expect(row).toBeVisible();
}
export async function verifyDeletion(
  page: Page,
  testInfo: TestInfo,
  networkName: string,
  snapshotId: string,
) {
  const resultUrl = page.url();
  await page.getByRole("link", { name: "网络与快照", exact: true }).click();
  await loadNetwork(page, networkName);
  const networkRow = page.getByRole("row").filter({ hasText: networkName });
  await networkRow
    .getByRole("button", { name: "删除网络", exact: true })
    .click();
  let dialog = page.getByRole("dialog", { name: "确认删除网络" });
  await dialog.getByRole("button", { name: "确认删除", exact: true }).click();
  await expect(
    dialog.getByText(/存在活动任务、未删除快照或待对账状态/),
  ).toBeVisible();
  await dialog.getByRole("button", { name: "保留资源", exact: true }).click();
  await networkRow
    .getByRole("button", { name: "查看快照", exact: true })
    .click();
  const snapshotRow = page.getByRole("row").filter({ hasText: snapshotId });
  await snapshotRow
    .getByRole("button", { name: "删除快照", exact: true })
    .click();
  dialog = page.getByRole("dialog", { name: "确认删除快照" });
  await expect(
    dialog.getByText(`资源编号：${snapshotId}`, { exact: true }),
  ).toBeVisible();
  await expect(dialog).toHaveCSS("opacity", "1");
  await dialog.screenshot({
    path: testInfo.outputPath("delete-confirmation.png"),
    animations: "allow",
  });
  await dialog.getByRole("button", { name: "保留资源", exact: true }).click();
  await expect(snapshotRow.getByText(/^就绪/)).toBeVisible();
  await snapshotRow
    .getByRole("button", { name: "删除快照", exact: true })
    .click();
  await dialog.getByRole("button", { name: "确认删除", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "删除任务", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "取消排队", exact: true }),
  ).toHaveCount(0);
  await expect(page.getByText("已完成", { exact: true })).toBeVisible({
    timeout: 90000,
  });
  await page.reload();
  await expect(page.getByText("已完成", { exact: true })).toBeVisible();
  await page.getByRole("link", { name: "网络与快照", exact: true }).click();
  await loadNetwork(page, networkName);
  await networkRow
    .getByRole("button", { name: "查看快照", exact: true })
    .click();
  await expect(
    page.getByText("暂无快照，请先上传配置。", { exact: true }),
  ).toBeVisible();
  await page.getByRole("link", { name: "网络与快照", exact: true }).click();
  await networkRow
    .getByRole("button", { name: "删除网络", exact: true })
    .click();
  dialog = page.getByRole("dialog", { name: "确认删除网络" });
  await dialog.getByRole("button", { name: "确认删除", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "删除任务", exact: true }),
  ).toBeVisible();
  await expect(page.getByText("已完成", { exact: true })).toBeVisible({
    timeout: 90000,
  });
  await page.getByRole("link", { name: "网络与快照", exact: true }).click();
  await expect(networkRow).toHaveCount(0, { timeout: 15000 });
  await page.goto(resultUrl);
  await expect(
    page.getByRole("heading", { name: "分析结果", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText(`来源快照：${snapshotId}`, { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "下载 JSON", exact: true }),
  ).toBeVisible();
  await page.screenshot({
    path: testInfo.outputPath("retained-result.png"),
    animations: "disabled",
  });
}
