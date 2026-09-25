# MVP-03 业务持久化与迁移基础

- 状态：已完成
- 阶段：1
- 依赖：[MVP-02](../mvp/mvp-02-backend-foundation.md)
- 预计工作量：1.5 人天（实现/验证 1.0 + 测试 0.25 + 文档/自检 0.25），依赖就绪后计；超过 2 人天先拆分。
- 共享约束：[架构](../../architecture.md)、[API 契约](../../api-contracts.md)、[前端规范](../../frontend.md)、[运行设计](../../operations.md)、[验收](../../validation.md)。

## 需求与目标

提供可迁移数据库与隔离文件存储，供后续模块持久化状态。

- PostgreSQL 连接/事务、Alembic、用户/会话/网络/上传/快照/任务/结果/审计的初始表。
- 结果临时文件及原子发布基础；共享事务句柄不暴露跨模块 ORM。

## 设计与接口

- 表字段、UUID、外键、唯一约束按 api-contracts.md。
- 文件接口只接受内部 storage_key，拒绝绝对路径和越界；不直接读取 Batfish 文件卷。

沿用 api → service → controller；所有跨业务模块调用经过 service。非 SDK 存储由本模块 repository 负责。浏览器不接触 SDK 会话或连接参数。

## 预期改动位置

以下是实现时的目标路径，本次文档编写不创建代码文件：

- `web/backend/app/infrastructure/database.py`
- `web/backend/app/infrastructure/storage.py`
- `web/backend/migrations/`
- `web/backend/tests/test_persistence.py`

## 实施步骤

- [x] 创建初始 migration 和最小 repository 接口，保留 DTO 与 ORM 分离。
- [x] 落实 username/engine_name/idempotency 的唯一约束和带删除标记的资源关联。
- [x] 实现临时写入、原子发布、失败回滚和受控删除。
- [x] 用临时 PostgreSQL 验证全新迁移与数据库/文件失败路径。
- [x] 运行下述验证，记录实际命令与结果，更新本文及索引状态。

## 测试与验收

- test_migration_from_empty：空库可升级且约束存在。
- test_transaction_rollback：发布前失败不出现成功记录。
- test_storage_key_boundary：穿越和绝对路径被拒绝。

后端测试在 `web/backend` 下使用 `uv run pytest` 指定上述测试文件；集成测试连接版本固定的隔离 Batfish 测试网络，不操作团队生产网络。

验收成功同时要求：契约与文档一致、失败行为可解释、无跨层/跨模块越界、没有把 mock 验证宣称为真实 SDK 验证。共享约束中的身份、版本、模型覆盖和结果截断规则均适用。

## 非目标与实施边界

- 不建设通用 ORM 框架、多数据库兼容或自动备份系统。

## 完成记录

2026-09-25 完成。交付 `backend/app/infrastructure/database.py`、`storage.py`，按模块归属的 9 张业务表（含幂等记录）、users/results 最小 repository、composition 模型注册、Alembic `0001` 固定迁移与依赖锁；lab 启动自动迁移自己的数据库。

验证（仓库根）：`web/backend/.venv/bin/python web/scripts/lab.py serve` → `seed` → `verify`，使用重启后的当前源码、真实 PostgreSQL 17.10/Batfish/API、r1/r2 与 Cisco 四设备配置。MVP-01～03 累计 **87 passed、0 failed、0 errors、0 skipped**，其中新增持久化 4 项、文件存储 14 项；现有 69 项保留。空库升级/降级重建、metadata 一致、外键/唯一/状态约束、软删除关联、事务回滚和结果发布均通过。backend 中 Ruff、`uv lock --check`、Markdown 本地链接和 Git 空白检查通过。

运行 Python 3.12.12、SQLAlchemy 2.0.54、Alembic 1.20.0、psycopg 3.3.6、Pybatfish 2026.9.17.3748；引擎 revision `7d0deeeac4a09973b3876327f6aef721ee12f955`，没有修改 Java。源码指纹、测试清单、环境和原始证据位置见 [脱敏验收证据](../../evidence/mvp-03-verification.json)。

独立只读审查发现暂存对象 key 可修改，已通过先红后绿的回归测试修复为只读且发布前再次校验。自动生成迁移遗漏的循环外键由 metadata 一致性测试发现并修复。没有未通过或跳过的必需检查；一条既有 Starlette/httpx 弃用警告。

限制：已发布文件与数据库不是分布式事务；数据库提交失败/结果未知可能留下未引用文件，后续清理必须查证引用。无账号业务、worker、分析或浏览器页面，尚不做这些后续功能验收；ready 仍为 503。满足 MVP-04 依赖。提交哈希由 runner checkpoint 和 Git 关联。
