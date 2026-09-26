# ADV-11 双快照对比上下文与记录

- 状态：已完成
- 阶段：3
- 依赖：[ADV-10](../advance/adv-10-phase-two-acceptance.md)
- 预计工作量：1.0 人天（实现/验证 0.5 + 测试 0.25 + 文档/自检 0.25），依赖就绪后计；超过 2 人天先拆分。
- 共享约束：[架构](../../architecture.md)、[API 契约](../../api-contracts.md)、[前端规范](../../frontend.md)、[运行设计](../../operations.md)、[验收](../../validation.md)。

## 需求与目标

固定基线和候选方向，为所有差异功能建立共同契约。

- 比较记录、同网络/快照状态校验、版本/覆盖提示、不可变引用。

## 设计与接口

- POST /networks/{id}/comparisons：baseline_snapshot_id、candidate_snapshot_id、display_name 可选 → ComparisonDTO。
- GET /networks/{id}/comparisons 与 /comparisons/{id}；两快照必须不同、同网络且可分析。
- DELETE /comparisons/{id} 仅管理员可调用；有在途任务返回409，否则保留来源后标记删除并返回204。删除快照前通过 changes.service 检查有效引用，由既有 ResourceLifecycleService 编排，不能让 snapshots.service 反向导入 changes。
- candidate 映射 SDK snapshot，baseline 映射 reference_snapshot；不同模型版本标记 limited/不兼容时拒绝。

沿用 api → service → controller；所有跨业务模块调用经过 service。非 SDK 存储由本模块 repository 负责。浏览器不接触 SDK 会话或连接参数。

## 预期改动位置

实际实现位置：

- `web/backend/app/modules/changes/api.py`
- `web/backend/app/modules/changes/service.py`
- `web/backend/app/modules/changes/repository.py`
- `web/backend/app/modules/lifecycle/service.py`
- `web/backend/migrations/`
- `web/backend/tests/test_comparisons.py`

## 实施步骤

- [x] 增加 ComparisonDTO/表/索引，记录两侧内容摘要与版本。
- [x] 通过 snapshots.service 取上下文，不直接查快照 repository。
- [x] 扩展删除依赖检查：被 comparison 引用的快照不得删除，先由管理员删除比较记录（保留历史结果来源）。
- [x] 运行下述验证，记录实际命令与结果，更新本文及索引状态。

## 测试与验收

- test_comparison_direction：有效参数中两侧方向固定。
- test_cross_network_or_same_snapshot：明确拒绝。
- test_comparison_blocks_delete：引用存在时不删除快照。

后端测试在 `web/backend` 下使用 `uv run pytest` 指定上述测试文件；集成测试连接版本固定的隔离 Batfish 测试网络，不操作团队生产网络。

验收成功同时要求：契约与文档一致、失败行为可解释、无跨层/跨模块越界、没有把 mock 验证宣称为真实 SDK 验证。共享约束中的身份、版本、模型覆盖和结果截断规则均适用。

## 非目标与实施边界

- 不执行差异计算、不自动对齐不兼容厂商模型。

## 完成记录

2026-09-26 已完成。新增 changes 模块（API、service、repository、DTO、ORM）、Alembic 0009、生命周期引用检查及 OpenAPI 类型；真实 PostgreSQL 与 Cisco 四设备快照验证方向、跨网络与同快照拒绝、版本冲突、管理员权限、软删除、在途任务、并发创建/删除和删除后 worker 清理。比较不触发计算；候选映射 SDK snapshot，基线映射 reference_snapshot。新增结果中的 coverage 提示反映模型限制或格式差异，不把文本差异当作转发结论。

仓库根执行 `web/backend/.venv/bin/python web/scripts/lab.py smoke`（12 passed）与 `verify`（336 passed）、Ruff lint/变更文件格式、离线 uv 锁文件及 Git 空白检查。`web/frontend` 执行 `pnpm generate:api`、`pnpm check:api`、`pnpm typecheck`、`pnpm test`（81 passed）、`pnpm build`、`pnpm format:check`、`pnpm exec playwright test`（23 passed）。本机独立 HTTPS 部署通过重启、失联对账、备份与新卷恢复；恢复后的生产构建浅色/深色各 3 项部署页与 1 项双用户验收通过。环境为引擎 revision `7d0deeeac4a09973b3876327f6aef721ee12f955`、Pybatfish `2026.9.17.3748`、Python `3.12.12`、迁移 0009，使用 r1/r2 与 Cisco 四设备配置。完整命令、源码身份与证据见[验收记录](../../evidence/adv-11-verification.md)。

限制：本篇仅记录比较上下文，文件、路由、可达性差异分别由 ADV-12～14 实现。配置样例证明功能路径，不证明仿真与真实设备一致或规模容量。ADV-12 的依赖已满足。
