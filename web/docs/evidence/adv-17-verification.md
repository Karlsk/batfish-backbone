# ADV-17 故障模拟向导验收

日期：2026-09-27；基线提交：`118fcdfda8`（ADV-16）。状态：ADV-17 及 MVP-01～25、ADV-01～17 累计门槛通过。

故障向导在 `/faults` 选择就绪基线，以现有节点分析读取候选，预览停用设备/接口与不可变派生关系。双击只发出一份带固定幂等键的创建请求；任务失败、引擎未知、快照未就绪时没有“进入影响分析”链接。就绪并带警告时显示质量提示与诊断入口。比较页预填原始基线和派生快照，仍须手动创建比较并填写分析范围。页面只调用 Web API，不接触 SDK 或真实设备。

| 检查 | 本轮结果 |
| --- | --- |
| 隔离 Batfish/PostgreSQL 后端全量回归 | 368 passed、0 failed/skip；`8a53df3cb24f/checks/c65c13f060fc` |
| r1/r2 与 Cisco 四设备真实 API/worker 冒烟 | 13 passed、355 项按 smoke 标记有意筛选；`8a53df3cb24f/checks/7c4ece5e7497` |
| 前端单测、类型/构建、OpenAPI 与格式 | 92 passed / 27 files；其余通过 |
| 两拓扑及新增故障向导真实浏览器回归 | 25 passed、0 skip/failed；`adv17-final` |
| 故障向导真实四台 Cisco 流程与明暗截图 | 上传/初始化、读取候选、派生就绪、原始基线方向和手动范围门槛通过；截图在 `adv17-final` |
| 新 HTTPS 部署、重启/失联对账、备份和新卷恢复 | 通过；`deploy-adv17-batch/verification.json` |
| 恢复后生产构建浅色/深色 | 各 3 项部署检查＋1 项双用户验收，均 0 skip/failed |
| Ruff、离线锁文件与 Git 空白检查 | 通过 |

仓库根执行 `web/backend/.venv/bin/python web/scripts/lab.py seed/smoke/verify`、`web/backend/.venv/bin/ruff check web/backend web/scripts web/deploy`、`UV_CACHE_DIR=web/.runtime/uv-cache uv lock --check --offline --directory web/backend` 与 `git diff --check`。`web/frontend` 执行 `pnpm test`、`pnpm check:api`、`pnpm typecheck`、`pnpm build`、`pnpm format:check`、`pnpm exec playwright test --output=test-results/adv17-final`。新部署 `web/.runtime/deploy-adv17-batch` 使用 18479 端口，`web/scripts/verify_deployment.py` 在 18480 端口恢复；用 `playwright.deployment.config.ts` 与 `playwright.acceptance.config.ts` 分别检查浅色和深色。首次生产浏览器命令漏传 `BFW_DEPLOYMENT_EVIDENCE`，前两项因此失败；补齐参数后各项全通过，未修改产品断言。原始日志、截图及测试凭证留在忽略提交的 `.runtime/` 或 `test-results/`。[机器证据](adv-17-verification.json)绑定 329 个源码文件的指纹 `7eb58b4539809b094e1ba7949e6835ee19e532ccf876c829e83d5646353db225`。

环境：Batfish revision `7d0deeeac4a09973b3876327f6aef721ee12f955`，JAR SHA-256 `0927de7c740bc72f999870e842605baad9a7cb6ea66e4b01fb9a6037bea00193`，Pybatfish `2026.9.17.3748`，Python `3.12.12`，迁移 `0010`。结论针对合成配置和 Web 功能；不对照现场路由或转发，不据此声称 Java 引擎仿真精度。
