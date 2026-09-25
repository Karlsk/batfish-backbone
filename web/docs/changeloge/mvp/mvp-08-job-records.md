# MVP-08 任务记录、幂等与排队取消

- 状态：已完成
- 阶段：1
- 依赖：[MVP-07](../mvp/mvp-07-configuration-upload.md)
- 预计工作量：1.5 人天（实现/验证 1.0 + 测试 0.25 + 文档/自检 0.25），依赖就绪后计；超过 2 人天先拆分。
- 共享约束：[架构](../../architecture.md)、[API 契约](../../api-contracts.md)、[前端规范](../../frontend.md)、[运行设计](../../operations.md)、[验收](../../validation.md)。

## 需求与目标

所有长操作拥有可查询的持久化任务身份。

- submit/list/detail、Idempotency-Key、队列限额、queued 取消、历史重试元数据。

## 设计与接口

- JobsService.submit(actor, kind, context, parameters, idempotency_key) → JobDTO。
- GET /jobs、GET /jobs/{id}、POST /jobs/{id}/cancel；重试执行接入由 MVP-09 完成。
- 只有所有者/管理员可取消 queued；running 返回 409；同 key 不同正文返回 409。
- JobDTO.cancel_allowed 由 kind 和状态共同决定；删除任务不开放取消。初始化取消后的快照状态由 snapshots.service 按 initialization_job_id 派生为失败，不需要 jobs 模块反向修改快照表。

沿用 api → service → controller；所有跨业务模块调用经过 service。非 SDK 存储由本模块 repository 负责。浏览器不接触 SDK 会话或连接参数。

## 预期改动位置

以下是实现时的目标路径，本次文档编写不创建代码文件：

- `web/backend/app/modules/jobs/api.py`
- `web/backend/app/modules/jobs/service.py`
- `web/backend/app/modules/jobs/repository.py`
- `web/backend/tests/test_jobs.py`

## 实施步骤

- [x] 实现状态转换表与不可变输入上下文。
- [x] 持久化请求摘要及幂等记录，应用每用户/全局排队限额。
- [x] 实现分页历史、所有权校验和排队取消的原子条件更新。
- [x] 运行下述验证，记录实际命令与结果，更新本文及索引状态。

## 测试与验收

- test_idempotent_submission：重复点击只产生一个任务。
- test_idempotency_payload_conflict：参数不同明确冲突。
- test_cancel_race：任务已领取后取消不能伪成功。
- test_queue_limit：超限 429 且不落半条任务。

后端测试在 `web/backend` 下使用 `uv run pytest` 指定上述测试文件；集成测试连接版本固定的隔离 Batfish 测试网络，不操作团队生产网络。

验收成功同时要求：契约与文档一致、失败行为可解释、无跨层/跨模块越界、没有把 mock 验证宣称为真实 SDK 验证。共享约束中的身份、版本、模型覆盖和结果截断规则均适用。

## 非目标与实施边界

- 不调用 SDK，不提供运行中强制取消。

## 完成记录

2026-09-25 完成 JobsService.submit/list/get/cancel、共享分页API、队列限额、事务幂等、不可变ExecutionContext与迁移0004（context/retry_of）。提交方service仍负责业务资源映射与权限；jobs不反向导入networks/snapshots，不提供任意SDK任务HTTP入口。取消仅发起人/管理员可操作queued非deletion任务，行锁与状态条件更新防止领取竞态；cancel_allowed由service按当前状态派生。

仓库根运行 `web/backend/.venv/bin/python web/scripts/lab.py seed` → `smoke` → `verify`：真实服务冒烟 **9 passed**，MVP-01～08 累计 **170 passed、0 skipped**，包含9项任务数据库测试、1项AnalysisContext衔接契约测试与真实HTTP任务历史/取消。并发同键提交只产生一条任务；每用户/全局限额无超卖，失败回滚幂等记录。backend Ruff、`uv lock --check`、文档链接与Git空白检查通过。独立审查发现的AnalysisContext父类实例提交不兼容已通过先红后绿测试修复并复审。版本/源码/逐项结果见 [证据](../../evidence/mvp-08-verification.json)。

两套配置的SDK、上传和既有功能均累计回归。MVP-09依赖就绪；worker、实际执行、重试与管理员对账尚未实现，本篇无后台计算成功声明。未修改Java引擎。
