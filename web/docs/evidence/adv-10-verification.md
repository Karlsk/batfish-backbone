# ADV-10 第二阶段整体验收证据

日期：2026-09-26；基线提交：`2350107f51`（ADV-09）。状态：ADV-10 及 MVP-01～25、ADV-01～10 累计门槛通过。完整结论见[第二阶段验收报告](../advance-phase2-acceptance.md)。

| 检查 | 实际结果 |
| --- | --- |
| 后端完整 `lab.py verify` | 330 passed、0 skip；27c57a46ecac/checks/30b90814d266 |
| 真实 API/worker `lab.py smoke` | 12 passed；318项为有意筛选；checks/37eb967f949b |
| 前端完整单测、构建/类型、OpenAPI 一致性、格式 | 81 passed / 25 files；其余通过 |
| 两套配置及阶段样例浏览器全回归 | 23 passed、0 skip/failed |
| 新 HTTPS 部署、服务重启/失联对账、备份及新卷恢复 | 通过；deploy-adv10-batch/verification.json |
| 恢复后生产构建浅色/深色 | 各3项部署＋1项双用户验收，均0 skip/failed |
| Ruff lint/本篇 Python 格式、离线锁文件、Git 空白检查 | 通过 |

新增后端验收在一个派生 Cisco 快照上直接对照 SDK 三层边与 BGP 行；孤立设备保留但无伪边，c1→c2 的 AS 错配为 `NOT_COMPATIBLE`。ACL 的 permit、显式/隐式 deny，以及规则诊断的 `BLOCKING_LINES`、`INDEPENDENTLY_UNMATCHABLE` 均在真实引擎上获得；专家与专用 `nodes` 请求命中同一结果身份和有效参数，任意问题 ID 返回422。新增浏览器从上传到结果跨拓扑、BGP、ACL、专家四页保持同一快照来源，BGP 模型提示可见。既有 ADV-01～09 的独立 SDK 细项、厂商限制及双用户不同快照验收通过累计测试覆盖。

仓库根实际执行 `web/backend/.venv/bin/python web/scripts/lab.py verify`、`smoke`，`web/backend/.venv/bin/ruff check web/backend/app web/backend/tests web/scripts web/deploy`、新增 Python 文件 `ruff format --check`、`UV_CACHE_DIR=web/.runtime/uv-cache uv lock --check --offline --directory web/backend`、`git diff --check`。`web/frontend` 执行 `pnpm test`、`pnpm build`、`pnpm check:api`、`pnpm typecheck`、`pnpm format:check`、`pnpm exec playwright test`。本机部署使用 `web/scripts/deploy.py prepare --state web/.runtime/deploy-adv10-batch --port 18465`、`build` 和 `web/scripts/verify_deployment.py --state web/.runtime/deploy-adv10-batch`；恢复后配置正确的 `BFW_DEPLOYMENT_STATE`、`BFW_DEPLOYMENT_EVIDENCE`，在 `BFW_TEST_THEME=light/dark` 下分别运行 `playwright.deployment.config.ts` 与 `playwright.acceptance.config.ts`。部署实例验收后停止，卷和日志保留。

固定 Batfish revision `7d0deeeac4a09973b3876327f6aef721ee12f955`、JAR SHA-256 `0927de7c740bc72f999870e842605baad9a7cb6ea66e4b01fb9a6037bea00193`、Pybatfish `2026.9.17.3748`、Python `3.12.12`，迁移0008。[机器证据](adv-10-verification.json)记录298个源码文件的指纹 `77396cb09d913c0c1797c1b0ec27ddc734403d9d0f3bcac5bf455a851348535c`。原始日志、凭证和截图仅存忽略提交的 `.runtime/` 或前端 `test-results/`。

自审确认新增内容仅为验收测试和文档；API/service/controller 分层与 SDK 分派未改。完整回归无失败或必需跳过。前端现有共享包仍有大于500 kB 提示，但构建与页面通过。未取得现场设备转发对照或百台设备容量数据；本篇结论限定在配置模型及所选范围。
