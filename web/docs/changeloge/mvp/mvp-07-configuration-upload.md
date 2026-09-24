# MVP-07 配置上传与输入校验

- 状态：待开发
- 阶段：1
- 依赖：[MVP-06](../mvp/mvp-06-network-management.md)
- 预计工作量：2.0 人天（实现/验证 1.25 + 测试 0.5 + 文档/自检 0.25），依赖就绪后计；超过 2 人天先拆分。
- 共享约束：[架构](../../architecture.md)、[API 契约](../../api-contracts.md)、[前端规范](../../frontend.md)、[运行设计](../../operations.md)、[验收](../../validation.md)。

## 需求与目标

将文件安全地转换为可初始化快照输入，同时保留原始配置。

- 多文件/单 ZIP 上传、manifest/hash、目录/大小/条目校验、临时文件清理。

## 设计与接口

- POST /networks/{id}/uploads → 201 UploadDTO。
- UploadsService.consume(actor, network_id, upload_id) → UploadManifest；上传仅所有者或管理员可消费，绑定 network。
- ZIP 限额、configs 根识别和原始字节保留按 operations.md。

沿用 api → service → controller；所有跨业务模块调用经过 service。非 SDK 存储由本模块 repository 负责。浏览器不接触 SDK 会话或连接参数。

## 预期改动位置

以下是实现时的目标路径，本次文档编写不创建代码文件：

- `web/backend/app/modules/uploads/api.py`
- `web/backend/app/modules/uploads/service.py`
- `web/backend/app/modules/uploads/repository.py`
- `web/backend/app/modules/uploads/archive.py`
- `web/backend/tests/test_uploads.py`

## 实施步骤

- [ ] 实现流式接收和实际字节限额，生成内部目录与内容摘要。
- [ ] 验证 ZIP 单根、路径、链接、加密、文件冲突及解压限额。
- [ ] 保留 UTF-8/GB18030 原始文件，生成文件 ID 与行查看所需元数据。
- [ ] 失败清理临时文件，建立过期上传清理入口。
- [ ] 运行下述验证，记录实际命令与结果，更新本文及索引状态。

## 测试与验收

- test_traversal_and_symlink_rejected：内容不写出专属目录。
- test_zip_limits_and_multiple_roots：提前拒绝且无残留。
- test_original_bytes_preserved：GB18030/终端字符字节不改写。
- test_upload_owner_and_network：其他成员不能消费未发布上传。

后端测试在 `web/backend` 下使用 `uv run pytest` 指定上述测试文件；集成测试连接版本固定的隔离 Batfish 测试网络，不操作团队生产网络。

验收成功同时要求：契约与文档一致、失败行为可解释、无跨层/跨模块越界、没有把 mock 验证宣称为真实 SDK 验证。共享约束中的身份、版本、模型覆盖和结果截断规则均适用。

## 非目标与实施边界

- 不触发 SDK 初始化，不做前端拖拽界面或在线编辑配置。

## 完成记录

当前尚未开发或运行本 spec 的产品测试。实施者完成后在本节记录实际文件、验证命令、结果、引擎/SDK版本（如涉及）和剩余限制；存在验收失败时保持未通过状态。
