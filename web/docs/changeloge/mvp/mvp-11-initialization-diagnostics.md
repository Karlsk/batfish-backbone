# MVP-11 解析质量与原始文件查看

- 状态：待开发
- 阶段：1
- 依赖：[MVP-10](../mvp/mvp-10-snapshot-initialization.md)
- 预计工作量：1.5 人天（实现/验证 1.0 + 测试 0.25 + 文档/自检 0.25），依赖就绪后计；超过 2 人天先拆分。
- 共享约束：[架构](../../architecture.md)、[API 契约](../../api-contracts.md)、[前端规范](../../frontend.md)、[运行设计](../../operations.md)、[验收](../../validation.md)。

## 需求与目标

用户能判断配置被理解到什么程度，并定位真实源文件。

- 诊断分页、文件清单、按行读取；厂商能力限制附着快照元数据。

## 设计与接口

- GET S/diagnostics、GET S/files、GET S/files/{file_id}。
- fileParseStatus/initIssues/parseWarning/viConversionWarning 的可用字段以兼容性基线为准。
- FAILED/UNKNOWN/UNSUPPORTED 阻止业务分析；部分识别进入 ready_with_warnings。已知不支持的具体分析范围由 analysis service 拒绝。

沿用 api → service → controller；所有跨业务模块调用经过 service。非 SDK 存储由本模块 repository 负责。浏览器不接触 SDK 会话或连接参数。

## 预期改动位置

以下是实现时的目标路径，本次文档编写不创建代码文件：

- `web/backend/app/modules/snapshots/service.py`
- `web/backend/app/modules/snapshots/controller.py`
- `web/backend/app/modules/snapshots/schemas.py`
- `web/backend/tests/test_diagnostics.py`

## 实施步骤

- [ ] 归一化文件状态、严重程度、描述和可用源位置，保留原始枚举。
- [ ] 增加 H3C/Huawei 覆盖声明；无法判断细粒度覆盖时标记 limited/unknown。
- [ ] 按 file_id 读取原始配置并做受控解码/分页，不返回服务器路径。
- [ ] 运行下述验证，记录实际命令与结果，更新本文及索引状态。

## 测试与验收

- test_missing_source_line：没有行号时不伪造定位。
- test_vendor_limits_visible：解析 PASSED 仍附带未模拟能力说明。
- test_file_access_bounds：负行号/超限分页/跨快照 file_id 明确拒绝。

后端测试在 `web/backend` 下使用 `uv run pytest` 指定上述测试文件；集成测试连接版本固定的隔离 Batfish 测试网络，不操作团队生产网络。

验收成功同时要求：契约与文档一致、失败行为可解释、无跨层/跨模块越界、没有把 mock 验证宣称为真实 SDK 验证。共享约束中的身份、版本、模型覆盖和结果截断规则均适用。

## 非目标与实施边界

- 不修改原始配置，不实现新的 Java parser 或源行推断。

## 完成记录

当前尚未开发或运行本 spec 的产品测试。实施者完成后在本节记录实际文件、验证命令、结果、引擎/SDK版本（如涉及）和剩余限制；存在验收失败时保持未通过状态。
