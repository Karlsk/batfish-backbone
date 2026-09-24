# MVP-02 后端骨架与分层约束

- 状态：待开发
- 阶段：1
- 依赖：[MVP-01](../mvp/mvp-01-sdk-compatibility.md)
- 预计工作量：1.0 人天（实现/验证 0.5 + 测试 0.25 + 文档/自检 0.25），依赖就绪后计；超过 2 人天先拆分。
- 共享约束：[架构](../../architecture.md)、[API 契约](../../api-contracts.md)、[前端规范](../../frontend.md)、[运行设计](../../operations.md)、[验收](../../validation.md)。

## 需求与目标

建立可启动、可测试、层次清晰的 FastAPI 工程。

- 独立 Python 依赖与锁文件、应用配置、健康接口、统一错误、公共 DTO。
- 导入约束测试；明确 controller 命名和 composition 装配例外。

## 设计与接口

- 版本输入以 [MVP-01 实测报告](../../sdk-compatibility.md) 为准：Python 3.12、Pybatfish 2026.9.17.3748；不可安装文档版本号 `pybatfish==0.36.0`。本篇生成应用锁文件。

- GET /health/live 返回存活；GET /health/ready 仅在依赖就绪后 ready。
- 错误对象统一 code/message/field_errors/request_id/retryable。
- 公共契约遵循 api-contracts.md；不在 api/service 导入 pybatfish。

沿用 api → service → controller；所有跨业务模块调用经过 service。非 SDK 存储由本模块 repository 负责。浏览器不接触 SDK 会话或连接参数。

## 预期改动位置

以下是实现时的目标路径，本次文档编写不创建代码文件：

- `web/backend/pyproject.toml`
- `web/backend/app/main.py`
- `web/backend/app/composition.py`
- `web/backend/app/contracts/`
- `web/backend/app/infrastructure/settings.py`
- `web/backend/tests/test_architecture.py`

## 实施步骤

- [ ] 建立最小包与开发测试命令，依据兼容性报告锁定 SDK。
- [ ] 定义 Actor、AnalysisContext、JobDTO、ResultEnvelope 和异常类型。
- [ ] 实现健康路由、错误映射、request_id；敏感配置不参与日志输出。
- [ ] 添加禁止跨模块 repository/controller 导入及跨层 SDK 导入的检查。
- [ ] 运行下述验证，记录实际命令与结果，更新本文及索引状态。

## 测试与验收

- test_live_without_batfish：引擎不可用不影响 liveness。
- test_error_shape：校验错误保持字段路径，无堆栈/凭证。
- test_import_boundaries：故意违规的小样例能被约束检测。

后端测试在 `web/backend` 下使用 `uv run pytest` 指定上述测试文件；集成测试连接版本固定的隔离 Batfish 测试网络，不操作团队生产网络。

验收成功同时要求：契约与文档一致、失败行为可解释、无跨层/跨模块越界、没有把 mock 验证宣称为真实 SDK 验证。共享约束中的身份、版本、模型覆盖和结果截断规则均适用。

## 非目标与实施边界

- 不实现账号、数据库业务表或分析执行。

## 完成记录

当前尚未开发或运行本 spec 的产品测试。实施者完成后在本节记录实际文件、验证命令、结果、引擎/SDK版本（如涉及）和剩余限制；存在验收失败时保持未通过状态。
