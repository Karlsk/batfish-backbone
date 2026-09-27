# LDR-07 MVP 自主检查页面验收

日期：2026-09-28；基线提交 `aa0cbcd0e7`（LDR-06）。隔离环境运行 ID `8a53df3cb24f`；Batfish revision `7d0deeeac4a09973b3876327f6aef721ee12f955`、Pybatfish `2026.9.17.3748`、Python `3.12.12`。

领导端自主检查页面覆盖六个 MVP 模板，网络与就绪快照、范围与高级条件逐步输入；业务关注项只预填显式的一条流量，需核对当前快照。运行详情使用固定运行 ID 恢复，不根据当前浏览器上下文拼接结果。配置质量展示解析数量、问题和模型限制；traceroute 只显示已保存路径的 disposition，不把单向推演写成在线/回程可达。其他表格结果只说明返回记录数或当前范围无记录，原始表格/逐跳/导出交给技术端。任务失败、中断、引擎 unknown、结果暂不可读及服务 `NOT_READY` 都有不同提示和来源。

| 检查 | 结果 |
| --- | --- |
| 目标单测 | `pnpm exec vitest run src/features/leader/checks/model.test.ts`：4 passed，覆盖范围必填、失败/未知、混合路径 disposition、解析警告与业务流量协议/端口映射。 |
| 目标真实浏览器 | `leader-mvp-checks.spec.ts`：4 passed，r1/r2 配置质量刷新、Cisco 四设备单向路径与高级条件、关注项预填/切网清草稿、`NOT_READY` 错误与重试。当前源码 API/独立 worker/隔离 PostgreSQL/Batfish。 |
| 视觉 | Chromium 1440 浅色工作页、1440 深色详情和 390 移动宽度工作页截图已目视检查，无横向溢出；截图位于忽略提交的 `web/frontend/test-results/leader-mvp-checks-leader-r-6a68e--fixed-detail-after-refresh-chromium/`。 |
| 累计前端 | `web/frontend` 执行 `pnpm check:api`、`pnpm test`（102 passed）、`pnpm build`、`pnpm format:check`，均通过；TypeScript 类型检查也通过。 |
| 累计浏览器 | 当前源码 API/独立 worker/隔离 PostgreSQL/Batfish 上，LDR-01/03/05/06/07 及原用户管理页面共 13 passed。关注项测试原先在异步网络列表尚未加载时立即取选项而失败，增加明确等待后整组重跑通过；没有更改产品行为来掩盖失败。 |
| 后端基线与冒烟 | 本篇未改后端；LDR-06 真实环境全量 385 passed，证据 `8a53df3cb24f/checks/53bdb0bc2105`。本篇重跑 `web/backend/.venv/bin/python web/scripts/lab.py smoke`：13 passed，证据 `8a53df3cb24f/checks/05c43a5fb6b0`。`git diff --check` 通过。 |

旧截图缺少原 URL、网络和快照，无法确定该 `NOT_READY` 是否同一故障；本篇验证其在自主检查页可见且可重试，没有隐藏错误。验收只覆盖 Web 工作流及固定配置模型的行为，不宣称与真实设备转发或 Java 仿真结果一致。
