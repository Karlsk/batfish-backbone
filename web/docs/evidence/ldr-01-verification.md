# LDR-01 双入口与领导端壳层验收

日期：2026-09-28；基线提交：`6ada5e69a5`。状态：LDR-01 及此前 MVP-01～25、ADV-01～18 的受影响门槛通过。

同一前端增加独立 `/leader/overview` 壳层。现有技术端路由和首次登录默认入口不变；管理员、普通成员都能双向切换。只有主动切换才保存浏览器入口偏好，损坏或禁用存储时回到技术端。两个入口共用认证、Cookie/CSRF、主题、服务状态、QueryClient 与网络/快照上下文；登录、退出、改密仍由原流程处理。领导端尚无汇总数据时明确显示“尚未检查”，不生成健康分或业务影响数字。

| 检查 | 结果 |
| --- | --- |
| 前端单测 | `pnpm test`：94 passed / 28 files，0 failed |
| API 契约、类型、生产构建、格式 | `pnpm check:api`、`pnpm typecheck`、`pnpm build`、`pnpm format:check` 均退出 0；构建保留原有大 chunk 提示 |
| 真实 Chromium 累计回归 | `pnpm exec playwright test`：29 passed，0 failed/skip，覆盖原技术端和新增领导端 |
| 双用户与上下文 | 管理员、普通成员切换通过；r1/r2 配置创建并初始化就绪快照后，双向切换保持网络与快照；主题、刷新记忆、退出与登录通过 |
| 响应式视觉 | 1440 深色、768/390 浅色截图已检查，无横向溢出；截图保留在忽略提交的 `web/frontend/test-results/` |
| 隔离后端累计回归 | `web/backend/.venv/bin/python web/scripts/lab.py verify`：369 passed；证据 `8a53df3cb24f/checks/ce4a640cf784` |
| r1/r2 与 Cisco 四设备真实 API/worker 冒烟 | `web/backend/.venv/bin/python web/scripts/lab.py smoke`：13 passed；证据 `8a53df3cb24f/checks/0183e391cb82` |
| Git 空白 | `git diff --check` 退出 0 |

真实环境为隔离 Batfish revision `7d0deeeac4a09973b3876327f6aef721ee12f955`、JAR SHA-256 `0927de7c740bc72f999870e842605baad9a7cb6ea66e4b01fb9a6037bea00193`、Pybatfish `2026.9.17.3748`、Python `3.12.12`、数据库迁移 `0010`。首次浏览器运行发现领导端滚动副作用返回值被 React 当成清理函数；修正后领导端目标用例和最终 29 项累计用例通过。另一次上下文测试误选无快照网络，已改为自行创建双设备快照，最终通过。这些中间失败不计为最终通过。

本篇只交付入口与诚实空状态；跨网络汇总、业务关注项、引导检查和汇报分别由后续 LDR 实现。此前截图中的 `NOT_READY` 缺少原 URL/网络/快照，恢复后的就绪 Cisco 查询可成功，原始故障仍不可复现；后续验收继续覆盖服务不可用与未就绪状态。验收只证明 Web 工作流和固定版本模型行为，不证明真实设备转发或 Java 仿真精度。
