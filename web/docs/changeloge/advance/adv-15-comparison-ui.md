# ADV-15 变更对比工作台

- 状态：已完成
- 阶段：3
- 依赖：[ADV-14](../advance/adv-14-differential-reachability.md)
- 预计工作量：2.0 人天（实现/验证 1.25 + 测试 0.5 + 文档/自检 0.25），依赖就绪后计；超过 2 人天先拆分。
- 共享约束：[架构](../../architecture.md)、[API 契约](../../api-contracts.md)、[前端规范](../../frontend.md)、[运行设计](../../operations.md)、[验收](../../validation.md)。

## 需求与目标

用户可选择两份快照并逐级审阅配置、路由和可达性变化。

- 基线/候选选择、比较列表、三类分析标签、两侧证据与原始详情。

## 设计与接口

- 使用 comparisons 及三个分析接口；始终基线左/候选右，所有结果显示方向。
- 必须填写差异可达性范围；空表不能展示“全网无影响”。

沿用 api → service → controller；所有跨业务模块调用经过 service。非 SDK 存储由本模块 repository 负责。浏览器不接触 SDK 会话或连接参数。

## 预期改动位置

以下是实现时的目标路径，本次文档编写不创建代码文件：

- `web/frontend/src/features/changes/`
- `web/frontend/src/features/changes/changes.test.tsx`

## 实施步骤

- [x] 实现比较上下文创建/选择并固定两侧标签。
- [x] 复用表格/TraceSteps 展示路由与 flow，配置 diff 采用按文件按需加载。
- [x] 把覆盖不足/版本差异/截断放在摘要区域。
- [x] 运行下述验证，记录实际命令与结果，更新本文及索引状态。

## 测试与验收

- changes.test.tsx：交换快照后创建新上下文，不重用旧结果。
- 新增/删除颜色与方向一致，并提供文字标签。
- 无差异、计算失败、模型不兼容分别显示。

前端组件测试在 `web/frontend` 下使用 `pnpm exec vitest run` 指定上述 `.test.tsx` 文件；页面交互同时按前端规范人工检查。

验收成功同时要求：契约与文档一致、失败行为可解释、无跨层/跨模块越界、没有把 mock 验证宣称为真实 SDK 验证。共享约束中的身份、版本、模型覆盖和结果截断规则均适用。

## 非目标与实施边界

- 不做审批流、自动变更评审或配置部署按钮。

## 完成记录

2026-09-27 完成。新增 `web/frontend/src/features/changes/`、导航/样式、历史结果展示、`changes.test.tsx` 和 `tests/changes.spec.ts`。真实浏览器回归发现快照状态跨事务读偏斜，补充 `web/backend/tests/test_snapshots.py` 回归并修复 `app/modules/snapshots/service.py`，重新启动隔离服务后复验。

实际验证与环境见 [ADV-15 完整验收](../../evidence/adv-15-verification.md)：`web/backend` 对应隔离运行 `lab.py verify` 358 passed、`lab.py smoke` 13 passed；`web/frontend` 运行 `pnpm test` 87 passed、`pnpm check:api`、`pnpm typecheck`、`pnpm build`、`pnpm format:check`，浏览器 24 passed；新 HTTPS 部署、恢复和恢复后深浅主题/双用户验收通过。Batfish revision `7d0deeeac4a09973b3876327f6aef721ee12f955`、Pybatfish `2026.9.17.3748`、Python `3.12.12`；源码身份见机器证据。没有必需检查未运行或失败。范围限制为模型及已选流量条件，不声明真实网络转发一致性；满足 ADV-16 前置门槛。
