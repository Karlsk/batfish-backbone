# LDR-05 领导端日常总览与网络下钻验收

日期：2026-09-28；基线提交：`9f3f479cae`（LDR-04）。隔离环境运行 ID `8a53df3cb24f`，Batfish revision `7d0deeeac4a09973b3876327f6aef721ee12f955`、Pybatfish `2026.9.17.3748`、Python `3.12.12`。

领导首页现在按服务端全量口径显示共享网络数、历史就绪快照记录数与仍在运行的分析任务。网络卡区分最新快照和最近就绪来源、未检查/任务状态、结果覆盖与警告；无结论不显示健康分。最近变更比较固定列出最多五条，标注网络、时间、覆盖、基线与候选快照 ID，仅代表已建立比较。分页按需加载；单网络详情可直达和刷新，显示业务关注项、任务、结果和最近比较，证据链接使用固定资源 ID。

| 检查 | 结果 |
| --- | --- |
| 后端合同 | 新增单网络卡与最近比较测试先失败后实现；隔离 PostgreSQL 的 LDR-05 目标测试 2 passed。比较查询通过 ChangesService、网络名称通过 NetworksService 批量读取，领导模块未访问其他模块 repository/SDK。 |
| 前端检查 | `pnpm check:api`、`pnpm test`（98 passed）、`pnpm build`、`pnpm format:check`、TypeScript 类型检查通过。 |
| 累计浏览器 | 当前源码 API、隔离 PostgreSQL/Batfish 与 Chromium 上，LDR-01/03/05 及用户管理回归 8 passed。管理员/成员均可进入；真实两设备 `small_network`、四设备 `cisco_four` Web 快照的卡片、网络详情及证据来源可读；服务返回 `NOT_READY` 时保留错误提示并可重试。首页总数与同会话 API 返回的 `total` 相等，最近比较数量/首条名称与 API 相等。 |
| 视觉与键盘 | Chromium 1280 浅色、1440 深色、1920 浅色截图已目视检查，无横向溢出；Tab 可聚焦操作。截图保留在忽略提交的 `web/frontend/test-results/leader-overview-real-r1-r2-d383e-verview-and-retain-evidence-chromium/`。 |
| 后端累计/冒烟 | `web/backend/.venv/bin/python web/scripts/lab.py verify`：374 passed，证据 `8a53df3cb24f/checks/cbd0b80b295a`；`web/backend/.venv/bin/python web/scripts/lab.py smoke`：13 passed，证据 `8a53df3cb24f/checks/c0527a09005c`。Ruff check/format 与 `git diff --check` 通过。 |

本篇只汇总已持久化事实；快照就绪与模型结果不证明真实设备转发或 Java 仿真精度。先前截图的“服务尚未就绪”缺少原 URL、网络和快照，无法认定为同一请求或宣称已修复；本篇验证了可见错误与重试流程。新增读模型不自动运行检查，LDR-06 才建立可恢复检查任务。
