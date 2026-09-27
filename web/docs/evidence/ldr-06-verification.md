# LDR-06 检查模板与运行记录验收

日期：2026-09-28；基线提交 `e78f263e46`（LDR-05）。隔离环境运行 ID `8a53df3cb24f`；Batfish revision `7d0deeeac4a09973b3876327f6aef721ee12f955`，Pybatfish `2026.9.17.3748`，Python `3.12.12`。

实现 13 个固定模板、版本化运行记录与迁移 `0012`。检查绑定就绪快照、明确的范围和经过白名单校验的高级条件；关注项版本、快照质量、引擎/SDK版本、比较方向、任务和结果引用均被冻结。配置质量无需 worker；其余调用已有 analysis/changes/fault service 的持久任务。不同成员可读取同一运行，发起人同键同请求复用资源，异请求冲突；数据库行锁使并发请求只执行一次下游提交。运行详情显示每个子任务的阶段和 `engine_state`；未知、中断、失败和结果不可读分别保留，不生成成功结论或自行重放。

| 检查 | 结果 |
| --- | --- |
| 合同/权限/幂等/真实引擎 | `web/backend` 隔离 PostgreSQL/Batfish 上运行 `pytest -q tests/test_leader_check_runs.py tests/test_persistence.py`：12 passed。包含双用户共享读取、并发同键且下游提交仅一次、冲突、13 种模板准入、r1/r2 与四台 Cisco、真实 worker 完成、中断/引擎 unknown、结果引用缺失、迁移 upgrade/downgrade 与 ORM 一致性。 |
| 架构 | `pytest -q tests/test_architecture.py`：55 passed。新增模块的层级映射明确登记；leader 只通过其他模块 service，不导入跨模块 schema/repository/controller。Ruff check 及改动文件 format check 通过。 |
| 前端契约 | `pnpm generate:api`、`pnpm check:api`、`pnpm typecheck`、`pnpm test`（98 passed）、`pnpm build`、`pnpm format:check` 通过。 |
| 真实 HTTP 与浏览器 | 当前源码 API、隔离 PostgreSQL/Batfish/独立 worker 与 Chromium：`leader-checks-api`、`leader-overview`、`leader-entry`、`leader-concerns`、`auth-users` 合计 9 passed。质量检查固定事实、设备检查经 worker 成功并可再次 GET、同键复用/冲突、成员和技术端入口回归、r1/r2 与 Cisco 总览，以及服务不可用时的可见错误和重试均通过。 |
| 累计后端 | `web/backend/.venv/bin/python web/scripts/lab.py verify`：385 passed，证据目录 `8a53df3cb24f/checks/53bdb0bc2105`。 |
| 冒烟 | `web/backend/.venv/bin/python web/scripts/lab.py smoke`：13 passed，证据目录 `8a53df3cb24f/checks/8a7e75eb0141`。Ruff check/改动文件 format 与 `git diff --check` 通过。 |

模型能力的限制和来源与每个模板一并返回；不宣称真实设备转发或 Java 仿真精度。先前截图的“服务尚未就绪”缺少原 URL、网络、快照，不能证明当前重试测试覆盖了同一请求；本篇没有隐藏或吞掉 `NOT_READY`。
