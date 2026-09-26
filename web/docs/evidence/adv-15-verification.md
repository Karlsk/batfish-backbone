# ADV-15 变更对比工作台验收

日期：2026-09-27；基线提交：`23e19dfe79`（ADV-14）。状态：ADV-15 及 MVP-01～25、ADV-01～15 累计门槛通过。

技术工作台新增“变更对比”：同一网络内选两份就绪快照，比较记录固定基线在左、候选在右；草稿交换不改已有比较。配置变化按文件列出，点击后才读取双侧行差异；路由按候选新增/消失及两侧下一跳展示；可达性必须先填写目的范围和起点，再显示同一 Flow 的双侧路径。摘要先呈现模型覆盖、警告、截断与范围，原始行在详情中查看。历史结果可通过结果编号重新打开。

浏览器使用合成 Cisco 四设备的两份真实快照：基线有静态路由 `198.51.100.0/24`，候选改为 `203.0.113.0/24` 并在 c1 出向 ACL 拒绝到 c4 的流量。页面实际显示配置文本差异、路由新增/消失，以及基线可达而候选不可达的 Flow 和两侧 Trace。空结果只描述所选条件，版本不兼容与计算失败分别解释。深浅主题截图保存在忽略提交的浏览器测试目录。

| 检查 | 结果 |
| --- | --- |
| 隔离 Batfish/PostgreSQL 完整后端回归 | 358 passed、0 skip；`c66c07011826/checks/bd8092e977de` |
| 真实 API/独立 worker 冒烟 | 13 passed、345 项按 smoke 标记有意筛选；`c66c07011826/checks/e8906bbc0fb3` |
| 前端单测、类型/构建、OpenAPI 与格式 | 87 passed / 26 files；其余通过 |
| r1/r2、Cisco 四设备及新对比页浏览器全回归 | 24 passed、0 skip/failed；`adv15-final-rerun` |
| 新 HTTPS 部署、重启/失联对账、备份和新卷恢复 | 通过；`deploy-adv15-batch/verification.json` |
| 恢复后生产构建浅色/深色 | 各 3 项部署检查＋1 项双用户验收，均 0 skip/failed |
| Ruff、离线锁文件与 Git 空白检查 | 通过 |

仓库根执行 `web/backend/.venv/bin/python web/scripts/lab.py seed/verify/smoke`、全量 Ruff lint、变更 Python 文件格式检查、`UV_CACHE_DIR=web/.runtime/uv-cache uv lock --check --offline --directory web/backend` 和 `git diff --check`。`web/frontend` 执行 `pnpm test`、`pnpm check:api`、`pnpm typecheck`、`pnpm build`、`pnpm format:check`、`pnpm exec playwright test --output=test-results/adv15-final-rerun`。本机部署使用 `web/.runtime/deploy-adv15-batch` 的 18475 端口构建并运行 `web/scripts/verify_deployment.py`；恢复后的 18476 端口分别运行明暗主题的 `playwright.deployment.config.ts` 和 `playwright.acceptance.config.ts`。原始日志、截图与测试凭证保留在忽略提交的 `.runtime/` 或 `test-results/`。[机器证据](adv-15-verification.json)绑定 321 个源码文件的指纹 `d9e8d61b23d555ad1ccdf64154a589fe9906e018af6d91e40a754f6c41d8ff97`。

首次全套浏览器为 23/24：旧专家查询页在快照初始化期间读到跨事务状态竞态，将随后成功的任务暂显为“初始化失败”并停止轮询。新增 `test_succeeded_job_does_not_make_earlier_queued_snapshot_read_look_failed` 先复现失败，后端修复为在这种读偏斜下继续显示“初始化中”；受控环境重启后，目标用例及整套 24/24 均通过。首次生产浏览器命令漏传 `BFW_DEPLOYMENT_EVIDENCE`，脚本按预期拒绝运行；补齐已生成报告路径后明暗主题全通过。没有放宽产品断言。

环境：Batfish revision `7d0deeeac4a09973b3876327f6aef721ee12f955`，JAR SHA-256 `0927de7c740bc72f999870e842605baad9a7cb6ea66e4b01fb9a6037bea00193`，Pybatfish `2026.9.17.3748`，Python `3.12.12`，迁移 0009。对比结果说明当前模型和填写范围内的差异；不能据此断言现场转发、回程或全部业务流影响。共享构建大于 500 kB 的提示不影响构建和页面验收。
