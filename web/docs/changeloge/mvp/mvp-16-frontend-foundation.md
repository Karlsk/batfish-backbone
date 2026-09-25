# MVP-16 前端骨架与渐进展示组件

- 状态：已完成
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

- [x] 建立最小前端构建和主题 token，创建侧栏/顶栏布局。
- [x] 接入会话、错误和 CSRF 请求封装以及 OpenAPI 类型生成。
- [x] 实现公共逐级展示组件和未生效功能开关。
- [x] 运行下述验证，记录实际命令与结果，更新本文及索引状态。

## 测试与验收

- context.test.tsx：旧快照请求晚返回不能覆盖新快照。
- advanced-options.test.tsx：折叠后已填写参数保留且显示生效数量。
- 人工检查 1280/1920 宽度、键盘焦点和中文长名称。

前端组件测试在 `web/frontend` 下使用 `pnpm exec vitest run` 指定上述 `.test.tsx` 文件；页面交互同时按前端规范人工检查。

验收成功同时要求：契约与文档一致、失败行为可解释、无跨层/跨模块越界、没有把 mock 验证宣称为真实 SDK 验证。共享约束中的身份、版本、模型覆盖和结果截断规则均适用。

## 非目标与实施边界

- 不实现具体分析页面、复杂动画或完整移动端布局。

## 完成记录

2026-09-25 完成 `web/frontend`：React/Ant Design 中文浅色工作台、固定侧栏及常驻网络/快照上下文、显式路由和禁用的未开放入口；TanStack Query 查询键包含身份/资源/结果/参数，切换身份清缓存及上下文，切换网络清快照。Cookie同源请求，CSRF仅内存，过期旧身份响应不清新会话；统一安全错误，不展示任意服务堆栈。

完整OpenAPI从后端装配离线生成，未访问数据库或读取运行凭证；类型与契约一致性检查纳入脚本。锁定TypeScript5.9.3满足生成器peer约束。AdvancedOptions折叠保留参数和生效数、ResultSummary显示覆盖/截断/忽略ACL、DetailsDrawer打开时才加载、错误/加载/空态组件具备测试。

`web/frontend` 执行 `pnpm test`：**7 passed、0 skipped**；`check:api`、`typecheck`、`build`、`format:check`均通过。`pnpm test:e2e`：**2 passed、0 skipped**，真实Chromium153访问实际API健康检查；1280/1920页面、键盘焦点、中文长名称、参数保留和详情展开均验证。长页面实际滚动后顶栏仍位于y=0。已人工查看两种宽度截图，无横向溢出；组件harness使用明确标识的合成上下文，非业务分析闭环。

仓库根 `lab.py smoke/verify`：真实两套配置HTTP/worker五类分析冒烟 **12 passed**，MVP-01～16后端累计 **259 passed、0 skipped**；Ruff、uv锁、文档链接和Git检查通过。固定引擎/SDK不变。见 [验收证据](../../evidence/mvp-16-verification.json)。独立审查指出顶部常驻缺失，修复并复核通过。

构建初始JS829.30kB（gzip265.69kB）存在体积提示，后续业务页面按路由拆分；未做容量背书。本篇不含实际认证/业务页面，满足MVP-17前置，继续登录与用户管理。
