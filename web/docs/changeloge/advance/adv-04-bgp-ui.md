# ADV-04 BGP 状态列表与异常详情

- 状态：已完成
- 阶段：2
- 依赖：[ADV-03](../advance/adv-03-bgp-api.md)
- 预计工作量：1.0 人天（实现/验证 0.5 + 测试 0.25 + 文档/自检 0.25），依赖就绪后计；超过 2 人天先拆分。
- 共享约束：[架构](../../architecture.md)、[API 契约](../../api-contracts.md)、[前端规范](../../frontend.md)、[运行设计](../../operations.md)、[验收](../../validation.md)。

## 需求与目标

让用户从 BGP 异常列表进入会话双方的配置与分析上下文。

- 会话表、状态筛选、兼容性模式、双方设备/接口详情与路由入口。

## 设计与接口

- 使用 bgp-sessions 专用 API，状态分类保持原始值可查。
- 默认必要列；AS/地址族/原始属性在详情层。

沿用 api → service → controller；所有跨业务模块调用经过 service。非 SDK 存储由本模块 repository 负责。浏览器不接触 SDK 会话或连接参数。

## 预期改动位置

以下是实现时的目标路径，本次文档编写不创建代码文件：

- `web/frontend/src/features/bgp/`
- `web/frontend/src/features/bgp/bgp.test.tsx`

## 实施步骤

- [x] 建立列表、基础/高级筛选和模型状态提示。
- [x] 详情支持双端跳转；没有远端设备时保留未知状态。
- [x] 按告警给出已有页面导航，不编造修复指令。
- [x] 运行下述验证，记录实际命令与结果，更新本文及索引状态。

## 测试与验收

- bgp.test.tsx：单端/未知远端/不兼容会话均可读。
- 切换兼容性模式不会拿状态问题结果当同一种表。
- 页面常驻“模型计算，非实时设备状态”。

前端组件测试在 `web/frontend` 下使用 `pnpm exec vitest run` 指定上述 `.test.tsx` 文件；页面交互同时按前端规范人工检查。

验收成功同时要求：契约与文档一致、失败行为可解释、无跨层/跨模块越界、没有把 mock 验证宣称为真实 SDK 验证。共享约束中的身份、版本、模型覆盖和结果截断规则均适用。

## 非目标与实施边界

- 不显示假实时刷新图表，不加入告警推送。

## 完成记录

2026-09-26：新增 `web/frontend/src/features/bgp/` 的独立 BGP 入口与结果视图，并在工作台侧栏和通用结果页接入。默认不要求填写筛选条件；高级参数保留本地/远端设备选择器。模型状态与配置兼容性分别提交新的分析任务、保存独立结果。列表对 SDK 原始状态做精确筛选和分页；设备名打开逐层详情，未知远端不提供虚假跳转。详情保留双方接口、地址、VRF、AS、地址族、原始属性，并从固定快照恢复上下文后进入路由分析；解析与模型限制链接到已有快照诊断页。常驻提示为配置模型而非实时状态。

在 `web/frontend` 执行目标 `pnpm exec vitest run src/features/bgp/bgp.test.tsx`、全量 `pnpm test`、`pnpm build`、`pnpm check:api`、`pnpm format:check` 和全量 Playwright；在仓库根目录执行 `web/backend/.venv/bin/python web/scripts/lab.py verify`、`smoke`、Ruff、离线锁文件检查与隔离 HTTPS 部署恢复。结果：前端58项、真实浏览器18项、后端314项、冒烟12项、部署恢复及恢复后的浅/深主题各3项与双用户各1项均通过。浏览器样本包括 Cisco 同 AS 与 AS 错配会话、Huawei/H3C 无建模会话；未用 mock 替代真实引擎验收。深浅主题截图已检查，修正了原始 IP 显示与详情入口在窄结果栏溢出问题。源码身份、实际命令与部署证据见[ADV-04验收](../../evidence/adv-04-verification.md)。

固定引擎 revision `7d0deeeac4a09973b3876327f6aef721ee12f955`，JAR SHA-256 `0927de7c740bc72f999870e842605baad9a7cb6ea66e4b01fb9a6037bea00193`，Pybatfish `2026.9.17.3748`，Python `3.12.12`，迁移0008。仍只验证配置模型的 Web 功能，不宣称现场 BGP 健康或百台设备容量。
