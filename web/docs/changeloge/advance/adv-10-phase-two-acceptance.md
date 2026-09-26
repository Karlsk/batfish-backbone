# ADV-10 第二阶段整体验收

- 状态：已完成
- 阶段：2
- 依赖：[ADV-09](../advance/adv-09-expert-catalog.md)
- 预计工作量：1.0 人天（实现/验证 0.5 + 测试 0.25 + 文档/自检 0.25），依赖就绪后计；超过 2 人天先拆分。
- 共享约束：[架构](../../architecture.md)、[API 契约](../../api-contracts.md)、[前端规范](../../frontend.md)、[运行设计](../../operations.md)、[验收](../../validation.md)。

## 需求与目标

验证增强排障功能与首版闭环共同可用。

- 拓扑/BGP/ACL/专家入口对照与前端联动回归。

## 设计与接口

- 以 validation.md 阶段2为门槛，产出 web/docs/advance-phase2-acceptance.md。
- 问题限定范围、模型边界及 source 证据完整，才可以宣布阶段通过。

沿用 api → service → controller；所有跨业务模块调用经过 service。非 SDK 存储由本模块 repository 负责。浏览器不接触 SDK 会话或连接参数。

## 预期改动位置

验收交付路径：

- `web/backend/tests/integration/test_advance_phase2.py`
- `web/frontend/e2e/advance-phase2.spec.ts`
- `web/docs/advance-phase2-acceptance.md`

## 实施步骤

- [x] 运行新增接口/页面检查与首版关键回归。
- [x] 在真实引擎执行已知 BGP 不匹配、ACL deny/遮蔽、孤立拓扑样例。
- [x] 核对专家/专用调用一致并记录覆盖与限制。
- [x] 运行下述验证，记录实际命令与结果，更新本文及索引状态。

## 测试与验收

- 拓扑关系与 SDK 原始边一致，图中不显示伪实时链路。
- ACL例子可复核，未知/不支持未被当作通过。
- 首版两用户不同快照行为不回退。

后端测试在 `web/backend` 下使用 `uv run pytest` 指定上述测试文件；集成测试连接版本固定的隔离 Batfish 测试网络，不操作团队生产网络。

浏览器验收在 `web/frontend` 下使用 `pnpm exec playwright test e2e/advance-phase2.spec.ts`；测试账号和快照应使用隔离环境。

验收成功同时要求：契约与文档一致、失败行为可解释、无跨层/跨模块越界、没有把 mock 验证宣称为真实 SDK 验证。共享约束中的身份、版本、模型覆盖和结果截断规则均适用。

## 非目标与实施边界

- 验收发现超范围缺陷先追加小修复 spec，不直接开始第三阶段。

## 完成记录

2026-09-26 已完成：新增 `backend/tests/integration/test_advance_phase2.py` 和 `frontend/tests/advance-phase2.spec.ts`，在同一 Cisco 派生快照覆盖孤立节点、BGP AS 错配、ACL 放行/显式与隐式拒绝、遮蔽与空匹配原因、专家/专用一致性。完整阶段报告见[第二阶段验收](../../advance-phase2-acceptance.md)，逐项命令、源码指纹与实际结果见[ADV-10证据](../../evidence/adv-10-verification.md)。后端 `lab.py verify` 330项、当前 API/worker `smoke` 12项、前端81项、真实浏览器23项；全新 HTTPS 部署、未知引擎占用对账、备份/新卷恢复及恢复后明暗主题各3项部署和1项双用户验收均通过，0必需跳过。固定 Batfish revision `7d0deeeac4a09973b3876327f6aef721ee12f955`、JAR SHA-256 `0927de7c740bc72f999870e842605baad9a7cb6ea66e4b01fb9a6037bea00193`、Pybatfish `2026.9.17.3748`、Python `3.12.12`，迁移0008。只验证配置模型和小规模合成样本，不证明现场转发或百台容量；ADV-11 的阶段依赖已满足。
