# MVP-16 前端骨架与渐进展示组件

- 状态：待开发
- 阶段：1
- 依赖：[MVP-12](../mvp/mvp-12-analysis-results.md)
- 预计工作量：1.5 人天（实现/验证 1.0 + 测试 0.25 + 文档/自检 0.25），依赖就绪后计；超过 2 人天先拆分。
- 共享约束：[架构](../../architecture.md)、[API 契约](../../api-contracts.md)、[前端规范](../../frontend.md)、[运行设计](../../operations.md)、[验收](../../validation.md)。

## 需求与目标

建立统一、简洁的工作台布局和 API 类型边界。

- React/TypeScript/Vite、Ant Design、请求封装、主题、路由、网络/快照上下文。
- 公共 AdvancedOptions、ResultSummary、DetailsDrawer 和错误/空态组件。

## 设计与接口

- OpenAPI 生成类型；请求管理带 Cookie/CSRF，不保存长期 token。
- 所有查询 key 包含资源上下文；服务返回未登记的功能时不自动生成任意执行入口。

沿用 api → service → controller；所有跨业务模块调用经过 service。非 SDK 存储由本模块 repository 负责。浏览器不接触 SDK 会话或连接参数。

## 预期改动位置

以下是实现时的目标路径，本次文档编写不创建代码文件：

- `web/frontend/package.json`
- `web/frontend/src/app/`
- `web/frontend/src/api/`
- `web/frontend/src/components/`
- `web/frontend/src/app/context.test.tsx`

## 实施步骤

- [ ] 建立最小前端构建和主题 token，创建侧栏/顶栏布局。
- [ ] 接入会话、错误和 CSRF 请求封装以及 OpenAPI 类型生成。
- [ ] 实现公共逐级展示组件和未生效功能开关。
- [ ] 运行下述验证，记录实际命令与结果，更新本文及索引状态。

## 测试与验收

- context.test.tsx：旧快照请求晚返回不能覆盖新快照。
- advanced-options.test.tsx：折叠后已填写参数保留且显示生效数量。
- 人工检查 1280/1920 宽度、键盘焦点和中文长名称。

前端组件测试在 `web/frontend` 下使用 `pnpm exec vitest run` 指定上述 `.test.tsx` 文件；页面交互同时按前端规范人工检查。

验收成功同时要求：契约与文档一致、失败行为可解释、无跨层/跨模块越界、没有把 mock 验证宣称为真实 SDK 验证。共享约束中的身份、版本、模型覆盖和结果截断规则均适用。

## 非目标与实施边界

- 不实现具体分析页面、复杂动画或完整移动端布局。

## 完成记录

当前尚未开发或运行本 spec 的产品测试。实施者完成后在本节记录实际文件、验证命令、结果、引擎/SDK版本（如涉及）和剩余限制；存在验收失败时保持未通过状态。
