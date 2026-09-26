import { createHash, randomUUID } from "node:crypto";
import { readdirSync, readFileSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";
import { test, expect, type Page } from "@playwright/test";
import { login, loginAdmin } from "../tests/auth-helpers";
import type { components } from "../src/api/schema";

async function checkConfiguration(
  page: Page,
  context: { network_id: string; snapshot_id: string },
  fixture: string,
) {
  const folder = resolve(`../backend/tests/fixtures/${fixture}/configs`);
  const base = `/api/v1/networks/${context.network_id}/snapshots/${context.snapshot_id}/files`;
  const response = await page.request.get(base);
  expect(response.status()).toBe(200);
  const files: components["schemas"]["SnapshotFiles"] = await response.json();
  expect(files.items.map((file) => file.path).sort()).toEqual(
    readdirSync(folder)
      .map((name) => `configs/${name}`)
      .sort(),
  );
  for (const file of files.items) {
    const original = readFileSync(
      resolve(folder, file.path.slice("configs/".length)),
    );
    expect(file.sha256).toBe(
      createHash("sha256").update(original).digest("hex"),
    );
    const source = await page.request.get(`${base}/${file.id}?limit=200`);
    expect(source.status()).toBe(200);
    const content: components["schemas"]["FilePage"] = await source.json();
    const lines = original
      .toString("utf8")
      .replace(/\r+\n|\r+/g, "\n")
      .split("\n");
    if (lines.at(-1) === "") lines.pop();
    expect(content.total).toBe(lines.length);
    expect(content.lines).toEqual(
      lines.map((text, index) => ({
        number: index + 1,
        text,
        truncated: false,
      })),
    );
    expect(content.warnings).toEqual([]);
  }
}

async function createNetwork(page: Page, name: string) {
  await page.getByRole("link", { name: "网络与快照", exact: true }).click();
  await page.getByRole("button", { name: "创建网络", exact: true }).click();
  const dialog = page.getByRole("dialog", { name: "创建网络" });
  await dialog.getByLabel("网络名称", { exact: true }).fill(name);
  await dialog.getByRole("button", { name: "创建", exact: true }).click();
  await expect(page.getByRole("heading", { name, exact: true })).toBeVisible();
}
async function upload(page: Page, fixture: string) {
  const folder = resolve(`../backend/tests/fixtures/${fixture}/configs`);
  await page
    .getByLabel("选择配置文件", { exact: true })
    .setInputFiles(readdirSync(folder).map((n) => resolve(folder, n)));
  await page.getByRole("button", { name: "上传并校验", exact: true }).click();
  await expect(page.getByText(/文件校验完成.*尚未初始化/)).toBeVisible();
  await page.getByLabel("快照名称", { exact: true }).fill(`双用户-${fixture}`);
}
async function initialize(page: Page) {
  const response = page.waitForResponse(
    (r) =>
      r.request().method() === "POST" &&
      /\/snapshots$/.test(new URL(r.url()).pathname),
  );
  await page.getByRole("button", { name: "提交初始化", exact: true }).click();
  return (await response).json() as Promise<{
    snapshot_id: string;
    job_id: string;
  }>;
}
async function restoreTaskAndSelect(
  page: Page,
  name: string,
  created: { snapshot_id: string; job_id: string },
) {
  await page.goto(`/jobs/${created.job_id}`);
  await page.reload();
  await expect(page.getByText("已完成", { exact: true })).toBeVisible({
    timeout: 90000,
  });
  await page.getByRole("link", { name: "网络与快照", exact: true }).click();
  await page
    .getByRole("row")
    .filter({ hasText: name })
    .getByRole("button", { name: "查看快照", exact: true })
    .click();
  await page
    .getByRole("row")
    .filter({ hasText: created.snapshot_id })
    .getByRole("button", { name: "选择快照", exact: true })
    .click();
}
async function submitNodes(page: Page) {
  await page.getByRole("link", { name: "网络分析", exact: true }).click();
  await page.getByRole("link", { name: "设备", exact: true }).click();
  const response = page.waitForResponse(
    (r) =>
      r.request().method() === "POST" &&
      /\/analyses\/nodes$/.test(new URL(r.url()).pathname),
  );
  await page.getByRole("button", { name: "执行查询", exact: true }).click();
  return (await response).json() as Promise<{
    id: string;
    created_by: string;
    context: { network_id: string; snapshot_id: string };
  }>;
}
async function checkResult(
  page: Page,
  snapshot: string,
  nodes: string[],
  foreign: string,
) {
  await expect(page.getByText("已完成", { exact: true })).toBeVisible({
    timeout: 90000,
  });
  await page.getByRole("button", { name: "查看分析结果", exact: true }).click();
  await expect(
    page.getByText(`来源快照：${snapshot}`, { exact: true }),
  ).toBeVisible();
  for (const node of nodes) {
    await expect(
      page.getByRole("cell", { name: node, exact: true }).first(),
    ).toBeVisible();
  }
  await expect(page.locator("tbody tr[data-row-key]")).toHaveCount(
    nodes.length,
  );
  await expect(
    page.getByRole("cell", { name: foreign, exact: true }),
  ).toHaveCount(0);
  const url = page.url();
  await page.reload();
  await expect(
    page.getByText(`来源快照：${snapshot}`, { exact: true }),
  ).toBeVisible();
  for (const node of nodes) {
    await expect(
      page.getByRole("cell", { name: node, exact: true }).first(),
    ).toBeVisible();
  }
  await expect(page.locator("tbody tr[data-row-key]")).toHaveCount(
    nodes.length,
  );
  return url;
}

test("two independent users interleave snapshots, queries, refresh and revocation", async ({
  page,
  browser,
}, info) => {
  test.setTimeout(240000);
  await page.setViewportSize({ width: 1280, height: 1000 });
  const deploymentEvidence = process.env.BFW_DEPLOYMENT_EVIDENCE;
  if (deploymentEvidence) {
    const report = JSON.parse(readFileSync(deploymentEvidence, "utf8"));
    const credentials = JSON.parse(
      readFileSync(`${report.state.state_dir}/auth.json`, "utf8"),
    );
    await login(page, credentials.username, credentials.password);
    await expect(
      page.getByRole("heading", { name: "网络分析，从一份配置开始" }),
    ).toBeVisible();
  } else {
    await loginAdmin(page);
  }
  const adminIdentity = await (
    await page.request.get("/api/v1/auth/me")
  ).json();
  const username = `acceptance-${randomUUID().slice(0, 8)}`;
  const temporary = `Temp-${randomUUID()}`;
  const password = `New-${randomUUID()}`;
  await page.getByRole("link", { name: "用户管理", exact: true }).click();
  await page.getByRole("button", { name: "创建用户", exact: true }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel("用户名", { exact: true }).fill(username);
  await dialog.getByLabel("临时密码", { exact: true }).fill(temporary);
  await dialog.getByRole("button", { name: "保存", exact: true }).click();
  await expect(dialog).toBeHidden();
  const context = await browser.newContext({
    baseURL: info.project.use.baseURL,
    ignoreHTTPSErrors: info.project.use.ignoreHTTPSErrors,
    colorScheme: info.project.use.colorScheme,
    viewport: { width: 1280, height: 1000 },
  });
  try {
    const member = await context.newPage();
    await login(member, username, temporary);
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
    await login(member, username, password);
    await expect(
      member.getByRole("heading", { name: "网络分析，从一份配置开始" }),
    ).toBeVisible();
    const memberIdentity = await (
      await member.request.get("/api/v1/auth/me")
    ).json();
    expect(memberIdentity.user_id).not.toBe(adminIdentity.user_id);
    await expect(
      member.getByRole("link", { name: "用户管理", exact: true }),
    ).toHaveCount(0);
    const names = [
      `双用户-r1r2-${randomUUID().slice(0, 6)}`,
      `双用户-cisco-${randomUUID().slice(0, 6)}`,
    ];
    // Network creation uses a synchronous exclusive SDK slot; complete setup sequentially.
    await createNetwork(page, names[0]);
    await createNetwork(member, names[1]);
    await expect(
      member.getByRole("button", { name: /删除快照|删除网络/ }),
    ).toHaveCount(0);
    await Promise.all([
      upload(page, "small_network"),
      upload(member, "cisco_four"),
    ]);
    const [first, second] = await Promise.all([
      initialize(page),
      initialize(member),
    ]);
    expect(first.snapshot_id).not.toBe(second.snapshot_id);
    await Promise.all([
      restoreTaskAndSelect(page, names[0], first),
      restoreTaskAndSelect(member, names[1], second),
    ]);
    const [a, b] = await Promise.all([submitNodes(page), submitNodes(member)]);
    expect(a.created_by).toBe(adminIdentity.user_id);
    expect(b.created_by).toBe(memberIdentity.user_id);
    expect(a.context.snapshot_id).toBe(first.snapshot_id);
    expect(b.context.snapshot_id).toBe(second.snapshot_id);
    await Promise.all([
      checkConfiguration(page, a.context, "small_network"),
      checkConfiguration(member, b.context, "cisco_four"),
    ]);
    const [urlA, urlB] = await Promise.all([
      checkResult(page, first.snapshot_id, ["r1", "r2"], "c1"),
      checkResult(member, second.snapshot_id, ["c1", "c2", "c3", "c4"], "r1"),
    ]);
    await page
      .getByRole("combobox", { name: "当前网络", exact: true })
      .fill(names[1]);
    await page.getByRole("option", { name: new RegExp(names[1]) }).click();
    await page
      .getByRole("combobox", { name: "当前快照", exact: true })
      .fill("双用户-cisco_four");
    await page.getByRole("option", { name: /双用户-cisco_four/ }).click();
    expect(page.url()).toBe(urlA);
    expect(member.url()).toBe(urlB);
    await expect(
      page.getByText(`来源快照：${first.snapshot_id}`, { exact: true }),
    ).toBeVisible();
    await expect(
      page.getByRole("cell", { name: "r1", exact: true }).first(),
    ).toBeVisible();
    await expect(
      member.getByRole("cell", { name: "c1", exact: true }).first(),
    ).toBeVisible();
    await page.screenshot({
      path: info.outputPath("admin-fixed-r1r2-result.png"),
      animations: "disabled",
    });
    await member.screenshot({
      path: info.outputPath("member-cisco-result.png"),
      animations: "disabled",
    });
    writeFileSync(
      info.outputPath("two-user-context.json"),
      JSON.stringify(
        {
          admin_user_id: adminIdentity.user_id,
          member_user_id: memberIdentity.user_id,
          first,
          second,
          queries: [a, b],
          result_urls: [urlA, urlB],
        },
        null,
        2,
      ),
    );
    await page.getByRole("link", { name: "用户管理", exact: true }).click();
    await page
      .getByRole("row")
      .filter({ hasText: username })
      .getByRole("button", { name: "编辑权限", exact: true })
      .click();
    await dialog.getByLabel("账号状态").click();
    await page.getByRole("option", { name: "停用", exact: true }).click();
    await dialog.getByRole("button", { name: "保存", exact: true }).click();
    await expect(dialog).toBeHidden();
    await member.reload();
    await expect(
      member.getByRole("heading", { name: "登录工作台" }),
    ).toBeVisible();
  } finally {
    await context.close();
  }
});
