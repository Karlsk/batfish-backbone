# 第三阶段整体验收（ADV-18）

日期：2026-09-27。**结论：通过。**MVP-01～25、ADV-01～18 的累计门槛在同一版源码上通过；阶段三的结论仅针对合成配置、Web 工作流和固定版本 Batfish 模型。

## 固定快照对与直接 SDK 对照

隔离测试在 Cisco 四设备配置上建立一对不可变快照：基线 `c1` 有 `198.51.100.0/24` 静态路由，候选改为 `203.0.113.0/24`，并用 ACL 阻断从 `c1` 到 `10.64.0.4` 的 ICMP。比较记录固定基线与候选、引擎和 SDK 版本。配置差异只指向 `configs/c1.cfg`，两侧文件 SHA-256 对应上传原始字节，详情包含候选静态路由文本和从 1 开始的源行号。路由结果标出前一前缀“候选消失”、后一前缀“候选新增”，行中的网络与存在方向和同一快照对的公开 SDK `routes` 差异答案一致。限定起点、源/目的地址和 ICMP 后，差异可达性为“候选消失”，双侧 trace 与公开 SDK `differentialReachability` 答案一致。该查询的计数是 SDK 给出的见证行数，不是所有业务流数量；本例未截断。

从原始基线停用 `c2` 派生故障快照后，派生记录仍引用原始基线，原始快照的 Web 元数据和公开 SDK 设备行保持原样。受控失败的第二次派生任务进入 `failed`，失败快照不能建立比较，原始基线仍不变。浏览器从已知快照对完成配置、路由、可达性查看，再创建故障派生；交接到比较页仍以原始基线为左侧，并要求用户显式填写分析范围。该流程没有对真实设备下发操作。

## 累计与恢复门槛

| 检查 | 结果 |
| --- | --- |
| 隔离 Batfish/PostgreSQL 后端全量回归 | 369 passed，0 failed/skip；`8a53df3cb24f/checks/ce089ab85209` |
| r1/r2 与 Cisco 四设备真实 API/worker 冒烟 | 13 passed；356 项按 smoke 标记有意筛选；`8a53df3cb24f/checks/29c115278d8e` |
| 前端单测、OpenAPI 类型、类型检查、构建和格式 | 92 passed / 27 files；其余通过 |
| 两拓扑及阶段三固定双快照真实浏览器回归 | 26 passed，0 failed/skip；`adv18-final` |
| 全新 HTTPS 部署与新卷恢复 | 两套快照、API 重启、worker 失联及未知状态栅栏、显式对账、备份和原结果/新查询恢复均通过；`deploy-adv18-batch/verification.json` |
| 恢复后生产构建明暗主题与双用户 | 每个主题 3 项部署浏览器 + 1 项双用户验收，全部通过 |
| Ruff、离线锁文件及 Git 空白检查 | 通过 |

后端在仓库根以 `web/backend/.venv/bin/python web/scripts/lab.py verify`、`lab.py smoke` 验证；前端在 `web/frontend` 以 `pnpm test`、`pnpm check:api`、`pnpm typecheck`、`pnpm build`、`pnpm format:check`、`pnpm exec playwright test --output=test-results/adv18-final` 验证。新部署使用 `web/backend/.venv/bin/python web/scripts/verify_deployment.py --state web/.runtime/deploy-adv18-batch`，恢复后的生产检查以 `playwright.deployment.config.ts` 和 `playwright.acceptance.config.ts` 分别运行 light/dark。直接 SDK 对照的结果 ID、快照 ID 和版本保存在忽略提交的 `web/.runtime/test-lab/8a53df3cb24f/acceptance/phase3-af5cc41239b94b28af0c046c96ebdcb8.json`；原始日志、截图、凭证也留在本地忽略目录。可提交的[机器证据](evidence/adv-18-verification.json)绑定 331 个源码文件的指纹 `c8e2d001008326e7cb06012ad389a8378adbf9ffd3b73e5b5e71acebfd0f14fa`。

环境：Batfish revision `7d0deeeac4a09973b3876327f6aef721ee12f955`，JAR SHA-256 `0927de7c740bc72f999870e842605baad9a7cb6ea66e4b01fb9a6037bea00193`，引擎 `0.36.0`，Pybatfish `2026.9.17.3748`，Python `3.12.12`，迁移 `0010`。现有范围内的空结果、模型提示、截断、权限、失败重试、删除引用保护由累计测试覆盖；本次固定流样例未截断，也不能据此推断任意流都可达或不可达。没有使用真实设备或现场结果，因此不声称 Java 引擎仿真精度，也不声称 SDK 全能力适配或约 100 台设备的容量已验证。
