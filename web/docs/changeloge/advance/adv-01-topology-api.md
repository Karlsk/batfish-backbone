# ADV-01 三层与协议拓扑分析接口

- 状态：待开发
- 阶段：2
- 依赖：[MVP-25](../mvp/mvp-25-mvp-acceptance.md)
- 预计工作量：1.5 人天（实现/验证 1.0 + 测试 0.25 + 文档/自检 0.25），依赖就绪后计；超过 2 人天先拆分。
- 共享约束：[架构](../../architecture.md)、[API 契约](../../api-contracts.md)、[前端规范](../../frontend.md)、[运行设计](../../operations.md)、[验收](../../validation.md)。

## 需求与目标

基于已有引擎问题生成可解释的网络关系图。

- 三层边和 BGP/OSPF/ISIS 关系；节点/邻居过滤、方向与接口信息。

## 设计与接口

- POST S/analyses/topology，最小参数 view=layer3，options.nodes/remote_nodes；返回 JobDTO。
- view 白名单映射 layer3Edges/bgpEdges/ospfEdges/isisEdges；graph 结果为 nodes/edges/edge_type/source。
- GET /results/{id}/graph 使用 focus_node/hops/limit 按需读取，返回 scope/truncated；完整字段见公共API契约。
- 协议关系与会话健康不同；缺少边不能自动判定物理断线。

沿用 api → service → controller；所有跨业务模块调用经过 service。非 SDK 存储由本模块 repository 负责。浏览器不接触 SDK 会话或连接参数。

## 预期改动位置

以下是实现时的目标路径，本次文档编写不创建代码文件：

- `web/backend/app/modules/analysis/schemas/topology.py`
- `web/backend/app/modules/analysis/controllers/topology.py`
- `web/backend/app/modules/results/graph.py`
- `web/backend/tests/test_topology.py`

## 实施步骤

- [ ] 登记拓扑问题和视图枚举，按已验证模板映射参数。
- [ ] 归一化有向边、接口端点和孤立设备，稳定生成节点/边 ID。
- [ ] 增加图结果读取与筛选，保留来源类型和截断信息。
- [ ] 运行下述验证，记录实际命令与结果，更新本文及索引状态。

## 测试与验收

- test_topology_edge_identity：双向/多接口关系不错误合并。
- test_topology_matches_sdk：三层与协议视图对应原始边。
- test_isolated_node：没有边的节点仍可展示。

后端测试在 `web/backend` 下使用 `uv run pytest` 指定上述测试文件；集成测试连接版本固定的隔离 Batfish 测试网络，不操作团队生产网络。

验收成功同时要求：契约与文档一致、失败行为可解释、无跨层/跨模块越界、没有把 mock 验证宣称为真实 SDK 验证。共享约束中的身份、版本、模型覆盖和结果截断规则均适用。

## 非目标与实施边界

- 不推断没有输入依据的物理布线，不修改设备连接。

## 完成记录

当前尚未开发或运行本 spec 的产品测试。实施者完成后在本节记录实际文件、验证命令、结果、引擎/SDK版本（如涉及）和剩余限制；存在验收失败时保持未通过状态。
