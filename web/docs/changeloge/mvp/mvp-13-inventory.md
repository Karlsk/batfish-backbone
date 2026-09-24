# MVP-13 设备与接口分析接口

- 状态：待开发
- 阶段：1
- 依赖：[MVP-12](../mvp/mvp-12-analysis-results.md)
- 预计工作量：1.5 人天（实现/验证 1.0 + 测试 0.25 + 文档/自检 0.25），依赖就绪后计；超过 2 人天先拆分。
- 共享约束：[架构](../../architecture.md)、[API 契约](../../api-contracts.md)、[前端规范](../../frontend.md)、[运行设计](../../operations.md)、[验收](../../validation.md)。

## 需求与目标

通过首批专用接口验证分析管道，并支持页面设备选择。

- nodeProperties/interfaceProperties、节点/接口/属性筛选、结果字段展示映射。

## 设计与接口

- POST S/analyses/nodes、POST S/analyses/interfaces → 202 JobDTO。
- nodes/interfaces 支持显式字面选择或专家表达式，模式清晰，字面值需安全转义。
- 仅支持模型已有属性，不将解析出的 IPv6 地址等同于可做 IPv6 仿真。

沿用 api → service → controller；所有跨业务模块调用经过 service。非 SDK 存储由本模块 repository 负责。浏览器不接触 SDK 会话或连接参数。

## 预期改动位置

以下是实现时的目标路径，本次文档编写不创建代码文件：

- `web/backend/app/modules/analysis/api.py`
- `web/backend/app/modules/analysis/schemas/inventory.py`
- `web/backend/app/modules/analysis/controllers/inventory.py`
- `web/backend/tests/test_inventory.py`

## 实施步骤

- [ ] 登记两类问题的参数、展示列和 result_kind。
- [ ] 实现 controller 映射，service 判断快照状态与能力。
- [ ] 用结果接口分页返回；用于选择器的数据仍来源于绑定快照的结果。
- [ ] 运行下述验证，记录实际命令与结果，更新本文及索引状态。

## 测试与验收

- test_inventory_matches_sdk：稳定列与直接 SDK 一致。
- test_literal_node_names：带特殊字符的设备名称可被正确选择。
- test_no_matching_nodes：正常空结果，有明确说明。

后端测试在 `web/backend` 下使用 `uv run pytest` 指定上述测试文件；集成测试连接版本固定的隔离 Batfish 测试网络，不操作团队生产网络。

验收成功同时要求：契约与文档一致、失败行为可解释、无跨层/跨模块越界、没有把 mock 验证宣称为真实 SDK 验证。共享约束中的身份、版本、模型覆盖和结果截断规则均适用。

## 非目标与实施边界

- 不做拓扑、BGP 专页或设备实时状态。

## 完成记录

当前尚未开发或运行本 spec 的产品测试。实施者完成后在本节记录实际文件、验证命令、结果、引擎/SDK版本（如涉及）和剩余限制；存在验收失败时保持未通过状态。
