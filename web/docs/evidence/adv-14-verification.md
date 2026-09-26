# ADV-14 差异可达性验收

日期：2026-09-27；基线提交：`72ca4b2491`（ADV-13）。状态：ADV-14 及 MVP-01～25、ADV-01～14 累计门槛通过。

锁定版 Pybatfish 的 `differentialReachability` 在同一 Flow 中返回候选 `Snapshot_Traces`、基线 `Reference_Traces` 及两侧原始路径计数。可控 Cisco 四设备配置中，对 c1 的出向 ACL 加拒绝规则，候选相对基线失去可达性；反向配置得到新增可达性；仅修改 OSPF 路径成本而两侧均可达时没有可达性差异。接口保留 Flow 和双侧路径，按可达 disposition 给出 `added`、`removed` 或 `undetermined`。若 `max_traces` 截断且某侧未见可达路径，该侧为 `null`，结果标记 `trace_limit`，不把有限证据误判为不可达。示例数量明确限定为 SDK witness rows。

| 检查 | 实际结果 |
| --- | --- |
| 真实 Batfish/PostgreSQL 完整后端 `lab.py verify` | 357 passed、0 skip；351638977894/checks/fc2eb15ffd92 |
| 真实 API/独立 worker `lab.py smoke` | 13 passed、343 项有意筛选；351638977894/checks/e9712118c8a9 |
| 前端单测、构建/类型、OpenAPI 一致性与格式 | 81 passed / 25 files；其余通过 |
| 两套配置浏览器全回归 | 23 passed、0 skip/failed；独占输出目录 `adv14-final` |
| 新 HTTPS 部署、服务重启/失联对账、备份和新卷恢复 | 通过；deploy-adv14-batch/verification.json |
| 恢复后的生产构建浅色/深色 | 各 3 项部署检查＋1 项双用户验收，均 0 skip/failed |
| Ruff lint/变更 Python 格式、离线锁文件、Git 空白检查 | 通过 |

仓库根实际运行 `web/backend/.venv/bin/python web/scripts/lab.py seed/smoke/verify`，以及 `web/backend/.venv/bin/ruff check web/backend/app web/backend/tests web/backend/migrations web/scripts web/deploy`、变更 Python 文件 `ruff format --check`、`UV_CACHE_DIR=web/.runtime/uv-cache uv lock --check --offline --directory web/backend`、`git diff --check`。`web/frontend` 运行 `pnpm generate:api`、`pnpm check:api`、`pnpm typecheck`、`pnpm test`、`pnpm build`、`pnpm format:check`、`pnpm exec playwright test --output=test-results/adv14-final`。本机部署使用 `web/.runtime/deploy-adv14-batch` 的 18473 端口创建和构建，运行 `web/scripts/verify_deployment.py` 后在恢复后的 18474 端口分别运行明暗主题的 `playwright.deployment.config.ts` 与 `playwright.acceptance.config.ts`。原始日志、截图及测试凭证留在忽略提交的 `.runtime/` 或前端 `test-results/`。[机器证据](adv-14-verification.json)记录 317 个源码文件的指纹 `21640faa2768e268c6c7451315dcd7face0af9f28b7a3dd8413c7c53e37ec084`。

首次全量浏览器运行 21/23 通过：ACL 候选选择及一项旧分析任务状态等待超时；两项单独复跑 2/2 通过，随后整套重跑 23/23 通过。首次 HTTPS 演练在 Docker 守护进程短暂失联时中断；本机服务恢复后，同一个隔离部署的完整演练重跑通过，原失败未计入通过数。没有放宽产品断言。已有前端共享包超过 500 kB 的提示，但构建及页面检查通过。

环境：Batfish revision `7d0deeeac4a09973b3876327f6aef721ee12f955`，JAR SHA-256 `0927de7c740bc72f999870e842605baad9a7cb6ea66e4b01fb9a6037bea00193`，Pybatfish `2026.9.17.3748`，Python `3.12.12`，迁移 0009。结果只说明提交范围内的模型可达性变化样例，不证明全量业务影响、现场转发或回程。
