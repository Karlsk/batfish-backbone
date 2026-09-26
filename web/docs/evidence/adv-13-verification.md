# ADV-13 路由差异验收

日期：2026-09-27；基线提交：`daffc4a41c`（ADV-12）。状态：ADV-13 及 MVP-01～25、ADV-01～13 累计门槛通过。

同一比较记录内，候选配置固定为 SDK snapshot，基线固定为 reference_snapshot。当前锁定引擎直接 SDK 调用已验证三类标记：`Only in Snapshot` 为候选新增、`Only in Reference` 为候选消失、`Changed` 为属性变化。原始 `Entry_Presence`、`Snapshot_*` 与 `Reference_*` 保留在分页/导出表中，另加 `Change` 方便展示。对同一前缀的 ECMP 变化逐行保留两条变动，SDK 附带的 `Unchanged` 路由不列作变动。选定前缀无变化时明确只对该范围成立。当前 routes 静态模板写有 `differential: false`，但 Java Answerer 和实际 Pybatfish 双快照回答支持差异；这一结论只适用于锁定版本。

| 检查 | 实际结果 |
| --- | --- |
| 真实 Batfish/PostgreSQL 完整后端 `lab.py verify` | 351 passed、0 skip；a5a2de95986c/checks/29ba58d0f7eb |
| 真实 API/独立 worker `lab.py smoke` | 13 passed、338 项有意筛选；a5a2de95986c/checks/0b2a0c41b7bf |
| 前端单测、构建/类型、OpenAPI 一致性与格式 | 81 passed / 25 files；其余通过 |
| 两套配置浏览器全回归 | 23 passed、0 skip/failed；独占输出目录 |
| 新 HTTPS 部署、服务重启/失联对账、备份和新卷恢复 | 通过；deploy-adv13-batch/verification.json |
| 恢复后的生产构建浅色/深色 | 各 3 项部署检查＋1 项双用户验收，均 0 skip/failed |
| Ruff lint/变更 Python 格式、离线锁文件、Git 空白检查 | 通过 |

仓库根执行 `web/backend/.venv/bin/python web/scripts/lab.py seed`、`smoke`、`verify`，以及 `web/backend/.venv/bin/ruff check web/backend/app web/backend/tests web/backend/migrations web/scripts web/deploy`、变更 Python 文件的 `ruff format --check`、`UV_CACHE_DIR=web/.runtime/uv-cache uv lock --check --offline --directory web/backend`、`git diff --check`。`web/frontend` 执行 `pnpm generate:api`、`pnpm check:api`、`pnpm typecheck`、`pnpm test`、`pnpm build`、`pnpm format:check`、`pnpm exec playwright test --output=test-results/adv13-isolated`。本机部署在 `web/.runtime/deploy-adv13-batch` 的 18471 端口创建，并执行 `web/scripts/verify_deployment.py`；恢复后的 18472 端口分别运行浅色、深色 `playwright.deployment.config.ts` 与 `playwright.acceptance.config.ts`。日志、截图和凭证保存在忽略提交的 `.runtime/` 或前端 `test-results/`。[机器证据](adv-13-verification.json)记录 314 个源码文件的指纹 `22415dcf943383d97714511b85dd6f2dd250eac6ed65141e7766d67135e4867c`。

直接运行一次定向测试时，默认沙箱拒绝访问隔离 PostgreSQL；使用已授权本机测试后通过。单独调用真实冒烟测试缺少 `lab.py` 暂停 worker 的确认文件；在新环境通过正式 `lab.py smoke` 执行后 13 项全部通过。导出测试曾错误假定 context 位于 JSON 顶层，按既有 `metadata.context` 契约修正后通过；均未放宽产品断言。已有前端大于 500 kB 共享包提示，构建及页面检查仍通过。

环境：Batfish revision `7d0deeeac4a09973b3876327f6aef721ee12f955`，JAR SHA-256 `0927de7c740bc72f999870e842605baad9a7cb6ea66e4b01fb9a6037bea00193`，Pybatfish `2026.9.17.3748`，Python `3.12.12`，迁移 0009。结果只说明选定范围内的模型路由差异，不证明策略等价、现场转发一致性或规模容量。
