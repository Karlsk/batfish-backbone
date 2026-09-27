# LDR-08 ADV 拓扑、BGP、ACL 与专家下钻

- 状态：已完成；阶段：领导端；依赖：[LDR-07](ldr-07-mvp-guided-checks.md)；预计 2.0 人天。
- 共享约束：[领导端设计](../../leader-design.md)、[前端规范](../../frontend.md)、[SDK 覆盖表](../../sdk-coverage.md)。

## 需求与接口

在领导端自主检查中覆盖 ADV-01～10：拓扑默认展示模型推导边和设备聚焦，BGP 展示会话状态与模型覆盖，ACL 对明确 flow 或规则范围展示 permit/deny/无匹配，专家能力仅列服务端已登记项。图形与数量只来自保存的结果；采样、截断和不支持厂商在第一层标示。专业查询参数、原始规则/会话/图结构深链至技术端。

复用 LDR-06 模板/运行记录和既有结果 graph/table API；页面不调用 SDK，也不把隐式拒绝、空条件或路径变化说成“业务中断”。拓扑图可读、可聚焦，会议式动画只表达已知边而不虚构流量。

## 改动位置与步骤

- `web/frontend/src/features/leader/checks/` 的 ADV 结论适配器和 `web/frontend/src/features/leader/topology/` 的聚焦图；复用现有 Cytoscape 与主题 token。
- 先写来源、聚焦、模型限制、ACL 三类结果、未知专家能力和截断测试，再实现；浏览器在 Cisco 四设备真实结果上验证。

## 验收

拓扑范围与边来源可查；BGP 模型/实际会话状态分开；ACL 显示显式/隐式拒绝和空匹配；未登记专家能力不可执行。前端单测/API 检查/类型/构建/格式、真实浏览器与 LDR-01～07 累计回归通过。

## 非目标与完成记录

不声称推导拓扑为物理链路，不让领导端执行任意 SDK 查询。回写改动、证据、版本与限制。

### 2026-09-28 实施与验收

在自主检查页增加拓扑、BGP、ACL 三个服务端已登记模板：拓扑可选三层/BGP/OSPF/ISIS 模型关系与设备范围，详情按固定结果绘制可聚焦邻域；BGP 可选模型状态/配置兼容性，行数和状态仅表示已保存范围；ACL 要求明确源、目的地址和 ACL 名称，可选设备/协议/端口，并区分放行、显式拒绝、隐式拒绝、无匹配与分页未知。专家能力列表来自 `/capabilities`，自定义参数跳现有技术工作台；不提供任意 SDK 调用。模型限制、来源、截断和技术结果 ID 保留在结论/证据层。

新增 `web/frontend/src/features/leader/checks/{advanced.ts,advanced.test.ts,AdvancedEvidence.tsx}`、`web/frontend/src/features/leader/topology/FocusedGraph.tsx` 和真实浏览器 `web/frontend/tests/leader-advanced-checks.spec.ts`；扩展 `ChecksPage.tsx` 与主题样式。`web/frontend` 执行 `pnpm check:api`、`pnpm test`（108 passed）、`pnpm build`（含 TypeScript）、`pnpm format:check` 均通过；隔离环境当前源码 API/独立 worker/PostgreSQL/Batfish 的累计浏览器 17 passed，含同一派生 Cisco 四设备快照的 BGP `NOT_COMPATIBLE` 与 ACL permit、显式/隐式 deny。LDR-06 的后端全量 385 passed 基线仍适用，本篇未改后端/API 契约；详细证据见[验收记录](../../evidence/ldr-08-verification.md)。LDR-09 前置满足。只验证配置模型工作流，不证明现场链路、会话或设备转发精度。
