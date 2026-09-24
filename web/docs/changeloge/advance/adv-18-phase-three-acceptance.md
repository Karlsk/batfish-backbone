# ADV-18 第三阶段整体验收

- 状态：待开发
- 阶段：3
- 依赖：[ADV-17](../advance/adv-17-fault-simulation-ui.md)
- 预计工作量：1.5 人天（实现/验证 1.0 + 测试 0.25 + 文档/自检 0.25），依赖就绪后计；超过 2 人天先拆分。
- 共享约束：[架构](../../architecture.md)、[API 契约](../../api-contracts.md)、[前端规范](../../frontend.md)、[运行设计](../../operations.md)、[验收](../../validation.md)。

## 需求与目标

验证变更与故障模拟完整闭环且不破坏前两阶段能力。

- 已知配置变化、路由增删、可达性方向、派生快照不变性、多用户回归。

## 设计与接口

- 以 validation.md 阶段3为门槛，产出 web/docs/advance-phase3-acceptance.md。
- 所有结论绑定基线/候选、有效范围和引擎版本；缺少真实引擎对照不能通过。

沿用 api → service → controller；所有跨业务模块调用经过 service。非 SDK 存储由本模块 repository 负责。浏览器不接触 SDK 会话或连接参数。

## 预期改动位置

以下是实现时的目标路径，本次文档编写不创建代码文件：

- `web/backend/tests/integration/test_advance_phase3.py`
- `web/frontend/e2e/advance-phase3.spec.ts`
- `web/docs/advance-phase3-acceptance.md`

## 实施步骤

- [ ] 构建两个可解释的小快照，执行配置/路由/可达性差异并对照直接 SDK。
- [ ] 执行节点与接口停用方案，核实基线未变及失败路径。
- [ ] 回归首版身份/任务与二阶段关键查询，更新所有阶段验收状态。
- [ ] 运行下述验证，记录实际命令与结果，更新本文及索引状态。

## 测试与验收

- 新增/消失可达性的方向、配置行号和路由变化一致。
- 模型不足、截断和无差异解释符合规范。
- 多用户并发操作、失败重试、删除引用保护不回退。

后端测试在 `web/backend` 下使用 `uv run pytest` 指定上述测试文件；集成测试连接版本固定的隔离 Batfish 测试网络，不操作团队生产网络。

浏览器验收在 `web/frontend` 下使用 `pnpm exec playwright test e2e/advance-phase3.spec.ts`；测试账号和快照应使用隔离环境。

验收成功同时要求：契约与文档一致、失败行为可解释、无跨层/跨模块越界、没有把 mock 验证宣称为真实 SDK 验证。共享约束中的身份、版本、模型覆盖和结果截断规则均适用。

## 非目标与实施边界

- 未适配 SDK 能力仍列为范围外，不因第三阶段完成而宣称覆盖整个SDK。

## 完成记录

当前尚未开发或运行本 spec 的产品测试。实施者完成后在本节记录实际文件、验证命令、结果、引擎/SDK版本（如涉及）和剩余限制；存在验收失败时保持未通过状态。
