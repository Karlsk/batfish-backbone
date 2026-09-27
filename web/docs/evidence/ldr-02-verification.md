# LDR-02 业务关注项接口验收

日期：2026-09-28；基线提交：`8c391d5cbb`（LDR-01）。状态：LDR-02 目标及此前 LDR-01、MVP/ADV 的受影响门槛通过。

新增网络级业务关注项 API 和 Alembic `0011` 迁移。管理员可创建、按预期版本修改与归档；所有登录成员可读取。1～10 条关键流量要求显式起点和规范目的 IPv4，可选源地址、协议和目的端口；端口只允许随 TCP/UDP 使用。记录当前版本与完整历史版本、创建/修改身份和时间。写入与脱敏审计同一事务；同一旧版本并发更新只有一个成功。关注项不含快照 ID，也不自动推断业务影响。

| 检查 | 结果 |
| --- | --- |
| 目标迁移、权限、历史、并发及架构 | 目标 `pytest` 59 passed；新增 3 项业务关注项测试，含并发 200/409、成员 403、非法流量/未知字段 422、旧版保持、归档与分页；迁移元数据和分层规则通过 |
| 隔离 Batfish/PostgreSQL 后端累计回归 | `web/backend/.venv/bin/python web/scripts/lab.py verify`：372 passed，0 failed/skip；证据 `8a53df3cb24f/checks/06b140f22990` |
| r1/r2 与 Cisco 四设备真实 API/worker 冒烟 | `web/backend/.venv/bin/python web/scripts/lab.py smoke`：13 passed；证据 `8a53df3cb24f/checks/b31e447bca82` |
| 真实 HTTP 与独立 PostgreSQL | 临时启动当前源码的 Uvicorn 与新建数据库并升级至 `0011`；管理员登录 200、无 CSRF 写入 403、创建 201、列表与历史读取 200、修改 200、旧版本冲突 409；成员登录/读取 200、修改 403。检查后停止 API 并删除临时数据库。该检查只验证 Web/PG 流程，不调用 SDK 分析。 |
| 前端契约与回归 | `pnpm generate:api`、`pnpm check:api`、`pnpm typecheck`、`pnpm build`、`pnpm format:check` 均通过；`pnpm test` 94 passed；LDR-01 真实浏览器目标回归 3 passed。生成的 `schema.d.ts` 已更新。 |
| 静态检查 | Ruff check、变更 Python 文件格式、离线 `uv lock --check`、`git diff --check` 通过 |

真实环境固定 Batfish revision `7d0deeeac4a09973b3876327f6aef721ee12f955`、JAR SHA-256 `0927de7c740bc72f999870e842605baad9a7cb6ea66e4b01fb9a6037bea00193`、Pybatfish `2026.9.17.3748`、Python `3.12.12`；本篇新增迁移 `0011`。LDR-02 尚无页面，LDR-03 才接入管理界面；检查任务和汇报仍由后续篇实现。历史版本供以后汇报冻结引用，资源后续删除时的汇报行为不属于本篇验收。
