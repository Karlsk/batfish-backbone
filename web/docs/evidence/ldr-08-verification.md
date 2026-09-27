# LDR-08 ADV 引导检查验收

日期：2026-09-28；基线提交 `277e9f8e97`（LDR-07）。隔离环境运行 ID `8a53df3cb24f`；Batfish revision `7d0deeeac4a09973b3876327f6aef721ee12f955`、Pybatfish `2026.9.17.3748`、Python `3.12.12`。真实配置均为合成样例，无真实设备。

| 检查 | 结果 |
| --- | --- |
| 目标单测 | `web/frontend` 执行 `pnpm exec vitest run src/features/leader/checks/advanced.test.ts src/features/leader/checks/model.test.ts`：10 passed；覆盖拓扑来源/范围、BGP 模型状态与分页、ACL permit/显式 deny/隐式 deny/无匹配/截断、必填流量和有界设备选择。 |
| 前端全量 | `web/frontend` 执行 `pnpm check:api && pnpm test && pnpm build && pnpm format:check`：OpenAPI 契约一致、108 passed、TypeScript 与生产构建通过、格式通过。构建仍有已有的大包体积提示，不视为容量验收。 |
| 真实浏览器 | `python3 /private/tmp/ldr03-run.py tests/leader-advanced-checks.spec.ts tests/leader-mvp-checks.spec.ts tests/leader-checks-api.spec.ts tests/leader-overview.spec.ts tests/leader-entry.spec.ts tests/leader-concerns.spec.ts tests/auth-users.spec.ts`：17 passed。当前源码 API、独立 worker、隔离 PostgreSQL/Batfish；覆盖 LDR-01～08 与原用户管理回归。 |
| 固定拓扑 | 已就绪 Cisco 四设备快照生成 4 台设备、8 条三层模型关系；可聚焦 c1 的一跳邻域，结论标明配置推导、模型来源与覆盖未知，不声称物理连接。Chromium 全页截图位于忽略提交的 `web/frontend/test-results/leader-advanced-checks-lea-5cbae-nd-a-focused-saved-topology-chromium/leader-topology.png`，已目视检查。 |
| BGP/ACL 真实行为 | 浏览器上传派生 Cisco 四设备配置，在同一快照增加 BGP AS 错配与 `WEB-TEST` ACL，经领导端检查及真实 worker 得到 `NOT_COMPATIBLE`、指定 ICMP 流量的局部 permit、显式 deny、隐式 deny。无匹配与分页/截断语义由目标单测验证。 |
| 后端与限制 | 本篇未改后端；LDR-06 固定引擎的全量 385 passed、LDR-07 的 13 项冒烟基线继续适用。未知专家问题仍由既有登记式 API 拒绝；领导端只列服务端返回的能力，不提供任意提交入口。`git diff --check` 通过。 |

初次新增浏览器用例曾因总览分页未包含新建网络、随后因快照名称定位不唯一而失败；改用页面已选择的快照及精确定位后，整组 17 项重跑通过。这两次是测试定位问题，未改写产品行为。此前截图的 `NOT_READY` 缺少原请求上下文，仍不能断言与该次故障相同；可见错误与重试在累计浏览器用例中通过。验收不证明真实设备转发或 Java 仿真精度。
