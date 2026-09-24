# ADV-11 双快照对比上下文与记录

- 状态：待开发
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

以下是实现时的目标路径，本次文档编写不创建代码文件：

- `web/backend/app/modules/changes/api.py`
- `web/backend/app/modules/changes/service.py`
- `web/backend/app/modules/changes/repository.py`
- `web/backend/app/modules/lifecycle/service.py`
- `web/backend/migrations/`
- `web/backend/tests/test_comparisons.py`

## 实施步骤

- [ ] 增加 ComparisonDTO/表/索引，记录两侧内容摘要与版本。
- [ ] 通过 snapshots.service 取上下文，不直接查快照 repository。
- [ ] 扩展删除依赖检查：被 comparison 引用的快照不得删除，先由管理员删除比较记录（保留历史结果来源）。
- [ ] 运行下述验证，记录实际命令与结果，更新本文及索引状态。

## 测试与验收

- test_comparison_direction：有效参数中两侧方向固定。
- test_cross_network_or_same_snapshot：明确拒绝。
- test_comparison_blocks_delete：引用存在时不删除快照。

后端测试在 `web/backend` 下使用 `uv run pytest` 指定上述测试文件；集成测试连接版本固定的隔离 Batfish 测试网络，不操作团队生产网络。

验收成功同时要求：契约与文档一致、失败行为可解释、无跨层/跨模块越界、没有把 mock 验证宣称为真实 SDK 验证。共享约束中的身份、版本、模型覆盖和结果截断规则均适用。

## 非目标与实施边界

- 不执行差异计算、不自动对齐不兼容厂商模型。

## 完成记录

当前尚未开发或运行本 spec 的产品测试。实施者完成后在本节记录实际文件、验证命令、结果、引擎/SDK版本（如涉及）和剩余限制；存在验收失败时保持未通过状态。
