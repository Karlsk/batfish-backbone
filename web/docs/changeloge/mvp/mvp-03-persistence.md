# MVP-03 业务持久化与迁移基础

- 状态：待开发
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

- [ ] 创建初始 migration 和最小 repository 接口，保留 DTO 与 ORM 分离。
- [ ] 落实 username/engine_name/idempotency 的唯一约束和带删除标记的资源关联。
- [ ] 实现临时写入、原子发布、失败回滚和受控删除。
- [ ] 用临时 PostgreSQL 验证全新迁移与数据库/文件失败路径。
- [ ] 运行下述验证，记录实际命令与结果，更新本文及索引状态。

## 测试与验收

- test_migration_from_empty：空库可升级且约束存在。
- test_transaction_rollback：发布前失败不出现成功记录。
- test_storage_key_boundary：穿越和绝对路径被拒绝。

后端测试在 `web/backend` 下使用 `uv run pytest` 指定上述测试文件；集成测试连接版本固定的隔离 Batfish 测试网络，不操作团队生产网络。

验收成功同时要求：契约与文档一致、失败行为可解释、无跨层/跨模块越界、没有把 mock 验证宣称为真实 SDK 验证。共享约束中的身份、版本、模型覆盖和结果截断规则均适用。

## 非目标与实施边界

- 不建设通用 ORM 框架、多数据库兼容或自动备份系统。

## 完成记录

当前尚未开发或运行本 spec 的产品测试。实施者完成后在本节记录实际文件、验证命令、结果、引擎/SDK版本（如涉及）和剩余限制；存在验收失败时保持未通过状态。
