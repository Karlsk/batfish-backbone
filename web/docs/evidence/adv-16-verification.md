# ADV-16 节点与接口故障派生验收

日期：2026-09-27；基线提交：`0e202fa9d1`（ADV-15）。状态：ADV-16 及 MVP-01～25、ADV-01～16 累计门槛通过。

新增 `POST S/fault-scenarios`：输入方案名以及要停用的设备/接口；服务端对真实快照清单做精确存在性校验，使用全新内部名称登记派生关系与持久任务。独立 worker 调用公开 `fork_snapshot(overwrite=False)`，按普通快照的解析诊断和质量门验收；完成前或失败时不能创建 comparison。派生快照保留 `base_snapshot_id`，未删除的派生快照阻止删除基线，同一资源锁保证创建/删除不会交错。已登记的幂等请求在引擎忙时也能取回原任务，不同内容复用键返回409；未知对象422，忙/未知引擎返回可解释的503。

| 检查 | 结果 |
| --- | --- |
| 隔离 Batfish/PostgreSQL 后端全量回归 | 368 passed、0 failed/skip；`c66c07011826/checks/ddf89a252dd9` |
| ADV-16 真实 SDK 故障与分层目标回归 | 62 passed，包括 SDK 未确认 fork、引擎忙/未知、幂等、基线不变、并发删除 |
| 迁移 0010、r1/r2 与 Cisco 四设备真实 API/worker 冒烟 | 13 passed、355 项按 smoke 标记有意筛选；`8a53df3cb24f/checks/a9ecd6b3b17d` |
| ADV-16 独立 HTTP/worker 流程 | 未知节点422；节点＋接口派生 ready；重复请求返回原资源；基线删除409；comparison 201 |
| 前端单测、类型/构建、OpenAPI 与格式 | 87 passed / 26 files；其余通过 |
| 两拓扑及已有技术工作台浏览器回归 | 24 passed、0 skip/failed；`adv16-cumulative` |
| 新 HTTPS 部署、重启/失联对账、备份和新卷恢复 | 通过；`deploy-adv16-batch/verification.json` |
| 恢复后生产构建浅色/深色 | 各 3 项部署检查＋1 项双用户验收，均 0 skip/failed |
| Ruff、离线锁文件与 Git 空白检查 | 通过 |

仓库根执行 `web/backend/.venv/bin/python web/scripts/lab.py verify/seed/smoke`、`web/backend/.venv/bin/ruff check web/backend web/scripts web/deploy`、变更 Python 文件格式检查、`UV_CACHE_DIR=web/.runtime/uv-cache uv lock --check --offline --directory web/backend` 和 `git diff --check`。`web/frontend` 执行 `pnpm test`、`pnpm check:api`、`pnpm typecheck`、`pnpm build`、`pnpm format:check`、`pnpm exec playwright test --output=test-results/adv16-cumulative`。本机 HTTPS 部署使用 `web/.runtime/deploy-adv16-batch` 的 18477 端口构建并运行 `web/scripts/verify_deployment.py`；恢复后的 18478 端口分别执行明暗主题的 `playwright.deployment.config.ts` 与 `playwright.acceptance.config.ts`。原始日志、截图及测试凭证保留在忽略提交的 `.runtime/` 或 `test-results/`。[机器证据](adv-16-verification.json)绑定 326 个源码文件的指纹 `88654652bbe5e1fbbf77bd70560b688d5d5bdfffbd499639c4da7ff00802b69e`。

首次全量回归的唯一失败是新增模块未被分层静态检查识别；将新文件登记为 service 层并把跨模块快照返回类型移入公共契约后，目标分层检查与最终全量通过。SDK 返回 None 的新增测试先复现了“中断/未知”误分类，随后将确定性失败放在独占 SDK 会话退出后处理。首次前端单测与构建并发运行时有两个既有 ACL 用例超时/交互失败，单独重跑 87/87 通过。首次独立 HTTP 故障请求遇到可重试的引擎忙 503，客户端按该状态重试后完成；未改变产品断言。

环境：Batfish revision `7d0deeeac4a09973b3876327f6aef721ee12f955`，JAR SHA-256 `0927de7c740bc72f999870e842605baad9a7cb6ea66e4b01fb9a6037bea00193`，Pybatfish `2026.9.17.3748`，Python `3.12.12`，迁移 `0010`。故障方案只修改模型快照，不触碰真实设备；比较结论仍限于当前模型与明确填写的分析范围。
