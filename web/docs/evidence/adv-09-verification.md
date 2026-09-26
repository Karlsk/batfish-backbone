# ADV-09 登记式专家查询入口验收

日期：2026-09-26；基线提交：`65c0a9afde`（ADV-08）。状态：ADV-09 及 MVP-01～25、ADV-01～09 累计门槛通过。

`POST S/analyses/query` 只接收 `/capabilities` 已登记且 enabled 的能力 ID、该能力的参数对象，调用同一 AnalysisService、Registry 请求模型、任务和结果路径，不开放任意 SDK 方法或连接参数。能力目录增加完整 `parameters_schema`，专家页面按 schema 生成顶层基础字段，复杂字段及高级 options 可编辑 JSON；输入错误不丢文本，服务端错误显示到 `body.parameters...` 字段路径。基础视图显示含默认值的预计有效参数，提交时仍由服务端严格复核。

在固定版本真实引擎和 Cisco 四设备配置上，专家 `nodes` 与专用 `nodes` 的有效参数及结果 ID 一致；未登记的 `__import__`/`fileParseStatus`、`options.host`、快照覆盖及额外 `sdk_method` 均被拒绝。禁用注册项由注册表测试确认拒绝。浏览器完成错误修正、实际任务、结果对照，并检查浅色/深色页面；r1/r2 与 Cisco 四设备其余功能纳入累计回归。

| 检查 | 实际结果 |
| --- | --- |
| 后端完整 `lab.py verify` | 329 passed、0 skip；74e00ff42b56/checks/7b929e6b62c5 |
| 当前源码重启后的真实 API/worker `lab.py smoke` | 12 passed、317项为有意筛选；27c57a46ecac/checks/56ce00764109 |
| 前端完整单测、构建/类型、OpenAPI 生成一致性、格式 | 81 passed / 25 files；其余通过 |
| 两套配置浏览器全回归 | 22 passed、0 skip/failed |
| 新 HTTPS 部署、服务重启/失联对账、备份及新卷恢复 | 通过；deploy-adv09-batch/verification.json |
| 恢复后生产构建浅色/深色 | 各3项部署＋1项双用户验收，均0 skip/failed |
| Ruff lint/本篇 Python 格式、离线锁文件、Git 空白检查 | 通过 |

实际命令：仓库根执行 `web/backend/.venv/bin/python web/scripts/lab.py verify`、重启 `serve` 后执行 `seed`、`smoke`，以及 `web/backend/.venv/bin/ruff check web/backend/app web/backend/tests web/scripts web/deploy`、本篇 Python 文件 `ruff format --check`、`UV_CACHE_DIR=web/.runtime/uv-cache uv lock --check --offline --directory web/backend`、`web/backend/.venv/bin/python web/scripts/deploy.py prepare --state web/.runtime/deploy-adv09-batch --port 18463`、`deploy.py build`、`web/backend/.venv/bin/python web/scripts/verify_deployment.py --state web/.runtime/deploy-adv09-batch`。`web/frontend` 执行 `pnpm generate:api`、`pnpm test`、`pnpm build`、`pnpm check:api`、`pnpm format:check`、`pnpm exec playwright test`；恢复后设置正确的 `BFW_DEPLOYMENT_STATE`、`BFW_DEPLOYMENT_EVIDENCE`，在 `BFW_TEST_THEME=light/dark` 下分别执行 `playwright.deployment.config.ts`、`playwright.acceptance.config.ts`。原始日志、截图和凭证留在忽略提交的 `.runtime/` 或前端 `test-results/`；[机器证据](adv-09-verification.json)记录296个源码文件指纹 `8cb8d8257155ff0fa65661022c49c33a34dd6e66e00de30c313b3392afe2d37c`。

首次完整前端测试在默认高并发下，既有 ACL 页面测试触发5秒超时；单文件9/9通过，将 Vitest 最大 worker 限制为2后完整81/81通过。JSON 编辑修正后旧错误提示残留由新增失败测试复现，清除错误状态后定向组件及浏览器通过，最终完整浏览器22/22通过。没有放宽业务断言。生产构建仍有现存大于500 kB 的共享包提示，但构建与页面检查通过。

环境：Batfish revision `7d0deeeac4a09973b3876327f6aef721ee12f955`，JAR SHA-256 `0927de7c740bc72f999870e842605baad9a7cb6ea66e4b01fb9a6037bea00193`，Pybatfish `2026.9.17.3748`，Python `3.12.12`，迁移0008。只验证已登记的11项分析入口；复杂嵌套字段需要专家 JSON 输入。合成配置结果不等于现场转发实测，也不证明百台设备容量。
