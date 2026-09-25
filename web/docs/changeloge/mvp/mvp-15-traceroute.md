# MVP-15 IPv4 单向虚拟 traceroute 接口

- 状态：已完成
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

- [x] 校验必要地址、协议端口组合和专家选项，构造 HeaderConstraints。
- [x] 保存实际 Flow、所有返回路径和逐跳动作；统一未知枚举的可显示形式。
- [x] 结果摘要按 disposition 分组，保留覆盖限制/截断/忽略过滤标记。
- [x] 运行下述验证，记录实际命令与结果，更新本文及索引状态。

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

2026-09-25 完成traceroute专用请求/接口、固定HeaderConstraints映射和目录启用，沿用现有AnalysisService执行/缓存/发布管道，无新增空业务层。默认icmp/max_traces=5/ignore_filters=false，IPv4单地址、协议端口组合、严格布尔/整数边界明确校验；AH映射固定引擎AHP名称。SDK推导源地址，展示实际Flow，不选管理地址替代。

TraceFlow新增返回路径disposition计数；结果摘要明确计数只覆盖已保存Flow/返回路径，保留trace_count/returned_trace_count、原始hops/steps和未知枚举。混合成功/拒绝并存展示，不生成全部可达布尔结论。maxTraces/行/字节截断保持可见；ignore_filters、单向模型推演限制及华为/H3C覆盖限制进入结果摘要/警告。候选协议端口是SDK的代表Flow约束，不承诺穷举组合。

无源地址场景先真实复现；公开工作状态只给泛化错误，再通过公开get_answer的失败答案提取已知类别并生成固定source_ip提示；无活动起点提示start_location。原堆栈不持久化为结果、不返回用户；诊断文本不参与引擎占用判定，只有已知终态才允许释放，网络/超时未知规则保持。

仓库根执行 `web/backend/.venv/bin/python web/scripts/lab.py seed`、`smoke`、`verify`：真实HTTP/CLI worker冒烟 **12 passed**，两套配置均执行五类分析并读取Flow/Trace；MVP-01～15累计 **259 passed、0 skipped**。7项专项测试覆盖严格参数、两套配置与SDK逐Flow/Trace一致的成功和NO_ROUTE、Cisco ECMP成功+DENIED_IN混合/maxTraces截断/ignore_filters、缺源地址及显式source_ip恢复、未知枚举与存储截断统计、AH映射。见 [验收证据](../../evidence/mvp-15-verification.json)。

独立审查无阻断；Ruff、锁文件、Markdown链接及Git空白检查通过。固定Batfish0.36.0/Pybatfish2026.9.17.3748/JAR，未改Java。后端MVP-01～15已验证，不等于MVP-25整体交付；继续MVP-16前端骨架与浏览器验收。
