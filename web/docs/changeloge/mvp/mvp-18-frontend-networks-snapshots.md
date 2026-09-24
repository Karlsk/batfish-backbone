# MVP-18 网络、快照与上传向导界面

- 状态：待开发
- 阶段：1
- 依赖：[MVP-10](../mvp/mvp-10-snapshot-initialization.md)、[MVP-17](../mvp/mvp-17-frontend-auth-users.md)
- 预计工作量：2.0 人天（实现/验证 1.25 + 测试 0.5 + 文档/自检 0.25），依赖就绪后计；超过 2 人天先拆分。
- 共享约束：[架构](../../architecture.md)、[API 契约](../../api-contracts.md)、[前端规范](../../frontend.md)、[运行设计](../../operations.md)、[验收](../../validation.md)。

## 需求与目标

用户能从空系统开始上传并跟踪第一份快照。

- 网络列表/创建、快照列表/选择、文件与 ZIP 上传、初始化提交及任务链接。

## 设计与接口

- 接入 /networks、/uploads、/snapshots；上传成功不显示为初始化成功。
- 列表显示发起人、创建时间、状态；同名显示标签仍按 UUID 区分。

沿用 api → service → controller；所有跨业务模块调用经过 service。非 SDK 存储由本模块 repository 负责。浏览器不接触 SDK 会话或连接参数。

## 预期改动位置

以下是实现时的目标路径，本次文档编写不创建代码文件：

- `web/frontend/src/features/networks/`
- `web/frontend/src/features/snapshots/`
- `web/frontend/src/features/snapshots/upload.test.tsx`

## 实施步骤

- [ ] 实现空态引导和全局上下文切换。
- [ ] 按上传→校验完成→填写快照名称→提交初始化区分步骤。
- [ ] 使用 Idempotency-Key 防止重复提交，展示文件错误和服务端限额。
- [ ] 运行下述验证，记录实际命令与结果，更新本文及索引状态。

## 测试与验收

- upload.test.tsx：上传失败不提交初始化，重试保留用户选择的网络。
- 重复点击初始化只得到同一任务。
- 切换网络后不继续显示旧网络快照选项。

前端组件测试在 `web/frontend` 下使用 `pnpm exec vitest run` 指定上述 `.test.tsx` 文件；页面交互同时按前端规范人工检查。

验收成功同时要求：契约与文档一致、失败行为可解释、无跨层/跨模块越界、没有把 mock 验证宣称为真实 SDK 验证。共享约束中的身份、版本、模型覆盖和结果截断规则均适用。

## 非目标与实施边界

- 不做配置编辑、物理设备采集或高级拖拽目录浏览器兼容。

## 完成记录

当前尚未开发或运行本 spec 的产品测试。实施者完成后在本节记录实际文件、验证命令、结果、引擎/SDK版本（如涉及）和剩余限制；存在验收失败时保持未通过状态。
