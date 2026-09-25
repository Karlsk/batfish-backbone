# MVP-19 任务记录与解析诊断界面

- 状态：已完成
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

- [x] 实现状态文字与真实阶段，不显示伪百分比。
- [x] 刷新恢复任务详情，终态停止轮询；处理 interrupted/unknown。
- [x] 诊断点击进入配置行查看，没有位置时只展示原始说明。
- [x] 运行下述验证，记录实际命令与结果，更新本文及索引状态。

## 测试与验收

- jobs.test.tsx：页面卸载不调用 cancel，终态停止轮询。
- running 不提供伪取消，取消竞态 409 可理解。
- 诊断缺行号/文件不存在/部分解析不会错误高亮。

前端组件测试在 `web/frontend` 下使用 `pnpm exec vitest run` 指定上述 `.test.tsx` 文件；页面交互同时按前端规范人工检查。

验收成功同时要求：契约与文档一致、失败行为可解释、无跨层/跨模块越界、没有把 mock 验证宣称为真实 SDK 验证。共享约束中的身份、版本、模型覆盖和结果截断规则均适用。

## 非目标与实施边界

- 不做实时日志流、运行中强杀或自动修复配置。

## 完成记录

2026-09-25 完成任务中心状态/本人/当前网络筛选、分页与任务详情；显示真实状态、阶段、起止时间计算的执行耗时和不可变来源。活动任务2秒轮询后退避5秒，终态停止；切回窗口刷新，页面卸载不取消后台任务。仅queued、cancel_allowed且本人/管理员才显示取消；409刷新并解释领取竞态。重试以稳定幂等键创建新任务，unknown提供管理员核对说明，服务端最终决定是否可调度。

初始化重试展示旧任务/旧快照与新任务/新快照，原快照不伪装恢复；分析重试明确沿用原快照。任务参数和原始上下文放在详情抽屉。诊断页首层展示解析质量、模型覆盖及版本；诊断按级别分页，已知文件/行通过file_id按需查看，缺行不猜测高亮，缺文件只解释，错误与空结果分开；原始说明按需展开。

实际文件：frontend/src/features/jobs、snapshots/diagnostics及路由/快照入口，tests/jobs.spec.ts及双拓扑浏览器回归。浏览器用受控worker暂停界限验证queued取消、不可变重试、新旧UUID及恢复后真实完成；两套配置均从真实快照任务刷新进入诊断及文件行查看。所有旧账号/上传/上下文/桌面宽度流程保留。

仓库根 `lab.py smoke/verify`：冒烟 **12 passed**，累计后端 **260 passed、0 skipped**；前端 `pnpm test`：**23 passed、0 skipped**，契约、构建内类型检查、格式、Ruff及锁文件通过；`pnpm test:e2e`：**6 passed、0 skipped**。已查看诊断摘要、配置文件抽屉和重试来源截图。见 [验收证据](../../evidence/mvp-19-verification.json)。

独立审查修正分析重试误称新快照和缺耗时，并复核通过；浏览器测试修正中文按钮选择器、等待旧UUID加载后再比对及抽屉动画截图。不存在物理设备或现场仿真精度验证；共享UI包846kB仍有体积提示，未作容量背书。满足MVP-20依赖。
