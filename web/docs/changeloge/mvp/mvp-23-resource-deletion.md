# MVP-23 管理员资源删除与任务互斥

- 状态：待开发
- 阶段：1
- 依赖：[MVP-22](../mvp/mvp-22-result-export.md)
- 预计工作量：1.5 人天（实现/验证 1.0 + 测试 0.25 + 文档/自检 0.25），依赖就绪后计；超过 2 人天先拆分。
- 共享约束：[架构](../../architecture.md)、[API 契约](../../api-contracts.md)、[前端规范](../../frontend.md)、[运行设计](../../operations.md)、[验收](../../validation.md)。

## 需求与目标

管理员可以清理网络/快照，且不破坏正在运行的分析。

- 删除任务、资源删除标记、依赖检查、SDK 删除对账、前端管理入口。

## 设计与接口

- DELETE N / DELETE S → 202 job；queued/running/unknown 引擎相关依赖存在时返回 409。
- 网络下还有未删除快照时拒绝网络删除，提示先逐个删除；不隐式级联。
- 结果保留来源墓碑，文件卷清理只针对已确认删除的资源；历史结果不可直接重试。
- 删除任务排队后 cancel_allowed=false；SDK删除失败/中断后管理员检查远端对象：仍存在则恢复资源可用状态，不存在则补记 deleted，不明则保持占用。相关逻辑在网络/快照 service 内完成。
- DELETE路由由 lifecycle.api 提供，ResourceLifecycleService 调用 networks/snapshots/jobs.service 编排依赖检查，域内SDK操作仍留在原模块controller。为第三阶段新增comparison引用保护保留上层入口，不反向依赖 changes。

沿用 api → service → controller；所有跨业务模块调用经过 service。非 SDK 存储由本模块 repository 负责。浏览器不接触 SDK 会话或连接参数。

## 预期改动位置

以下是实现时的目标路径，本次文档编写不创建代码文件：

- `web/backend/app/modules/networks/service.py`
- `web/backend/app/modules/lifecycle/api.py`
- `web/backend/app/modules/lifecycle/service.py`
- `web/backend/app/modules/networks/controller.py`
- `web/backend/app/modules/snapshots/service.py`
- `web/backend/app/modules/snapshots/controller.py`
- `web/frontend/src/features/snapshots/DeleteResource.tsx`
- `web/backend/tests/test_deletion.py`

## 实施步骤

- [ ] 在同一互斥边界校验资源活动任务并标记 deleting，禁止新分析提交。
- [ ] worker 通过 SDK 删除，远端成功/写回失败可按固定名称对账。
- [ ] 前端显示具体资源和影响，管理员确认后调用；普通成员不显示管理操作。
- [ ] 运行下述验证，记录实际命令与结果，更新本文及索引状态。

## 测试与验收

- test_delete_submit_race：删除和提交交错不能产生悬挂任务。
- test_nonempty_network_delete：无隐式批量删除。
- test_delete_sdk_writeback_failure：不把未知状态显示为彻底删除。

后端测试在 `web/backend` 下使用 `uv run pytest` 指定上述测试文件；集成测试连接版本固定的隔离 Batfish 测试网络，不操作团队生产网络。

验收成功同时要求：契约与文档一致、失败行为可解释、无跨层/跨模块越界、没有把 mock 验证宣称为真实 SDK 验证。共享约束中的身份、版本、模型覆盖和结果截断规则均适用。

## 非目标与实施边界

- 不做自动历史清理策略、批量删除或运行中强制取消。

## 完成记录

当前尚未开发或运行本 spec 的产品测试。实施者完成后在本节记录实际文件、验证命令、结果、引擎/SDK版本（如涉及）和剩余限制；存在验收失败时保持未通过状态。
