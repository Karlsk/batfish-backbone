import { randomUUID } from "node:crypto";
import { test, expect } from "@playwright/test";
import { login, loginAdmin } from "./auth-helpers";
test("real administrator and member lifecycle with session revocation", async ({
  page,
  browser,
}, testInfo) => {
  test.setTimeout(90000);
  const username = `browser-${randomUUID().slice(0, 8)}`;
  const temporary = `Temp-${randomUUID()}`;
  const password = `New-${randomUUID()}`;
  await page.setViewportSize({ width: 1280, height: 1000 });
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "登录工作台" })).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath("login.png") });
  await loginAdmin(page);
  await page.getByRole("link", { name: "用户管理", exact: true }).click();
  await page.getByRole("button", { name: "创建用户" }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel("用户名", { exact: true }).fill(username);
  await dialog.getByLabel("临时密码", { exact: true }).fill(temporary);
  await dialog.getByRole("button", { name: "保存", exact: true }).click();
  await expect(dialog).toBeHidden();
  const row = page.getByRole("row").filter({ hasText: username });
  await expect(row).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath("users.png") });
  await row.getByRole("button", { name: "详情" }).click();
  await expect(page.getByRole("dialog", { name: "用户详情" })).toBeVisible();
  await page.getByRole("button", { name: "关闭", exact: true }).click();
  await expect(page.getByRole("dialog")).toBeHidden();
  for (const role of ["管理员", "普通成员"]) {
    await row.getByRole("button", { name: "编辑权限" }).click();
    await dialog.getByLabel("角色", { exact: true }).click();
    await page.getByRole("option", { name: role, exact: true }).click();
    await dialog.getByRole("button", { name: "保存", exact: true }).click();
    await expect(dialog).toBeHidden();
    await expect(row.getByText(role, { exact: true })).toBeVisible();
  }
  const memberContext = await browser.newContext({
    viewport: { width: 1280, height: 1000 },
  });
  try {
    const member = await memberContext.newPage();
    await login(member, username, temporary);
    await expect(
      member.getByRole("heading", { name: "设置新密码" }),
    ).toBeVisible();
    await member.goto("/users");
    await expect(
      member.getByRole("heading", { name: "设置新密码" }),
    ).toBeVisible();
    await member.getByLabel("当前密码", { exact: true }).fill(temporary);
    await member.getByLabel("新密码", { exact: true }).fill(password);
    await member.getByLabel("确认新密码", { exact: true }).fill(password);
    await member.getByRole("button", { name: "更新密码并重新登录" }).click();
    await expect(
      member.getByRole("heading", { name: "登录工作台" }),
    ).toBeVisible();
    await expect(
      member.getByText("密码已更新，请使用新密码登录。"),
    ).toBeVisible();
    await login(member, username, password);
    await expect(
      member.getByRole("heading", { name: "网络分析，从一份配置开始" }),
    ).toBeVisible();
    await expect(
      member.getByRole("link", { name: "用户管理", exact: true }),
    ).toHaveCount(0);
    await member.getByRole("link", { name: "网络与快照", exact: true }).click();
    await expect(
      member.getByRole("heading", { name: "网络与快照", exact: true }),
    ).toBeVisible();
    await expect(
      member.getByRole("button", { name: "删除网络", exact: true }),
    ).toHaveCount(0);
    await member.goto("/users");
    await expect(member.getByText("当前账号没有操作权限。")).toBeVisible();
    await row.getByRole("button", { name: "编辑权限" }).click();
    await dialog.getByLabel("账号状态").click();
    await page.getByRole("option", { name: "停用", exact: true }).click();
    await dialog.getByRole("button", { name: "保存", exact: true }).click();
    await expect(dialog).toBeHidden();
    await expect(row.getByText("已停用")).toBeVisible();
    await member.reload();
    await expect(
      member.getByRole("heading", { name: "登录工作台" }),
    ).toBeVisible();
    await row.getByRole("button", { name: "编辑权限" }).click();
    await dialog.getByLabel("账号状态").click();
    await page.getByRole("option", { name: "启用", exact: true }).click();
    await dialog.getByRole("button", { name: "保存", exact: true }).click();
    await expect(dialog).toBeHidden();
    await row.getByRole("button", { name: "重置密码" }).click();
    const reset = `Reset-${randomUUID()}`;
    await dialog.getByLabel("临时密码", { exact: true }).fill(reset);
    await dialog.getByRole("button", { name: "保存", exact: true }).click();
    await expect(dialog).toBeHidden();
    await login(member, username, reset);
    await expect(
      member.getByRole("heading", { name: "设置新密码" }),
    ).toBeVisible();
    await member.getByRole("button", { name: "退出登录" }).click();
    await expect(
      member.getByRole("heading", { name: "登录工作台" }),
    ).toBeVisible();
    expect(
      await member.evaluate(() => localStorage.length + sessionStorage.length),
    ).toBe(0);
  } finally {
    await memberContext.close();
  }
});
