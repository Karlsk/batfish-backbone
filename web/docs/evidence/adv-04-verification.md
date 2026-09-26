# ADV-04 BGP 会话页面验收

日期：2026-09-26；基线提交：`a12256d55d`（ADV-03）。状态：ADV-04 及 MVP-01～25、ADV-01～04 累计门槛通过。

独立 BGP 入口默认只要求选择已有网络与快照，可选本地/远端设备高级筛选；状态与兼容性各提交独立任务。会话首层展示双端设备、远端地址和原始状态，精确状态过滤由结果 API 执行。点击本地设备查看接口、VRF、AS、地址族及原始 SDK 属性；有远端设备时可查询双方路由，未知远端保留“远端未知”且无虚假链接。路由导航先恢复结果固定快照；模型非实时提示和快照诊断入口常驻。

浏览器使用真实 Batfish/Pybatfish 和配置文件：Cisco 四设备生成同 AS 与错配会话，验证 `NOT_COMPATIBLE` 筛选、详情、路由与兼容性结果分离；Huawei/H3C 两设备空会话保留未建模说明。深浅主题截图已检查；发现原始 `Ip` 对象曾显示 JSON、详情入口在结果窄栏需要横向滚动，修正后重跑全部相关检查。

| 检查 | 实际结果 |
| --- | --- |
| 后端完整 `lab.py verify` | 314 passed、0 skip；9ab34410fb11/checks/5aa98153ea9b |
| 实际 HTTP/worker `lab.py smoke` | 12 passed、302为有意筛选；checks/ed52382096eb |
| 前端单测、类型/构建、OpenAPI 生成一致性、格式 | 58 passed / 20 files；其余通过 |
| 两套配置浏览器全回归 | 18 passed、0 skip/failed/flaky；9ab34410fb11 |
| 新 HTTPS 部署、服务重启/失联对账、备份和新卷恢复 | 通过；deploy-adv04-batch/verification.json |
| 恢复后生产构建浅色/深色 | 各3项部署＋1项双用户验收，均0 skip/failed/flaky |
| Ruff、离线锁文件、Markdown链接、Git空白检查 | 通过 |

实际命令：在仓库根目录执行 `web/backend/.venv/bin/python web/scripts/lab.py verify`、`web/backend/.venv/bin/python web/scripts/lab.py smoke`、`web/backend/.venv/bin/ruff check web/backend/app web/backend/tests web/scripts`、`UV_CACHE_DIR=web/.runtime/uv-cache uv lock --check --offline --directory web/backend`、`web/backend/.venv/bin/python web/scripts/deploy.py prepare --state web/.runtime/deploy-adv04-batch --port 18453`、`web/backend/.venv/bin/python web/scripts/deploy.py build --state web/.runtime/deploy-adv04-batch` 和 `web/backend/.venv/bin/python web/scripts/verify_deployment.py --state web/.runtime/deploy-adv04-batch`；在 `web/frontend` 执行 `pnpm test`、`pnpm build`、`pnpm check:api`、`pnpm format:check`、`pnpm exec playwright test`。恢复后的生产检查分别用 `playwright.deployment.config.ts`、`playwright.acceptance.config.ts` 在 `BFW_TEST_THEME=light/dark` 下运行。原始结果与截图保留在忽略提交的 `web/.runtime/`；[机器证据](adv-04-verification.json)包含源码指纹 `c0e6dd772dc1ec8b6f266be4d94c1e9518cf18fd33e85d85bbac948e81ff8e62`。

环境：Batfish revision `7d0deeeac4a09973b3876327f6aef721ee12f955`，JAR SHA-256 `0927de7c740bc72f999870e842605baad9a7cb6ea66e4b01fb9a6037bea00193`，Pybatfish `2026.9.17.3748`，Python `3.12.12`，迁移0008。验证限于配置模型功能，不宣称现场 BGP 健康、Huawei/H3C IPv6 会话覆盖或百台设备容量。
