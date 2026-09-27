# ADV-18 第三阶段整体验收

- 状态：已完成
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

## 实际改动位置

- `web/backend/tests/integration/test_advance_phase3.py`
- `web/frontend/tests/advance-phase3.spec.ts`（实际 Playwright `testDir` 为 `tests`）
- `web/docs/advance-phase3-acceptance.md`

## 实施步骤

- [x] 构建两个可解释的小快照，执行配置/路由/可达性差异并对照直接 SDK。
- [x] 执行节点停用方案，并在累计测试中覆盖接口停用，核实基线未变及失败路径。
- [x] 回归首版身份/任务与二阶段关键查询，更新所有阶段验收状态。
- [x] 运行下述验证，记录实际命令与结果，更新本文及索引状态。

## 测试与验收

- 新增/消失可达性的方向、配置行号和路由变化一致。
- 模型不足、截断和无差异解释符合规范。
- 多用户并发操作、失败重试、删除引用保护不回退。

后端测试在 `web/backend` 下使用 `uv run pytest` 指定上述测试文件；集成测试连接版本固定的隔离 Batfish 测试网络，不操作团队生产网络。

浏览器验收在 `web/frontend` 下使用 `pnpm exec playwright test tests/advance-phase3.spec.ts`；测试账号和快照应使用隔离环境。

验收成功同时要求：契约与文档一致、失败行为可解释、无跨层/跨模块越界、没有把 mock 验证宣称为真实 SDK 验证。共享约束中的身份、版本、模型覆盖和结果截断规则均适用。

## 非目标与实施边界

- 未适配 SDK 能力仍列为范围外，不因第三阶段完成而宣称覆盖整个SDK。

## 完成记录

2026-09-27 已完成。新增 `web/backend/tests/integration/test_advance_phase3.py` 与 `web/frontend/tests/advance-phase3.spec.ts`，以同一 Cisco 双快照核对配置原始字节与行号，并将静态路由和差异可达性对照公开 SDK 答案；覆盖原始基线不变、失败派生不可比较及浏览器交接。短视口回归暴露菜单底部遮挡和切页保留旧滚动位置；修复 `web/frontend/src/app/style.css` 与 `web/frontend/src/app/App.tsx`。真实环境积累多个网络时分页按钮加载中的文字会变化；调整 `web/frontend/tests/deletion-helpers.ts` 的定位并等待可点击。

仓库根运行 `web/backend/.venv/bin/python web/scripts/lab.py verify`（369 passed，0 skip/fail）、`lab.py smoke`（13 passed）、`web/backend/.venv/bin/python web/scripts/verify_deployment.py --state web/.runtime/deploy-adv18-batch`（全新 HTTPS、失联对账、备份恢复通过），并检查 Ruff、离线锁文件和 Git 空白。`web/frontend` 运行 `pnpm test`（92 passed / 27 files）、`pnpm check:api`、`pnpm typecheck`、`pnpm build`、`pnpm format:check`、`pnpm exec playwright test --output=test-results/adv18-final`（26 passed），恢复后生产构建浅/深主题各 3 项部署浏览器与各 1 项双用户验收全部通过。Batfish revision `7d0deeeac4a09973b3876327f6aef721ee12f955`，引擎 `0.36.0`，Pybatfish `2026.9.17.3748`，Python `3.12.12`。详见[阶段三验收报告](../../advance-phase3-acceptance.md)与[机器证据](../../evidence/adv-18-verification.json)。MVP-01～25、ADV-01～18 门槛满足；仅合成配置与模型行为，不验证现场设备或 Java 仿真精度，未覆盖的 SDK 能力仍属范围外。
