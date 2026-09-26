# MVP-21 连通性表单与逐跳路径界面

- 状态：已完成
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

- [x] 实现设备/接口选择、目标 IPv4 和高级参数输入校验。
- [x] 展示实际 Flow、混合 disposition 摘要与路径计数。
- [x] 路径用可读的顺序节点/步骤列表，不引入二阶段拓扑画布。
- [x] 展示 ignore_filters、截断和模型限制，原始数据在详情层。
- [x] 运行下述验证，记录实际命令与结果，更新本文及索引状态。

## 测试与验收

- traceroute.test.tsx：多 Flow/多路径可逐个查看，不只保留首条。
- maxTraces 截断时用户能看到尚有未展示路径。
- 无路由/ACL拒绝/未知动作均显示有依据的信息。

前端组件测试在 `web/frontend` 下使用 `pnpm exec vitest run` 指定上述 `.test.tsx` 文件；页面交互同时按前端规范人工检查。

验收成功同时要求：契约与文档一致、失败行为可解释、无跨层/跨模块越界、没有把 mock 验证宣称为真实 SDK 验证。共享约束中的身份、版本、模型覆盖和结果截断规则均适用。

## 非目标与实施边界

- 不引入地图/拓扑编辑器，不解释为真实 ping 或双向连通。

## 完成记录

2026-09-26 完成最小起点设备/可选接口和目标IPv4表单，真实候选来自当前快照，字面名称编码为精确SDK表达式。专家模式显式提供start_location；源IP、协议/端口、max_traces、ignore_filters折叠保留，默认值与协议由OpenAPI生成。复用草稿保护、稳定幂等键和固定任务/结果上下文。

Flow和路径分别分页，保留所有已保存路径的disposition、报告/返回计数与截断说明。TraceSteps按真实节点和动作顺序展开，未知动作保留名称，原始Flow/trace/step在详情层。切换路径清理旧step详情。摘要持续显示模型限制、忽略ACL及单向模型说明。

实际文件：frontend/features/traceroute、components/TraceSteps、结果/路由入口、契约目录生成脚本及tests/traceroute.spec.ts。独立只读审查无阻塞项，补充两套配置的真实起点接口选择。组件测试覆盖多Flow/混合结论/未知动作及请求边界；浏览器在Cisco配置副本c2入方向加入合成ACL，验证ACCEPTED与DENIED_IN路径切换、max_traces=1截断、ignore_filters和多Flow；两套配置均验证正常路径及NO_ROUTE。未修改标准fixture。

累计验证：`lab.py smoke/verify` 为12项冒烟、260项后端全部通过；前端31项单测、10项真实Chromium测试全部通过，均0skip。OpenAPI、类型、构建、格式、Ruff、锁文件检查通过。见 [验收证据](../../evidence/mvp-21-verification.json)。已查看两套真实结果截图；共享UI包816.53kB体积提示仍保留。未做真实设备仿真精度或容量验证。满足MVP-22依赖。

### 2026-09-26 累计复验

已完成全25篇复核及实际环境累计验收。修正分析/路径表单429队列拒绝后的恢复行为，未知提交仍保留原幂等键。后端289、前端47、双主题浏览器各14、生产部署各3及双用户各1通过。详见[本轮证据](../../evidence/mvp-recheck-2026-09-26.md)。
