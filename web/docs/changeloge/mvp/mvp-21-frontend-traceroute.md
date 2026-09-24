# MVP-21 连通性表单与逐跳路径界面

- 状态：待开发
- 阶段：1
- 依赖：[MVP-15](../mvp/mvp-15-traceroute.md)、[MVP-20](../mvp/mvp-20-frontend-inventory-routing.md)
- 预计工作量：2.0 人天（实现/验证 1.25 + 测试 0.5 + 文档/自检 0.25），依赖就绪后计；超过 2 人天先拆分。
- 共享约束：[架构](../../architecture.md)、[API 契约](../../api-contracts.md)、[前端规范](../../frontend.md)、[运行设计](../../operations.md)、[验收](../../validation.md)。

## 需求与目标

用户输入起点和目标后能理解分析结论及证据。

- 最小表单、高级选项、任务状态、Flow 分组、路径切换、hop/动作详情。

## 设计与接口

- 使用已登记 traceroute 参数，不另造前端默认语义。
- 从 /results/{id}/flows 和 traces 按需加载；所有路径保留 disposition。

沿用 api → service → controller；所有跨业务模块调用经过 service。非 SDK 存储由本模块 repository 负责。浏览器不接触 SDK 会话或连接参数。

## 预期改动位置

以下是实现时的目标路径，本次文档编写不创建代码文件：

- `web/frontend/src/features/traceroute/`
- `web/frontend/src/components/TraceSteps.tsx`
- `web/frontend/src/features/traceroute/traceroute.test.tsx`

## 实施步骤

- [ ] 实现设备/接口选择、目标 IPv4 和高级参数输入校验。
- [ ] 展示实际 Flow、混合 disposition 摘要与路径计数。
- [ ] 路径用可读的顺序节点/步骤列表，不引入二阶段拓扑画布。
- [ ] 展示 ignore_filters、截断和模型限制，原始数据在详情层。
- [ ] 运行下述验证，记录实际命令与结果，更新本文及索引状态。

## 测试与验收

- traceroute.test.tsx：多 Flow/多路径可逐个查看，不只保留首条。
- maxTraces 截断时用户能看到尚有未展示路径。
- 无路由/ACL拒绝/未知动作均显示有依据的信息。

前端组件测试在 `web/frontend` 下使用 `pnpm exec vitest run` 指定上述 `.test.tsx` 文件；页面交互同时按前端规范人工检查。

验收成功同时要求：契约与文档一致、失败行为可解释、无跨层/跨模块越界、没有把 mock 验证宣称为真实 SDK 验证。共享约束中的身份、版本、模型覆盖和结果截断规则均适用。

## 非目标与实施边界

- 不引入地图/拓扑编辑器，不解释为真实 ping 或双向连通。

## 完成记录

当前尚未开发或运行本 spec 的产品测试。实施者完成后在本节记录实际文件、验证命令、结果、引擎/SDK版本（如涉及）和剩余限制；存在验收失败时保持未通过状态。
