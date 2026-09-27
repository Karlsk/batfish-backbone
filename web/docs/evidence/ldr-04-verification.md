# LDR-04 跨网络总览接口验收

日期：2026-09-28；基线提交：`49192328d3`（LDR-03）。状态：已通过本篇与此前累计门槛。

新增 `GET /api/v1/leader/overview` 的有界只读投影。默认每页 20、最大 200，`total` 由数据库对全部未删除网络计数；状态汇总分别注明当前网络、未删除快照记录和历史分析任务口径。网络卡显示最新快照、最新就绪快照、人工维护的关注项数量，以及只属于最新就绪快照的最近分析任务与结果质量。最新快照尚未就绪时保留上一就绪来源并标记警告；无就绪快照为待准备，无该来源结果为未检查。结果提供覆盖、截断、警告数和来源 ID/时间，不生成健康分。

| 检查 | 结果 |
| --- | --- |
| 先失败后实现 | 新增 PostgreSQL 合同测试先因 `404` 失败；实现后覆盖空网络、服务端全量总数与分页、同时间快照 ID 排序、更新但未就绪、旧结果隔离、完成/中断任务、有限覆盖和截断、管理员/普通成员同读，以及 1/3 网络页 SQL 数量不随卡片逐项增长。目标与 LDR-02/分层合跑 57 passed。 |
| 全量后端与真实拓扑 | `web/backend/.venv/bin/python web/scripts/lab.py verify`：374 passed；证据 `8a53df3cb24f/checks/655242330197`。`web/backend/.venv/bin/python web/scripts/lab.py smoke`：13 passed；证据 `8a53df3cb24f/checks/1d056edd84aa`。隔离 lab 迁移清单已与数据库 `0011` 对齐。 |
| 真实 HTTP 双用户 | 当前源码 API 独立运行于本机隔离环境的 18001；管理员和新建后改密的临时普通成员读取同一 `limit=2` 总览，均为 200 且响应相同；临时账号随后停用。测试时共享网络总数 237。 |
| 本机性能采样 | 同一 API、同一数据库，分页大小 1/20/200，各 5 次顺序 GET，客户端墙钟中位数分别约 48.5/76.0/362.1 ms。该样本包含本机 HTTP/认证和多服务查询，不是生产容量指标；代码的批量 service 投影和目标测试检查了无逐网络 SQL 增长。 |
| 前端契约与累计回归 | `pnpm generate:api`、`pnpm check:api`、`pnpm test` 96 passed、`pnpm build`、`pnpm format:check` 通过；现有 LDR-01/03 浏览器 5 passed。Ruff check/format 与 `git diff --check` 通过。 |

跨模块依赖仅通过 network、snapshot、jobs、results、business concern 的 service；新增 leader 模块没有 SDK controller，也不启动任务。快照质量仍是 Batfish 模型解析/初始化事实，不证明现场转发精度；截图里的旧 `NOT_READY` 因缺少请求标识无法归因为同一问题。LDR-05 可消费此读模型。
