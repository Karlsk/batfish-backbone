# ADV-12 配置文件差异验收

日期：2026-09-27；基线提交：`cf52837b72`（ADV-11）。状态：ADV-12 及 MVP-01～25、ADV-01～12 累计门槛通过。

配置差异任务绑定 ADV-11 的不可变比较上下文，候选映射 snapshot，基线映射 reference_snapshot。文件按完整相对路径和原始 SHA-256 分类为新增、删除、变化；同一路径的文本详情提供两侧行号。GB18030、换行转换、二进制、超长行和超限文件保留原始摘要并标明显示限制。任务沿用身份、幂等、缓存、重试、worker 生命周期及原子结果发布。真实 Cisco 两快照的 API/独立 worker 冒烟验证了提交、完成和结果文件详情。

| 检查 | 实际结果 |
| --- | --- |
| 真实 Batfish/PostgreSQL 完整后端 `lab.py verify` | 345 passed、0 skip；bb1cdce974dd/checks/89f00799faba |
| 真实 API/worker `lab.py smoke` | 13 passed、332 项有意筛选；bb1cdce974dd/checks/dd89ab24731a |
| 前端单测、构建/类型、OpenAPI 一致性与格式 | 81 passed / 25 files；其余通过 |
| 两套配置浏览器全回归 | 23 passed、0 skip/failed；使用独占输出目录 |
| 新 HTTPS 部署、服务重启/失联对账、备份和新卷恢复 | 通过；deploy-adv12-batch/verification.json |
| 恢复后的生产构建浅色/深色 | 各 3 项部署检查＋1 项双用户验收，均 0 skip/failed |
| Ruff lint/变更 Python 格式、离线锁文件、Git 空白检查 | 通过 |

仓库根执行 `web/backend/.venv/bin/python web/scripts/lab.py smoke`、`web/backend/.venv/bin/python web/scripts/lab.py verify`、`web/backend/.venv/bin/ruff check web/backend/app web/backend/tests web/backend/migrations web/scripts web/deploy`、变更 Python 文件的 `ruff format --check`、`UV_CACHE_DIR=web/.runtime/uv-cache uv lock --check --offline --directory web/backend`、`git diff --check`。`web/frontend` 执行 `pnpm generate:api`、`pnpm check:api`、`pnpm typecheck`、`pnpm test`、`pnpm build`、`pnpm format:check`、`pnpm exec playwright test --output=test-results/adv12-isolated`。本机部署使用 `web/.runtime/deploy-adv12-batch` 在 18469 端口创建并执行 `web/scripts/verify_deployment.py`，恢复后的 18470 端口分别执行浅色与深色的 `playwright.deployment.config.ts`、`playwright.acceptance.config.ts`。日志、截图和凭证保存在忽略提交的 `.runtime/` 或前端 `test-results/`。[机器证据](adv-12-verification.json)记录 310 个源码文件的指纹 `5bc2ebfd6968992d25b96e0006510c31c75cef1d16d40ac26eb67bf1322332e0`。

初次完整后端运行发现新增模块未登记在精确架构导入规则；补齐 service 与纯辅助模块别名后，345 项通过。第一次浏览器回归与生产浏览器同时清理共用 `test-results` 导致 trace 文件丢失；独占输出目录重跑 23 项通过，业务断言未放宽。一次候选快照初始化偶发失败后，定向场景连续重跑五次和完整后端套件均通过。配置文本变化不代表网络行为变化；通用前端差异视图属于 ADV-15，目前 API 可读取文件摘要和详情。

环境：Batfish revision `7d0deeeac4a09973b3876327f6aef721ee12f955`，JAR SHA-256 `0927de7c740bc72f999870e842605baad9a7cb6ea66e4b01fb9a6037bea00193`，Pybatfish `2026.9.17.3748`，Python `3.12.12`，迁移 0009。合成配置功能通过不等于现场转发一致性或规模容量证明。
