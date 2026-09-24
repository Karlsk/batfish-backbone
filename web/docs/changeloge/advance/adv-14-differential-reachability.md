# ADV-14 差异可达性分析接口

- 状态：待开发
- 阶段：3
- 依赖：[ADV-13](../advance/adv-13-routing-diff.md)
- 预计工作量：2.0 人天（实现/验证 1.25 + 测试 0.5 + 文档/自检 0.25），依赖就绪后计；超过 2 人天先拆分。
- 共享约束：[架构](../../architecture.md)、[API 契约](../../api-contracts.md)、[前端规范](../../frontend.md)、[运行设计](../../operations.md)、[验收](../../validation.md)。

## 需求与目标

查找两份快照在明确流量和路径条件下的可达性变化。

- differentialReachability、headers/path constraints、示例 flow 及两侧路径。

## 设计与接口

- POST /comparisons/{id}/analyses/reachability-diff：destination_ips、start_location；options.source_ips/ip_protocols/destination_ports/max_traces。
- 范围必须明确，不默认无限制全网搜索；专家 action/invert_search 等仅在 schema 登记后启用。
- 两侧同一个 flow 按 disposition 判定新增/消失可达性，不把示例数量当全部受影响业务数量。

沿用 api → service → controller；所有跨业务模块调用经过 service。非 SDK 存储由本模块 repository 负责。浏览器不接触 SDK 会话或连接参数。

## 预期改动位置

以下是实现时的目标路径，本次文档编写不创建代码文件：

- `web/backend/app/modules/changes/schemas.py`
- `web/backend/app/modules/changes/controller.py`
- `web/backend/app/modules/changes/service.py`
- `web/backend/tests/test_reachability_diff.py`

## 实施步骤

- [ ] 验证真实 SDK 双侧 Trace 结构与差异语义，加入 schema/适配。
- [ ] 构造 HeaderConstraints/PathConstraints，受限范围下运行并保留有效条件。
- [ ] 输出 flow 示例、两侧结果、覆盖限制和截断信息。
- [ ] 运行下述验证，记录实际命令与结果，更新本文及索引状态。

## 测试与验收

- test_newly_reachable_and_unreachable：两个方向与已知配置变化一致。
- test_different_paths_same_reachability：路径变化不自动算可达性变化。
- test_bounded_no_difference：无差异仅针对当前条件解释。
- test_truncated_witnesses：示例不是完整影响数量。

后端测试在 `web/backend` 下使用 `uv run pytest` 指定上述测试文件；集成测试连接版本固定的隔离 Batfish 测试网络，不操作团队生产网络。

验收成功同时要求：契约与文档一致、失败行为可解释、无跨层/跨模块越界、没有把 mock 验证宣称为真实 SDK 验证。共享约束中的身份、版本、模型覆盖和结果截断规则均适用。

## 非目标与实施边界

- 不做无范围安全证明、双向业务会话证明或全网穷举。

## 完成记录

当前尚未开发或运行本 spec 的产品测试。实施者完成后在本节记录实际文件、验证命令、结果、引擎/SDK版本（如涉及）和剩余限制；存在验收失败时保持未通过状态。
