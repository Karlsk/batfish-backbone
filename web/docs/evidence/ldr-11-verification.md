# LDR-11 固定汇报页面验收

日期：2026-09-28；基线提交 `d0e9104a70`（LDR-10）。隔离环境运行 ID `84a19621afb6`；Batfish revision `7d0deeeac4a09973b3876327f6aef721ee12f955`，JAR SHA-256 `0927de7c740bc72f999870e842605baad9a7cb6ea66e4b01fb9a6037bea00193`，Pybatfish `2026.9.17.3748`，Python `3.12.12`，迁移 `0013`。

| 检查 | 结果 |
| --- | --- |
| 前端契约/单测/构建 | `web/frontend` 运行 `pnpm check:api`、`pnpm test`、`pnpm typecheck`、`pnpm build`、`pnpm format:check`：OpenAPI 一致，119 passed，类型、生产构建和格式通过。构建保留既有大包体积提示。目标模型测试 4 passed。 |
| 真实浏览器累计 | `web/frontend` 运行 `python3 /private/tmp/ldr03-run.py tests/leader-changes.spec.ts tests/leader-advanced-checks.spec.ts tests/leader-mvp-checks.spec.ts tests/leader-checks-api.spec.ts tests/leader-overview.spec.ts tests/leader-entry.spec.ts tests/leader-concerns.spec.ts tests/auth-users.spec.ts tests/changes.spec.ts tests/faults.spec.ts tests/leader-briefings-api.spec.ts tests/leader-briefings-ui.spec.ts`：22 passed，0 skip/fail。当前源码 API、独立 worker、PostgreSQL 和固定 Batfish 引擎在 r1/r2、Cisco 四设备合成配置上运行。 |
| 汇报行为 | 管理员从已完成检查创建固定汇报、产生标题修订，旧版仍可读取；另一成员登录后可查看同一旧版和会议页，不能归档。模拟来源失效时固定事实仍展示，失效证据链接关闭。会议页深浅主题、浏览器打印 A4 三页、减少动效 CSS 已验证；PDF 文本中保留固定快照、版本、模型边界、全部警告和人工备注。 |
| 页面目视 | Chromium 全页截图位于忽略提交的 `web/frontend/test-results/leader-briefings-ui-*/briefing-detail-light.png`、`briefing-meeting-light.png`、`briefing-meeting-dark.png`；打印件 `briefing-print.pdf`。已目视检查会议页层次与两主题，厂商能力限制在屏幕上折叠、打印时完整且转为可读文字。 |
| 后端基线 | 本篇未修改后端；LDR-10 同源码的隔离后端全量 392 passed、汇报目标 5 passed 和迁移 `0013` 继续适用。LDR-12 将重新运行全量及 HTTPS 恢复门槛。 |

本次重建隔离环境时，首次启动的管理员需改初始密码，并从 Web API 将两套合成配置上传/初始化为就绪快照。累计运行中曾因重复同名网络导致测试定位不唯一，并因多任务连续执行时汇报提交超过浏览器默认 5 秒断言而各失败一次；按卡片唯一定位、等待真实提交完成后整组 22 项重跑通过。早前“服务尚未就绪”截图缺少原请求、网络与快照上下文，不能宣称那次故障已定位；当前累计用例验证了未就绪提示和重试。验收仅证明合成配置上的 Web 工作流，不证明真实设备转发或 Java 仿真精度。
