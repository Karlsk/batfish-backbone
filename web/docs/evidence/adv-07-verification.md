# ADV-07 ACL 条件搜索与无效规则接口验收

日期：2026-09-26；基线提交：`5499fa0a75`（ADV-06）。状态：ADV-07 及 MVP-01～25、ADV-01～07 累计门槛通过。

新增两个固定 SDK 问题入口：`search-filters` 在明确的设备、ACL 和 IPv4 报头范围内寻找示例流量，`filter-line-reachability` 诊断规则不可达。两者仅接受各1～10个字面设备/ACL名，拒绝表达式和任意引擎控制参数；动作仅为 permit/deny/match_line，line_number 与动作互相约束。结果保留原始 SDK 行、Flow、Trace、Blocking_Lines、Reason、来源引用。空搜索只说明当前条件下没有示例流量；`BLOCKING_LINES` 和 `INDEPENDENTLY_UNMATCHABLE` 分开返回，均不推导全网安全。Huawei/H3C 的 ACL 模型验证在提交前拒绝。

在固定版本真实引擎上构造 Cisco 四设备 ACL：放行示例 Flow 由 `testFilters` 复核动作及命中规则；后续 `deny ip any any` 遮蔽的许可规则返回 `BLOCKING_LINES`，空对象组规则返回 `INDEPENDENTLY_UNMATCHABLE` 且阻挡行为空；限制 IP 后无示例流量时返回0行和非安全结论提示。通过实际 FastAPI TestClient、数据库任务、worker执行及 SDK 查询验证，非 mock 结果。

| 检查 | 实际结果 |
| --- | --- |
| 后端完整 `lab.py verify` | 325 passed、0 skip；74e00ff42b56/checks/60affda8256b |
| 真实 API/worker `lab.py smoke` | 12 passed、313项为有意筛选；checks/788a6ab91596 |
| 前端单测、构建/类型、OpenAPI 生成一致性、格式 | 70 passed / 22 files；其余通过 |
| 两套配置浏览器全回归 | 20 passed、0 skip/failed |
| 新 HTTPS 部署、服务重启/失联对账、备份及新卷恢复 | 通过；deploy-adv07-batch/verification.json |
| 恢复后生产构建浅色/深色 | 各3项部署＋1项双用户验收，均0 skip/failed |
| Ruff lint/本篇 Python 格式、离线锁文件、Git 空白检查 | 通过 |

实际命令：在仓库根目录运行 `web/backend/.venv/bin/pytest web/backend/tests/test_filter_search.py -q`（设置 `BATFISH_LAB_MANIFEST`）、`web/backend/.venv/bin/python web/scripts/lab.py verify`、`smoke`、`web/backend/.venv/bin/ruff check web/backend/app web/backend/tests web/scripts web/deploy`、`UV_CACHE_DIR=web/.runtime/uv-cache uv lock --check --offline --directory web/backend`，以及 `deploy.py prepare/build` 与 `verify_deployment.py --state web/.runtime/deploy-adv07-batch`。在 `web/frontend` 运行 `pnpm generate:api`、`pnpm test`、`pnpm build`、`pnpm check:api`、`pnpm format:check`、`pnpm exec playwright test`，恢复后使用 `playwright.deployment.config.ts` 和 `playwright.acceptance.config.ts` 分别测试浅/深主题。原始日志、截图及凭证均留在忽略提交的 `.runtime/`；[机器证据](adv-07-verification.json)记录源码指纹 `cdbedb84e64461f1f0733082e7ae0b9d7c080527a46143837957f9903dcfbbf9`。

首轮完整后端回归的两项能力清单失败来自仍运行 ADV-06 源码的旧 API；关闭本任务旧实验环境、当前源码重启并重新播种后，完整回归325/325通过。前端并行重负载时出现5秒超时，单篇隔离与全套重跑分别9/9、70/70通过。部署浏览器最初缺少 `BFW_DEPLOYMENT_EVIDENCE` 而读取了实验环境凭证；补齐本次验证报告路径后浅/深主题与双用户均通过，未改动产品逻辑或放宽断言。

环境：Batfish revision `7d0deeeac4a09973b3876327f6aef721ee12f955`，JAR SHA-256 `0927de7c740bc72f999870e842605baad9a7cb6ea66e4b01fb9a6037bea00193`，Pybatfish `2026.9.17.3748`，Python `3.12.12`，迁移0008。只验证配置模型下的 Web 功能；未比较现场转发结果，也未做百台设备容量验证。
