# MVP-10 快照初始化与不可变生命周期

- 状态：待开发
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

- [ ] 创建 UUID/内部名称，原子消费上传并提交初始化任务。
- [ ] 在 worker handler 中调用 init_snapshot，保存状态和版本信息。
- [ ] 初始化后调用 fileParseStatus/initIssues 形成最小质量门，具体展示/诊断分页在 MVP-11。
- [ ] 初始 ready/ready_with_warnings/failed 由质量判定决定，不只依据 SDK 返回名称。
- [ ] 运行下述验证，记录实际命令与结果，更新本文及索引状态。

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

当前尚未开发或运行本 spec 的产品测试。实施者完成后在本节记录实际文件、验证命令、结果、引擎/SDK版本（如涉及）和剩余限制；存在验收失败时保持未通过状态。
