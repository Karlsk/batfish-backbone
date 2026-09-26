# ADV-11 双快照对比上下文验收

日期：2026-09-26；基线提交：`198106e241`（ADV-10）。状态：ADV-11 及 MVP-01～25、ADV-01～11 累计门槛通过。

同一网络内的两个不同且可分析的快照可以建立不可变比较记录。记录保留基线/候选 ID、内容摘要、引擎与 SDK 版本及覆盖提示；后续差异分析上下文固定为 candidate→SDK snapshot、baseline→SDK reference_snapshot。跨网络、相同快照和版本不兼容被拒绝，创建不触发差异计算。管理员可以在无在途任务时软删除比较记录；有效引用阻止快照删除，创建比较与删除快照使用同一资源锁。删除比较记录后，原记录与审计保留，快照的实际 worker 清理继续成功。

| 检查 | 实际结果 |
| --- | --- |
| 真实 Batfish/PostgreSQL 完整后端 `lab.py verify` | 336 passed、0 skip；c2a637e59e5d/checks/80f50a549f39 |
| 新迁移实验环境的真实 API/worker `lab.py smoke` | 12 passed、324 项有意筛选；c2a637e59e5d/checks/2ef00cd3e8c4 |
| 前端单测、构建/类型、OpenAPI 一致性与格式 | 81 passed / 25 files；其余通过 |
| 两套配置浏览器全回归 | 23 passed、0 skip/failed |
| 新 HTTPS 部署、服务重启/失联对账、备份和新卷恢复 | 通过；deploy-adv11-batch/verification.json |
| 恢复后的生产构建浅色/深色 | 各 3 项部署检查＋1 项双用户验收，均 0 skip/failed |
| Ruff lint/变更 Python 格式、离线锁文件、Git 空白检查 | 通过 |

仓库根执行 `web/backend/.venv/bin/python web/scripts/lab.py smoke`、`web/backend/.venv/bin/python web/scripts/lab.py verify`、`web/backend/.venv/bin/ruff check web/backend/app web/backend/tests web/backend/migrations web/scripts web/deploy`、变更 Python 文件的 `ruff format --check`、`UV_CACHE_DIR=web/.runtime/uv-cache uv lock --check --offline --directory web/backend`、`git diff --check`。`web/frontend` 执行 `pnpm generate:api`、`pnpm check:api`、`pnpm typecheck`、`pnpm test`、`pnpm build`、`pnpm format:check`、`pnpm exec playwright test`。本机部署执行 `web/scripts/deploy.py prepare --state web/.runtime/deploy-adv11-batch --port 18467`、`build`、`web/scripts/verify_deployment.py --state web/.runtime/deploy-adv11-batch`；设置恢复后 `BFW_DEPLOYMENT_STATE` 和原验证的 `BFW_DEPLOYMENT_EVIDENCE`，在 `BFW_TEST_THEME=light/dark` 下分别运行 `playwright.deployment.config.ts`、`playwright.acceptance.config.ts`。日志、截图和凭证保存在忽略提交的 `.runtime/` 或前端 `test-results/`。[机器证据](adv-11-verification.json)记录 306 个源码文件的指纹 `d6b748bebaf68534c8a82ba95f4dca112613c2e13da098bbdb9bf8254be86f65`。

首次冒烟失败是实验环境清单将迁移写死为 0008；改为读取 Alembic 当前 head 后，全新 0009 环境的 12 项冒烟通过。首次浏览器命令在默认沙箱中无法绑定本机测试端口；授权本机启动后的 23 项完整回归通过。没有放宽断言。前端生产构建仍有既有大于 500 kB 的共享包提示，但构建和页面检查通过。

环境：Batfish revision `7d0deeeac4a09973b3876327f6aef721ee12f955`，JAR SHA-256 `0927de7c740bc72f999870e842605baad9a7cb6ea66e4b01fb9a6037bea00193`，Pybatfish `2026.9.17.3748`，Python `3.12.12`，迁移 0009。仅验证比较元数据与方向，差异计算属于 ADV-12～14。合成配置功能通过不等于现场转发一致性或规模容量证明。
