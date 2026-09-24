# ADV-10 第二阶段整体验收

- 状态：待开发
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

以下是实现时的目标路径，本次文档编写不创建代码文件：

- `web/backend/tests/integration/test_advance_phase2.py`
- `web/frontend/e2e/advance-phase2.spec.ts`
- `web/docs/advance-phase2-acceptance.md`

## 实施步骤

- [ ] 运行新增接口/页面检查与首版关键回归。
- [ ] 在真实引擎执行已知 BGP 不匹配、ACL deny/遮蔽、孤立拓扑样例。
- [ ] 核对专家/专用调用一致并记录覆盖与限制。
- [ ] 运行下述验证，记录实际命令与结果，更新本文及索引状态。

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

当前尚未开发或运行本 spec 的产品测试。实施者完成后在本节记录实际文件、验证命令、结果、引擎/SDK版本（如涉及）和剩余限制；存在验收失败时保持未通过状态。
