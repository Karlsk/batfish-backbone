# MVP-10 快照初始化与不可变生命周期

- 状态：已完成
- 阶段：1
- 依赖：[MVP-09](../mvp/mvp-09-worker-recovery.md)
- 预计工作量：2.0 人天（实现/验证 1.25 + 测试 0.5 + 文档/自检 0.25），依赖就绪后计；超过 2 人天先拆分。
- 共享约束：[架构](../../architecture.md)、[API 契约](../../api-contracts.md)、[前端规范](../../frontend.md)、[运行设计](../../operations.md)、[验收](../../validation.md)。

## 需求与目标

用户将已校验上传变成可追踪的 Batfish 快照。

- 创建/列表/详情、消费上传、初始化 job、SDK 映射、原始输入 manifest 保存。

## 设计与接口

- POST /networks/{id}/snapshots → {snapshot_id,job_id}；GET 列表和详情。
- SnapshotController.initialize(context, manifest, options) → InitializationAnswer。
- options 只登记 ignore_management_interfaces/parse_reuse，映射已验证 extra_args；overwrite 永远 false。
- 保存 initialization_job_id；取消/中断初始化时快照有效状态为 failed。初始化重试复用原始输入副本但创建新的 snapshot_id/engine_name，不能覆盖旧引擎对象；重试响应包括新 snapshot_id 与 job_id。

沿用 api → service → controller；所有跨业务模块调用经过 service。非 SDK 存储由本模块 repository 负责。浏览器不接触 SDK 会话或连接参数。

## 预期改动位置

以下是实现时的目标路径，本次文档编写不创建代码文件：

- `web/backend/app/modules/snapshots/api.py`
- `web/backend/app/modules/snapshots/service.py`
- `web/backend/app/modules/snapshots/controller.py`
- `web/backend/app/modules/snapshots/repository.py`
- `web/backend/tests/test_snapshots.py`

## 实施步骤

- [x] 创建 UUID/内部名称，原子消费上传并提交初始化任务。
- [x] 在 worker handler 中调用 init_snapshot，保存状态和版本信息。
- [x] 初始化后调用 fileParseStatus/initIssues 形成最小质量门，具体展示/诊断分页在 MVP-11。
- [x] 初始 ready/ready_with_warnings/failed 由质量判定决定，不只依据 SDK 返回名称。
- [x] 运行下述验证，记录实际命令与结果，更新本文及索引状态。

## 测试与验收

- test_overwrite_impossible：同显示名新快照不覆盖已有数据。
- test_upload_consumed_once：并发初始化只消费一次。
- test_failed_initialization：保留来源、错误与文件，禁止发起分析。
- test_partial_parse_not_clean：不显示无警告 ready。
- test_cancel_and_retry_initialization：取消后不永久queued；重试使用新内部名称且不再次消费原 upload token。

后端测试在 `web/backend` 下使用 `uv run pytest` 指定上述测试文件；集成测试连接版本固定的隔离 Batfish 测试网络，不操作团队生产网络。

验收成功同时要求：契约与文档一致、失败行为可解释、无跨层/跨模块越界、没有把 mock 验证宣称为真实 SDK 验证。共享约束中的身份、版本、模型覆盖和结果截断规则均适用。

## 非目标与实施边界

- 不做增量配置编辑、fork、删除和差异比较。

## 完成记录

2026-09-25 完成 snapshots api/service/controller/repository/schemas、迁移0006、UploadsService共享事务消费与受控物化，以及API/worker初始化和重试handler装配。原子消费上传并保存manifest、内容摘要、options、job；同名显示标签仍生成新UUID和内部名称，初始化固定overwrite=false。重试创建新快照与job并复用原始输入，不重复消费上传。

实际SDK初始化后读取fileParseStatus/initIssues，保存引擎及SDK版本。无节点或FAILED失败，部分识别/初始化问题显示ready_with_warnings。取消、中断、失败按关联job派生failed；require_analyzable只允许可用快照。MVP-11继续补充UNKNOWN/UNSUPPORTED的阻断、厂商模型覆盖声明、诊断与文件分页。

仓库根执行 `web/backend/.venv/bin/python web/scripts/lab.py seed`、`smoke`、`verify`：真实HTTP冒烟 **12 passed**；MVP-01～10累计 **201 passed、0 skipped**。两套ZIP分别经过真实上传/创建接口、独立CLI worker和固定Batfish初始化。10项快照测试覆盖并发单次消费、任务创建失败回滚、幂等、同名不覆盖、取消和中断对账后新身份重试、options/网络边界、真实两套拓扑及合成未知命令、失败保留输入并拒绝分析。Ruff、锁文件、文档链接和Git空白检查通过；独立只读审查无阻断项。详见 [验收证据](../../evidence/mvp-10-verification.json)。

累计验证发现并修正lab清单的迁移号0005→0006，重新启动环境并全量复验。版本仍为Batfish 0.36.0、Pybatfish 2026.9.17.3748，JAR及输入摘要记录在证据；未修改Java引擎、未使用真实路由器、未声称验证现场转发一致性。MVP-11前置依赖就绪。
