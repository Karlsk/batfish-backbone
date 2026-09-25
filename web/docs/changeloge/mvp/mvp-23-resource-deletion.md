# MVP-23 管理员资源删除与任务互斥

- 状态：已完成
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

- [x] 在同一互斥边界校验资源活动任务并标记 deleting，禁止新分析提交。
- [x] worker 通过 SDK 删除，远端成功/写回失败可按固定名称对账。
- [x] 前端显示具体资源和影响，管理员确认后调用；普通成员不显示管理操作。
- [x] 运行下述验证，记录实际命令与结果，更新本文及索引状态。

## 测试与验收

- test_delete_submit_race：删除和提交交错不能产生悬挂任务。
- test_nonempty_network_delete：无隐式批量删除。
- test_delete_sdk_writeback_failure：不把未知状态显示为彻底删除。

后端测试在 `web/backend` 下使用 `uv run pytest` 指定上述测试文件；集成测试连接版本固定的隔离 Batfish 测试网络，不操作团队生产网络。

验收成功同时要求：契约与文档一致、失败行为可解释、无跨层/跨模块越界、没有把 mock 验证宣称为真实 SDK 验证。共享约束中的身份、版本、模型覆盖和结果截断规则均适用。

## 非目标与实施边界

- 不做自动历史清理策略、批量删除或运行中强制取消。

## 完成记录

2026-09-26 完成管理员网络/快照DELETE→202持久任务，网络要求已就绪且无未删快照，不级联。JobsService共享队列事务锁覆盖删除依赖检查+标记、分析准入、初始化/重试，以及网络创建重试重读/SDK/写回，防止迟到创建复活已删网络。活动任务包含reference快照，unknown引擎拒绝删除。0008迁移保存当前deletion_job_id与审计说明，旧任务不能覆盖后续删除。

SDK删除及存在性检查位于各域controller，lifecycle仅跨service编排。远端确认不存在后才提交deleted；写回失败保留deleting与输入，通过管理员固定名称对账恢复原状态或补记删除。unknown先按运行手册停止旧worker并核验引擎再做全局对账，不用对象存在性推断引擎空闲。删除不可取消/重试，历史初始化在来源删除后拒绝重试。输入清理在数据库提交后且无其他未删快照引用时进行，已保存结果/来源墓碑与导出保留。

前端DeleteResource仅管理员可见，确认具体资源与不可取消/结果保留影响，409明确提示活动任务/非空网络/待对账，失败任务提供ReconcileDeletion。删除入队后只清理对应当前选择，网络/快照删除中轮询。实际文件：lifecycle模块，jobs/networks/snapshots/analysis/uploads/audit服务和域适配、0008迁移、test_deletion.py、前端删除/对账组件与真实browser helper。

独立只读审查发现网络创建重试竞态，修复并通过真实交错测试；最终无阻塞。累计 `lab.py smoke/verify` 为12项冒烟和286项后端通过；前端37项单测、10项真实Chromium流程通过，均0skip。包含并发准入、参考快照保护、SDK写回失败、unknown/远端仍存在恢复、共享重试输入、两拓扑删除后历史结果保留和普通成员拒绝。OpenAPI/类型/构建/格式/Ruff/锁/迁移/链接检查通过。见 [验收证据](../../evidence/mvp-23-verification.json)。UI共享包体积提示保留，不作容量或设备精度背书；满足MVP-24依赖。
