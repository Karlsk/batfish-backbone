# ADV-06 ACL 流量测试页面验收

日期：2026-09-26；基线提交：`3cb6198900`（ADV-05）。状态：ADV-06 及 MVP-01～25、ADV-01～06 累计门槛通过。

技术工作台现在有独立 ACL 入口。设备和已解析 ACL 候选均绑定固定网络/快照；基础表单仅显示设备、ACL、源/目的 IPv4，高级协议、端口和表达式折叠但不丢值。结果按局部动作、命中内容、实际 Flow/来源引用与原始 SDK 证据逐级展示。隐式拒绝没有虚构规则行；无匹配或截断结果不显示为放行，Huawei/H3C 的不支持反馈明确可见。路径分析从结果固定快照预填流量，仍要求用户选择起点。

浏览器使用真实 Batfish/Pybatfish 和两套合成配置。Cisco ACL 样本验证候选解析、PERMIT、隐式 DENY、来源引用、详情及路径预填；Huawei/H3C 样本验证模型不支持。浅色和深色结果截图已检查，表格、提示与详情可读。全量浏览器首轮 18/20：原有分析脚本在路由未切换完就提交，实际请求落在 `nodes`；在 `tests/analysis.spec.ts` 增加目标 URL/表单/任务/结果就绪等待后，受影响两套拓扑 2/2、全量 20/20 通过，未改产品路由或放宽业务断言。

| 检查 | 实际结果 |
| --- | --- |
| 后端完整 `lab.py verify` | 318 passed、0 skip；27ddf5674935/checks/175225443c36 |
| 实际 HTTP/worker `lab.py smoke` | 12 passed、306为有意筛选；checks/b63f77eb8815 |
| 前端单测、类型/构建、OpenAPI 生成一致性、格式 | 70 passed / 22 files；其余通过 |
| 两套配置浏览器全回归 | 20 passed、0 skip/failed/flaky；27ddf5674935 |
| 新 HTTPS 部署、服务重启/失联对账、备份和新卷恢复 | 通过；deploy-adv06-batch/verification.json |
| 恢复后生产构建浅色/深色 | 各3项部署＋1项双用户验收，均0 skip/failed/flaky |
| Ruff lint、离线锁文件、Markdown链接、Git空白检查 | 通过 |

实际命令：在仓库根目录执行 `web/backend/.venv/bin/python web/scripts/lab.py verify`、`web/backend/.venv/bin/python web/scripts/lab.py smoke`、`web/backend/.venv/bin/ruff check web/backend/app web/backend/tests web/scripts`、`UV_CACHE_DIR=web/.runtime/uv-cache uv lock --check --offline --directory web/backend`、`web/backend/.venv/bin/python web/scripts/deploy.py prepare --state web/.runtime/deploy-adv06-batch --port 18457`、`build` 及 `web/backend/.venv/bin/python web/scripts/verify_deployment.py --state web/.runtime/deploy-adv06-batch`；在 `web/frontend` 执行 `pnpm test`、`pnpm build`、`pnpm check:api`、`pnpm format:check`、`pnpm exec playwright test`。恢复后的生产检查分别用 `playwright.deployment.config.ts`、`playwright.acceptance.config.ts` 在 `BFW_TEST_THEME=light/dark` 下运行。原始结果与截图保留在忽略提交的 `web/.runtime/`；[机器证据](adv-06-verification.json)包含源码指纹 `0921b327b9062959dd782118a558b310adc55f3c94d8262f1d36c0a842f76be7`。

环境：Batfish revision `7d0deeeac4a09973b3876327f6aef721ee12f955`，JAR SHA-256 `0927de7c740bc72f999870e842605baad9a7cb6ea66e4b01fb9a6037bea00193`，Pybatfish `2026.9.17.3748`，Python `3.12.12`，迁移0008。额外执行的全仓 `ruff format --check` 仍提示两份未修改的既有文件（`test_sdk_baseline.py`、`lab.py`）排版差异；本篇无 Python 修改，必需的 Ruff lint 通过。未做现场转发一致性或百台设备容量验证。
