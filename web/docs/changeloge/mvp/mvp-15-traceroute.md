# MVP-15 IPv4 单向虚拟 traceroute 接口

- 状态：待开发
- 阶段：1
- 依赖：[MVP-14](../mvp/mvp-14-routing.md)
- 预计工作量：2.0 人天（实现/验证 1.25 + 测试 0.5 + 文档/自检 0.25），依赖就绪后计；超过 2 人天先拆分。
- 共享约束：[架构](../../architecture.md)、[API 契约](../../api-contracts.md)、[前端规范](../../frontend.md)、[运行设计](../../operations.md)、[验收](../../validation.md)。

## 需求与目标

按最小流量条件提供可解释、多路径的转发分析。

- 起点/目标、可选源/协议/端口、max_traces、ignore_filters、Flow/Trace 归一化。

## 设计与接口

- POST S/analyses/traceroute → JobDTO，参数映射见 api-contracts.md。
- ResultEnvelope.kind=traces；每个 Flow 分别有 trace_count/returned_trace_count/disposition/hops/steps。
- 缺少可推导源地址时返回明确分析错误，不随意用设备管理地址。

沿用 api → service → controller；所有跨业务模块调用经过 service。非 SDK 存储由本模块 repository 负责。浏览器不接触 SDK 会话或连接参数。

## 预期改动位置

以下是实现时的目标路径，本次文档编写不创建代码文件：

- `web/backend/app/modules/analysis/schemas/traceroute.py`
- `web/backend/app/modules/analysis/controllers/traceroute.py`
- `web/backend/app/modules/analysis/services/traceroute.py`
- `web/backend/tests/test_traceroute.py`

## 实施步骤

- [ ] 校验必要地址、协议端口组合和专家选项，构造 HeaderConstraints。
- [ ] 保存实际 Flow、所有返回路径和逐跳动作；统一未知枚举的可显示形式。
- [ ] 结果摘要按 disposition 分组，保留覆盖限制/截断/忽略过滤标记。
- [ ] 运行下述验证，记录实际命令与结果，更新本文及索引状态。

## 测试与验收

- test_trace_matches_sdk：已知成功/无路由/拒绝路径一致。
- test_ecmp_mixed_dispositions：部分成功不简化成全部可达。
- test_trace_limit：maxTraces 限制时保留总数和截断标记。
- test_model_warning_propagates：华为/H3C限制出现在结果元数据。

后端测试在 `web/backend` 下使用 `uv run pytest` 指定上述测试文件；集成测试连接版本固定的隔离 Batfish 测试网络，不操作团队生产网络。

验收成功同时要求：契约与文档一致、失败行为可解释、无跨层/跨模块越界、没有把 mock 验证宣称为真实 SDK 验证。共享约束中的身份、版本、模型覆盖和结果截断规则均适用。

## 非目标与实施边界

- 不做回程证明、全流量可达性或真实发包。

## 完成记录

当前尚未开发或运行本 spec 的产品测试。实施者完成后在本节记录实际文件、验证命令、结果、引擎/SDK版本（如涉及）和剩余限制；存在验收失败时保持未通过状态。
