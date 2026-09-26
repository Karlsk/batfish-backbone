# ADV-14 差异可达性分析接口

- 状态：已完成
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

- [x] 验证真实 SDK 双侧 Trace 结构与差异语义，加入 schema/适配。
- [x] 构造 HeaderConstraints/PathConstraints，受限范围下运行并保留有效条件。
- [x] 输出 flow 示例、两侧结果、覆盖限制和截断信息。
- [x] 运行下述验证，记录实际命令与结果，更新本文及索引状态。

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

2026-09-27 完成。`changes/schemas.py` 定义必填目的 IPv4 范围和起点、受控专家选项；`changes/reachability_analysis.py` 将分析绑定不可变比较上下文并按两侧摘要缓存；`analysis/controllers/reachability.py` 经公开 SDK 调用差异可达性并保留候选/基线两侧 Flow 与 Trace。结果追加方向、三态可达性和证据截断；只在证据完整时断言不可达。OpenAPI 生成类型与 API 契约已同步。测试覆盖候选新增/消失、路径变化但可达性不变、限定范围空结果、路径证据截断、无效起点、参数白名单、缓存/导出/删除后历史及真实 HTTP/独立 worker。

仓库根运行 `web/backend/.venv/bin/python web/scripts/lab.py smoke`（13 passed）和 `verify`（357 passed）、Ruff/格式、离线锁文件、Git 空白检查；`web/frontend` 运行 `pnpm generate:api/check:api/typecheck/test/build/format:check`（81 项单测）、全量 Playwright（23 passed）。本机独立 HTTPS `web/scripts/verify_deployment.py` 完成启动、失联对账、离线备份与新卷恢复；恢复后明暗主题分别 3 项部署检查和 1 项双用户验收通过。固定 Batfish revision `7d0deeeac4a09973b3876327f6aef721ee12f955`，JAR SHA-256 `0927de7c740bc72f999870e842605baad9a7cb6ea66e4b01fb9a6037bea00193`，Pybatfish `2026.9.17.3748`、Python `3.12.12`、迁移 0009。完整证据见[ADV-14 验收](../../evidence/adv-14-verification.md)。ADV-15 依赖已满足。

限制：SDK witness 是当前条件下的示例，不是所有受影响业务流；证据截断时方向可能不确定。模型结果不证明现场转发或回程。初次浏览器全回归的两项超时在隔离复跑后均通过，整套随后 23/23 通过；首次 HTTPS 演练遇本机 Docker 服务瞬时失联，重试完整通过，均在验收报告保留原始失败记录。
