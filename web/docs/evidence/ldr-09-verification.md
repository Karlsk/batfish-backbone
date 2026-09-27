# LDR-09 变更与故障领导视图验收

日期：2026-09-28；基线提交 `3476f0ed3e`（LDR-08）。隔离环境运行 ID `8a53df3cb24f`，Batfish revision `7d0deeeac4a09973b3876327f6aef721ee12f955`，Pybatfish `2026.9.17.3748`，Python `3.12.12`。以下仅验证合成配置上的 Web 工作流和固定版本模型，不证明真实设备转发或 Java 仿真精度。

| 检查 | 结果 |
| --- | --- |
| 目标单测 | `web/frontend` 执行 `pnpm exec vitest run src/features/leader/changes/model.test.ts`：7 passed；覆盖固定比较范围、业务流量精确匹配、失败派生阻断。 |
| 前端全量 | `web/frontend` 执行 `pnpm check:api && pnpm test && pnpm build && pnpm format:check`：OpenAPI 契约一致、115 passed、TypeScript 与生产构建和格式通过。最终网络名称及视觉修正后又执行 `pnpm check:api && pnpm typecheck && pnpm build && pnpm format:check`，全部通过。构建仍提示已有大包体积。 |
| 后端回归 | 在 `web/backend` 设置 `BATFISH_LAB_MANIFEST=/Users/gaorenjie/Documents/Coding/JAVA/batfish-dev/web/.runtime/test-lab/current.json` 并执行 `.venv/bin/python -m pytest tests/test_business_concerns.py -q`：3 passed；受影响 repository 的 Ruff check 与 format check 通过。 |
| 真实浏览器累计 | `python3 /private/tmp/ldr03-run.py tests/leader-changes.spec.ts tests/leader-advanced-checks.spec.ts tests/leader-mvp-checks.spec.ts tests/leader-checks-api.spec.ts tests/leader-overview.spec.ts tests/leader-entry.spec.ts tests/leader-concerns.spec.ts tests/auth-users.spec.ts`（工作目录 `web/frontend`）：18 passed，覆盖 LDR-01～09 与原用户管理。实际启动当前源码 API、隔离 PostgreSQL/Batfish、独立 worker 和 Chromium。 |
| 原技术端回归 | `python3 /private/tmp/ldr03-run.py tests/changes.spec.ts tests/faults.spec.ts`（工作目录 `web/frontend`）：2 passed；原双快照比较与故障派生技术页面继续可用。 |
| 已知差异 | 两份 Cisco 四设备合成快照中，候选相对基线修改 `c1.cfg`、替换静态路由并增加指定 ACL；领导端分别运行配置、网段路由与 `c1 → 10.64.0.4` 流量比较，固定基线→候选方向，按范围解释结果。故障向导对基线停用 `c2`，真实 worker 生成派生快照，待就绪才给出固定比较入口；模拟失败快照时入口消失。 |
| 页面检查 | Chromium 全页截图 `web/frontend/test-results/leader-changes-leader-fixe-f0af9-on-a-ready-derived-snapshot-chromium/leader-fixed-comparison.png` 和 `leader-derived-ready.png` 已目视检查；快照显示名称及固定 ID，主按钮文字对比度已修正。截图目录为本地测试产物，不纳入提交。 |

首次累计浏览器运行中，变更下拉选项在数据刷新时失稳，关注项列表在累积超过 20 条后新建项落在末页，导致 3 项失败；使用键盘完成明确选项选择并将列表改为最新优先后，受影响 3 项和完整 18 项均重跑通过。早前截图中的“服务尚未就绪”缺少原请求和快照上下文，不能声称定位为同一故障；未就绪错误与重试提示仍由累计浏览器用例覆盖。
