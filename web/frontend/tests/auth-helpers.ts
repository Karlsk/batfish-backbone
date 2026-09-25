import { readFileSync } from "node:fs";
import { expect, type Page } from "@playwright/test";
export function labCredentials() {
  const manifest = JSON.parse(
    readFileSync("../.runtime/test-lab/current.json", "utf8"),
  );
  return JSON.parse(
    readFileSync(`${manifest.run_directory}/auth.json`, "utf8"),
  ) as { username: string; password: string };
}
export async function login(page: Page, username: string, password: string) {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "登录工作台" })).toBeVisible();
  await page.getByLabel("用户名", { exact: true }).fill(username);
  await page.getByLabel("密码", { exact: true }).fill(password);
  await page.getByRole("button", { name: "登录", exact: true }).click();
}
export async function loginAdmin(page: Page) {
  const credentials = labCredentials();
  await login(page, credentials.username, credentials.password);
  await expect(
    page.getByRole("heading", { name: "网络分析，从一份配置开始" }),
  ).toBeVisible();
}
