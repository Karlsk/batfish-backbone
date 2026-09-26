# ADV-08 ACL 高级诊断页面验收

日期：2026-09-26；基线提交：`ad36950fd8`（ADV-07）。状态：ADV-08 及 MVP-01～25、ADV-01～08 累计门槛通过。

ACL 页面增加“条件搜索”和“规则诊断”标签，三个表单草稿独立。能力目录控制入口可用性与默认值，表单以生成的 OpenAPI 类型构造请求，并在提交前限制设备/ACL 为各最多10个字面名称。请求进行中或状态未知时，其他标签禁用，保留幂等请求标识和原参数。结果按查询范围、结论、逐行证据、原始 SDK 行展开；无搜索样本、截断和缺少阻挡证据不会推断安全或虚构遮蔽链。搜索得到的 Flow 可带原协议、IP 和端口进入 ACL 流量测试，且回到原结果所属网络/快照。

真实浏览器在 Cisco 四设备配置副本中创建 WEB-SEARCH ACL，搜索 TCP 12345→443 示例 Flow、查看证据、回测局部放行，再诊断出 `BLOCKING_LINES` 与 `INDEPENDENTLY_UNMATCHABLE` 两种不同原因并打开原始证据。浅色与深色截图均检查了范围、提示、表格和证据层级。复用的 r1/r2 与 Cisco 四设备全套测试通过；没有使用现场设备。

| 检查 | 实际结果 |
| --- | --- |
| 后端完整 `lab.py verify` | 325 passed、0 skip；74e00ff42b56/checks/ff5f186912b4 |
| 真实 API/worker `lab.py smoke` | 12 passed、313项为有意筛选；checks/151392355a85 |
| 前端完整单测、构建/类型、OpenAPI 生成一致性、格式 | 78 passed / 24 files；其余通过 |
| 两套配置浏览器全回归 | 21 passed、0 skip/failed |
| 新 HTTPS 部署、服务重启/失联对账、备份及新卷恢复 | 通过；deploy-adv08-batch/verification.json |
| 恢复后生产构建浅色/深色 | 各3项部署＋1项双用户验收，均0 skip/failed |
| Ruff lint、离线锁文件、Git 空白检查 | 通过 |

实际命令：仓库根运行 `web/backend/.venv/bin/python web/scripts/lab.py status/verify/smoke`、`web/backend/.venv/bin/ruff check web/backend/app web/backend/tests web/scripts web/deploy`、`UV_CACHE_DIR=web/.runtime/uv-cache uv lock --check --offline --directory web/backend`、`web/backend/.venv/bin/python web/scripts/deploy.py prepare/build --state web/.runtime/deploy-adv08-batch`（prepare 使用端口18461）及 `web/backend/.venv/bin/python web/scripts/verify_deployment.py --state web/.runtime/deploy-adv08-batch`。`web/frontend` 运行 `pnpm test`、`pnpm build`、`pnpm check:api`、`pnpm format:check`、`pnpm exec playwright test`；恢复后设置 `BFW_DEPLOYMENT_STATE` 和 `BFW_DEPLOYMENT_EVIDENCE`，在 `BFW_TEST_THEME=light/dark` 下分别运行 `playwright.deployment.config.ts` 和 `playwright.acceptance.config.ts`。原始日志、截图及凭证保存在忽略提交的 `.runtime/` 或前端 `test-results/`；[机器证据](adv-08-verification.json)记录290个源码文件的指纹 `1b8083300d8b7f7c2d15974981c1f50f5de84d1031efbbe57a98031677b79057`。

测试先复现提交未返回时可以切走标签的问题，修复后定向测试17/17、完整前端78/78通过。真实浏览器初次检查发现隐藏标签同时注册路由拦截器；将草稿保存在标签父层且仅挂载当前标签后，完整浏览器21/21通过，无该警告。仓库级 `ruff format --check` 仍报告未改动的 `test_sdk_baseline.py` 和 `lab.py` 两处既有格式差异，本篇没有 Python 改动；Ruff lint 通过。前端生产构建仍提示现有共享包超过500 kB，功能和浏览器门槛通过。

环境：Batfish revision `7d0deeeac4a09973b3876327f6aef721ee12f955`，JAR SHA-256 `0927de7c740bc72f999870e842605baad9a7cb6ea66e4b01fb9a6037bea00193`，Pybatfish `2026.9.17.3748`，Python `3.12.12`，迁移0008。只验证配置模型下的 Web 功能；未比较现场转发结果，也未做百台设备容量验证。
