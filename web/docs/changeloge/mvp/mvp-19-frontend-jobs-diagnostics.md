# MVP-19 任务记录与解析诊断界面

- 状态：待开发
- 阶段：1
- 依赖：[MVP-11](../mvp/mvp-11-initialization-diagnostics.md)、[MVP-18](../mvp/mvp-18-frontend-networks-snapshots.md)
- 预计工作量：1.5 人天（实现/验证 1.0 + 测试 0.25 + 文档/自检 0.25），依赖就绪后计；超过 2 人天先拆分。
- 共享约束：[架构](../../architecture.md)、[API 契约](../../api-contracts.md)、[前端规范](../../frontend.md)、[运行设计](../../operations.md)、[验收](../../validation.md)。

## 需求与目标

用户能区分任务进度、失败、模型限制与配置问题。

- 任务列表/详情、轮询、queued 取消、重试、解析诊断和原始文件行查看。

## 设计与接口

- 接入 /jobs、S/diagnostics、S/files；未运行与已运行的取消能力不同。
- 一层保留模型覆盖摘要；详情展示文件行位置、有效参数和恢复说明。
- 取消按钮依据 cancel_allowed；初始化重试返回新 snapshot_id 时显示新旧来源并跳转新任务，不把旧失败快照伪装成已恢复。

沿用 api → service → controller；所有跨业务模块调用经过 service。非 SDK 存储由本模块 repository 负责。浏览器不接触 SDK 会话或连接参数。

## 预期改动位置

以下是实现时的目标路径，本次文档编写不创建代码文件：

- `web/frontend/src/features/jobs/`
- `web/frontend/src/features/snapshots/diagnostics/`
- `web/frontend/src/features/jobs/jobs.test.tsx`

## 实施步骤

- [ ] 实现状态文字与真实阶段，不显示伪百分比。
- [ ] 刷新恢复任务详情，终态停止轮询；处理 interrupted/unknown。
- [ ] 诊断点击进入配置行查看，没有位置时只展示原始说明。
- [ ] 运行下述验证，记录实际命令与结果，更新本文及索引状态。

## 测试与验收

- jobs.test.tsx：页面卸载不调用 cancel，终态停止轮询。
- running 不提供伪取消，取消竞态 409 可理解。
- 诊断缺行号/文件不存在/部分解析不会错误高亮。

前端组件测试在 `web/frontend` 下使用 `pnpm exec vitest run` 指定上述 `.test.tsx` 文件；页面交互同时按前端规范人工检查。

验收成功同时要求：契约与文档一致、失败行为可解释、无跨层/跨模块越界、没有把 mock 验证宣称为真实 SDK 验证。共享约束中的身份、版本、模型覆盖和结果截断规则均适用。

## 非目标与实施边界

- 不做实时日志流、运行中强杀或自动修复配置。

## 完成记录

当前尚未开发或运行本 spec 的产品测试。实施者完成后在本节记录实际文件、验证命令、结果、引擎/SDK版本（如涉及）和剩余限制；存在验收失败时保持未通过状态。
