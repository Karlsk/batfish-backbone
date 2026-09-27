import { randomUUID } from "node:crypto";
import { expect, test } from "@playwright/test";
import { login, loginAdmin } from "./auth-helpers";

test("admin manages versioned concerns without leaking them across networks", async ({
  page,
}, testInfo) => {
  test.setTimeout(90000);
  await loginAdmin(page);
  await page.getByRole("link", { name: "领导视图" }).click();
  await page.getByRole("link", { name: "业务关注项" }).click();
  await expect(
    page.getByRole("heading", { name: "明确哪些流量最重要" }),
  ).toBeVisible();
  const network = page.getByLabel("所属网络");
  await network.click();
  const options = page.getByRole("option");
  await expect.poll(() => options.count()).toBeGreaterThan(1);
  const names = await options.allTextContents();
  expect(names.length).toBeGreaterThan(1);
  await options.first().click();
  const firstName = names[0].trim();
  const concernName = `订单关注-${randomUUID().slice(0, 8)}`;
  await page.getByRole("button", { name: "新增关注项" }).click();
  const dialog = page.getByRole("dialog", { name: "新增关注项" });
  await dialog.getByLabel("名称").fill(concernName);
  await dialog.getByLabel("重要程度").click();
  await page
    .locator(".ant-select-dropdown:visible")
    .getByText("高", { exact: true })
    .click();
  await dialog.getByLabel("起点").fill("r1");
  await dialog.getByLabel("目的 IPv4 地址").fill("10.0.0.9");
  await dialog.getByText("高级参数").click();
  await dialog.getByLabel("协议（可选）").click();
  await page
    .locator(".ant-select-dropdown:visible")
    .getByText("TCP", { exact: true })
    .click();
  await dialog.getByLabel("目的端口（仅 TCP / UDP）").fill("443");
  await expect(dialog.getByText(/r1 → 10.0.0.9 · TCP :443/)).toBeVisible();
  await dialog.getByText("高级参数").click();
  await dialog.getByRole("button", { name: "保存映射" }).click();
  await expect(dialog).toBeHidden();
  const card = page
    .locator(".leader-concern-card")
    .filter({ hasText: concernName });
  await expect(card).toContainText("映射 v1");
  await page.screenshot({
    path: testInfo.outputPath("concerns-light.png"),
    fullPage: true,
  });
  await page.getByRole("button", { name: "深色主题" }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await page.waitForTimeout(300);
  await page.screenshot({
    path: testInfo.outputPath("concerns-dark.png"),
    fullPage: true,
  });
  await page.getByRole("button", { name: "浅色主题" }).click();
  await card.getByRole("button", { name: "查看范围" }).click();
  const drawer = page.getByRole("dialog", { name: "关注项范围" });
  await expect(drawer).toContainText("TCP · 端口 443");
  await drawer.getByRole("button", { name: "编辑" }).click();
  const edit = page.getByRole("dialog", { name: "编辑关注项" });
  await expect(edit.getByLabel("目的端口（仅 TCP / UDP）")).toHaveValue("443");
  await edit.getByLabel("名称").fill(`${concernName}-更新`);
  await edit.getByRole("button", { name: "保存映射" }).click();
  await expect(edit).toBeHidden();
  const updated = page
    .locator(".leader-concern-card")
    .filter({ hasText: `${concernName}-更新` });
  await expect(updated).toContainText("映射 v2");
  await updated.getByRole("button", { name: "查看范围" }).click();
  await drawer.getByLabel("查看映射版本").click();
  await page
    .locator(".ant-select-dropdown:visible")
    .getByText("v1", { exact: true })
    .click();
  await expect(drawer).toContainText(concernName);
  await expect(drawer).not.toContainText(`${concernName}-更新`);
  await drawer.getByRole("button", { name: "关闭" }).click();
  await expect(drawer).toBeHidden();
  await page.evaluate(() => window.scrollTo(0, 0));
  await network.click();
  await page
    .locator(".ant-select-dropdown:visible .ant-select-item-option")
    .nth(1)
    .click();
  await expect(page.getByText(`${concernName}-更新`)).toHaveCount(0);
  await network.click();
  await page
    .locator(".ant-select-dropdown:visible")
    .getByText(firstName, { exact: true })
    .click();
  await expect(updated).toBeVisible();
  await updated.getByRole("button", { name: "查看范围" }).click();
  await drawer.getByRole("button", { name: "归档" }).click();
  await page
    .getByRole("dialog", { name: /归档/ })
    .getByRole("button", { name: "归档" })
    .click();
  await expect(updated).toHaveCount(0);
  await page.reload();
  await network.click();
  await page
    .locator(".ant-select-dropdown:visible")
    .getByText(firstName, { exact: true })
    .click();
  await expect(page.getByText(`${concernName}-更新`)).toHaveCount(0);
});

test("member reads shared concerns and stale edits keep their draft", async ({
  page,
  browser,
}) => {
  test.setTimeout(120000);
  await loginAdmin(page);
  await page.getByRole("link", { name: "领导视图" }).click();
  await page.getByRole("link", { name: "业务关注项" }).click();
  const network = page.getByLabel("所属网络");
  await network.click();
  const first = await page
    .locator(".ant-select-dropdown:visible .ant-select-item-option")
    .first()
    .textContent();
  await page
    .locator(".ant-select-dropdown:visible .ant-select-item-option")
    .first()
    .click();
  const name = `成员可读-${randomUUID().slice(0, 8)}`;
  await page.getByRole("button", { name: "新增关注项" }).click();
  const create = page.getByRole("dialog", { name: "新增关注项" });
  await create.getByLabel("名称").fill(name);
  await create.getByLabel("起点").fill("r1");
  await create.getByLabel("目的 IPv4 地址").fill("10.0.0.2");
  await create.getByRole("button", { name: "保存映射" }).click();
  await expect(create).toBeHidden();
  const card = page.locator(".leader-concern-card").filter({ hasText: name });
  await card.getByRole("button", { name: "查看范围" }).click();
  const drawer = page.getByRole("dialog", { name: "关注项范围" });
  await drawer.getByRole("button", { name: "编辑" }).click();
  const edit = page.getByRole("dialog", { name: "编辑关注项" });
  await edit.getByLabel("名称").fill(`${name}-本地草稿`);
  const result = await page.evaluate(async (concernName) => {
    const me = await fetch("/api/v1/auth/me").then((response) =>
      response.json(),
    );
    const concern = await fetch("/api/v1/business-concerns").then((response) =>
      response.json(),
    );
    const item = concern.items.find(
      (candidate: { name: string }) => candidate.name === concernName,
    );
    return fetch(`/api/v1/business-concerns/${item.id}`, {
      method: "PATCH",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        "X-CSRF-Token": me.csrf_token,
      },
      body: JSON.stringify({
        expected_version: item.version,
        name: `${concernName}-远端更新`,
      }),
    }).then((response) => response.status);
  }, name);
  expect(result).toBe(200);
  await edit.getByRole("button", { name: "保存映射" }).click();
  await expect(edit.getByText(/版本冲突/)).toBeVisible();
  await expect(edit.getByLabel("名称")).toHaveValue(`${name}-本地草稿`);
  await edit.getByRole("button", { name: "取消" }).click();

  await page
    .locator(".leader-topbar")
    .getByRole("link", { name: "技术工作台" })
    .click();
  await page.getByRole("link", { name: "用户管理" }).click();
  await page.getByRole("button", { name: "创建用户" }).click();
  const userDialog = page.getByRole("dialog", { name: "创建用户" });
  const username = `leader-${randomUUID().slice(0, 8)}`;
  const temporary = `Temp-${randomUUID()}`;
  const password = `New-${randomUUID()}`;
  await userDialog.getByLabel("用户名", { exact: true }).fill(username);
  await userDialog.getByLabel("临时密码", { exact: true }).fill(temporary);
  await userDialog.getByRole("button", { name: "保存" }).click();
  await expect(userDialog).toBeHidden();
  const memberContext = await browser.newContext();
  try {
    const member = await memberContext.newPage();
    await login(member, username, temporary);
    await expect(
      member.getByRole("heading", { name: "设置新密码" }),
    ).toBeVisible();
    await member.getByLabel("当前密码").fill(temporary);
    await member.getByLabel("新密码", { exact: true }).fill(password);
    await member.getByLabel("确认新密码").fill(password);
    await member.getByRole("button", { name: "更新密码并重新登录" }).click();
    await login(member, username, password);
    await member.getByRole("link", { name: "领导视图" }).click();
    await member.getByRole("link", { name: "业务关注项" }).click();
    const memberNetwork = member.getByLabel("所属网络");
    await memberNetwork.click();
    await member
      .locator(".ant-select-dropdown:visible")
      .getByText(first?.trim() ?? "", { exact: true })
      .click();
    const shared = member
      .locator(".leader-concern-card")
      .filter({ hasText: `${name}-远端更新` });
    await expect(shared).toBeVisible();
    await expect(
      member.getByRole("button", { name: "新增关注项" }),
    ).toHaveCount(0);
    await shared.getByRole("button", { name: "查看范围" }).click();
    const memberDrawer = member.getByRole("dialog", { name: "关注项范围" });
    await expect(memberDrawer).toContainText("10.0.0.2");
    await expect(
      memberDrawer.getByRole("button", { name: "编辑" }),
    ).toHaveCount(0);
    await expect(
      memberDrawer.getByRole("button", { name: "归档" }),
    ).toHaveCount(0);
  } finally {
    await memberContext.close();
  }
});
