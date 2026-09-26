# ADV-01 三层与协议拓扑分析接口

- 状态：已完成
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

- [x] 登记拓扑问题和视图枚举，按已验证模板映射参数。
- [x] 归一化有向边、接口端点和孤立设备，稳定生成节点/边 ID。
- [x] 增加图结果读取与筛选，保留来源类型和截断信息。
- [x] 运行下述验证，记录实际命令与结果，更新本文及索引状态。

## 测试与验收

- test_topology_edge_identity：双向/多接口关系不错误合并。
- test_topology_matches_sdk：三层与协议视图对应原始边。
- test_isolated_node：没有边的节点仍可展示。

后端测试在 `web/backend` 下使用 `uv run pytest` 指定上述测试文件；集成测试连接版本固定的隔离 Batfish 测试网络，不操作团队生产网络。

验收成功同时要求：契约与文档一致、失败行为可解释、无跨层/跨模块越界、没有把 mock 验证宣称为真实 SDK 验证。共享约束中的身份、版本、模型覆盖和结果截断规则均适用。

## 非目标与实施边界

- 不推断没有输入依据的物理布线，不修改设备连接。

## 完成记录

2026-09-26：已完成，基线为MVP累计复验提交 `b59995435c`。

- 新增 `analysis/schemas/topology.py`、`analysis/controllers/topology.py`、`results/graph.py` 及 `tests/test_topology.py`；更新analysis注册/API/同Session执行、公共Graph DTO、结果发布/读取API、分层守卫与真实worker冒烟；同步API契约与前端生成类型。
- 后端与SDK：仓库根执行 `web/backend/.venv/bin/python web/scripts/lab.py verify`，307通过、0跳过；另跑 `lab.py smoke`，12通过。三套配置（r1/r2、Cisco四设备、启用BGP/ISIS并带孤立节点的Cisco派生）四视图均与独立序列化的SDK原始行一致，派生协议视图要求非空。
- 前端目录执行 `pnpm test`（47通过）、`pnpm build`、`pnpm check:api`、`pnpm format:check`（均通过）；`pnpm exec playwright test --output=../.runtime/adv01-browser` 14通过。Ruff、文档链接、Git空白检查通过。
- 引擎revision `7d0deeeac4a09973b3876327f6aef721ee12f955`，SDK `2026.9.17.3748`，Python `3.12.12`；实际测试环境与机器证据见[验收报告](../../evidence/adv-01-verification.md)。
- 首轮分层守卫失败已按纯结果处理文件补充精确规则及反向测试，最终全量通过。独立审查指出的契约遗漏已修正，无未解决阻断。
- 满足ADV-02前置条件；图形页面尚未实施。只验证配置模型功能，不声明会话健康、物理链路或现场转发一致性；不新增100设备规模结论。本篇未重建生产部署镜像，MVP部署证据仅属于前置提交。

### 连续批次复验

本次补齐当前源码全新部署恢复及双主题双用户门槛，全部通过，允许提交并继续ADV-02。见[批次证据](../../evidence/adv-01-verification.md)。
