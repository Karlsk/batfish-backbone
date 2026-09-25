# MVP-09 独立执行进程与中断恢复

- 状态：已完成
- 阶段：1
- 依赖：[MVP-08](../mvp/mvp-08-job-records.md)
- 预计工作量：2.0 人天（实现/验证 1.25 + 测试 0.5 + 文档/自检 0.25），依赖就绪后计；超过 2 人天先拆分。
- 共享约束：[架构](../../architecture.md)、[API 契约](../../api-contracts.md)、[前端规范](../../frontend.md)、[运行设计](../../operations.md)、[验收](../../validation.md)。

## 需求与目标

队列任务可被可靠领取、执行和观察，并在引擎状态不明时保守恢复。

- 单 SDK 槽位、worker 心跳/租约、dispatcher、执行前身份复核、超时/失联、管理员解除阻塞。

## 设计与接口

- [MVP-01](../../sdk-compatibility.md) 已确认后台分析 work ID/状态/答案读取，但初始化仍同步，HTTP timeout 含重试影响且不是作业期限；本篇不因此扩大为自动接管或运行中取消。

- JobsService.claim(worker_id) → JobDTO | None；dispatcher 只调用登记的业务 service.execute。
- POST /jobs/{id}/retry 创建新任务并重新校验；GET /admin/engine 和 POST /admin/engine/reconcile。
- retry/cancel 通过装配层登记的业务 service handler 调用，jobs.service 不反向导入业务模块。初始化重试需新建快照和内部名称；analysis 重试保留原快照；删除任务使用对账而非通用重试。
- heartbeat 默认 10 秒、失联阈值 60 秒；不是自动远端重试条件。

沿用 api → service → controller；所有跨业务模块调用经过 service。非 SDK 存储由本模块 repository 负责。浏览器不接触 SDK 会话或连接参数。

## 预期改动位置

以下是实现时的目标路径，本次文档编写不创建代码文件：

- `web/backend/app/worker.py`
- `web/backend/app/composition.py`
- `web/backend/app/modules/jobs/service.py`
- `web/backend/app/modules/jobs/repository.py`
- `web/backend/tests/test_worker.py`

## 实施步骤

- [x] 用虚拟 handler 先验证原子领取、心跳和终态写入，不依赖真实 SDK。
- [x] 实现 SDK 占用和 unknown 阻塞；启动时扫描失联任务而不自动重放。
- [x] 加入手动重试/管理员对账接口，限制成功/运行中任务错误重试。
- [x] 绑定独占 Session 生命周期，优雅关闭停止领取。
- [x] 运行下述验证，记录实际命令与结果，更新本文及索引状态。

## 测试与验收

- test_two_workers_one_claim：重复启动不会同时领取同一任务或使用引擎。
- test_crash_after_remote_submission：标记 interrupted/unknown，后续工作保持排队。
- test_disable_before_execution：用户已停用时不调用 SDK。
- test_retry_preserves_original：新任务关联旧任务，旧记录不改写。

后端测试在 `web/backend` 下使用 `uv run pytest` 指定上述测试文件；集成测试连接版本固定的隔离 Batfish 测试网络，不操作团队生产网络。

验收成功同时要求：契约与文档一致、失败行为可解释、无跨层/跨模块越界、没有把 mock 验证宣称为真实 SDK 验证。共享约束中的身份、版本、模型覆盖和结果截断规则均适用。

## 非目标与实施边界

- 不做分布式调度、强杀引擎、自动接管阻塞 SDK 调用。

## 完成记录

2026-09-25 完成独立app.worker、数据库进程锁、JobsService原子领取/心跳/终态/失联恢复、execution.service dispatcher与管理员API、ExecutionController真实SDK版本探测、迁移0005及ready观测。执行前复核账号；重试经登记业务handler，保留旧任务并关联retry_of。SDK factory提供独占for_job上下文，reference由后续问题调用显式传入。

仓库根执行 `web/backend/.venv/bin/python web/scripts/lab.py seed` → `smoke` → `verify`：真实服务冒烟 **10 passed**，MVP-01～09 累计 **189 passed、0 skipped**。17项worker检查包含真实PostgreSQL双领取/审计回滚/预算/并发unknown保护、真实SDK会话隔离及子进程SDK GET后SIGKILL。真实HTTP冒烟另验证worker启动ready200、第二worker拒绝、优雅停止ready503。backend Ruff、`uv lock --check`、本地文档链接及Git空白检查通过。版本/源码/逐项结果见 [证据](../../evidence/mvp-09-verification.json)。

独立审查发现的idle→busy覆盖unknown竞态和两个心跳间超预算成功均先复现再修复、复审通过；旧worker未停止时不能对账解除unknown，迟到SDK完成也不能清除栅栏。重试实测还修复MVP-08冻结参数再次提交的兼容性，新增契约回归。引擎未知保持阻塞，管理员先停worker、外部确认空闲、记录依据和审计后再解除，不自动重放或强杀引擎。

lab管理独立worker；SDK基线命令先优雅暂停其worker，进程集成测试自行启动受控子进程，结束恢复。两套配置及此前接口完整回归。虚拟handler验证执行协议，真实SDK GET/进程测试验证环境与生命周期，不宣称已实现快照/分析业务；这些handler在MVP-10及后续登记。MVP-10依赖就绪，未修改Java引擎。
