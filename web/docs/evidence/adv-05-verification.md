# ADV-05 ACL 流量测试接口验收

日期：2026-09-26；基线提交：`4fc9780e92`（ADV-04）。状态：ADV-05 及 MVP-01～25、ADV-01～05 累计门槛通过。

两个新入口固定映射 Pybatfish `testFilters` 和 `resolveFilterSpecifier`。最小流量输入为源/目的 IPv4 与 ACL 选择器，节点可选，协议及端口置于类型化高级选项。Cisco 合成配置验证放行、显式拒绝及隐式拒绝，动作、规则内容、Flow、Trace 与固定 SDK 的原始结果逐项对照。额外来源引用只取实际 Trace 的 `vendorStructureId`；隐式拒绝没有虚构配置行。无匹配 ACL 保留无结论，Huawei/H3C ACL 验证拒绝提交。真实 FastAPI 与独立 worker 的 Cisco ACL 试运行返回 DENY、实际来源引用及已解析 ACL。

| 检查 | 实际结果 |
| --- | --- |
| 后端完整 `lab.py verify` | 318 passed、0 skip；27ddf5674935/checks/549143de1f00 |
| 实际 HTTP/worker `lab.py smoke` | 12 passed、306为有意筛选；checks/0ab1fb0b76c6 |
| 新 ACL SDK 对照、权限和参数测试 | `test_filters.py` 全通过，覆盖三种动作、空匹配、解析辅助、厂商限制及 TCP 端口 |
| 前端单测、类型/构建、OpenAPI 生成一致性、格式 | 58 passed / 20 files；其余通过 |
| 两套配置浏览器全回归 | 18 passed、0 skip/failed/flaky；27ddf5674935 |
| 新 HTTPS 部署、服务重启/失联对账、备份和新卷恢复 | 通过；deploy-adv05-batch/verification.json |
| 恢复后生产构建浅色/深色 | 各3项部署＋1项双用户验收，均0 skip/failed/flaky |
| Ruff、离线锁文件、Markdown链接、Git空白检查 | 通过 |

实际命令：在仓库根目录执行 `web/backend/.venv/bin/python web/scripts/lab.py verify`、`web/backend/.venv/bin/python web/scripts/lab.py smoke`、`web/backend/.venv/bin/ruff check web/backend/app web/backend/tests web/scripts`、`web/backend/.venv/bin/ruff format --check web/backend/app web/backend/tests web/scripts`、`UV_CACHE_DIR=web/.runtime/uv-cache uv lock --check --offline --directory web/backend`、`web/backend/.venv/bin/python web/scripts/deploy.py prepare --state web/.runtime/deploy-adv05-batch --port 18455`、`web/backend/.venv/bin/python web/scripts/deploy.py build --state web/.runtime/deploy-adv05-batch` 和 `web/backend/.venv/bin/python web/scripts/verify_deployment.py --state web/.runtime/deploy-adv05-batch`；在 `web/frontend` 执行 `pnpm test`、`pnpm build`、`pnpm check:api`、`pnpm format:check`、`pnpm exec playwright test`。恢复后的生产检查分别用 `playwright.deployment.config.ts`、`playwright.acceptance.config.ts` 在 `BFW_TEST_THEME=light/dark` 下运行。原始结果保留在忽略提交的 `web/.runtime/`；[机器证据](adv-05-verification.json)包含源码指纹 `1f466de74787e7a0ab6c128fd47008b621ea67f8728e8bbfdbc7ab084d843ace`。

环境：Batfish revision `7d0deeeac4a09973b3876327f6aef721ee12f955`，JAR SHA-256 `0927de7c740bc72f999870e842605baad9a7cb6ea66e4b01fb9a6037bea00193`，Pybatfish `2026.9.17.3748`，Python `3.12.12`，迁移0008。只验证配置模型下的 ACL 局部动作，不证明端到端可达、现场转发或百台设备容量。ADV-06 可继续。
