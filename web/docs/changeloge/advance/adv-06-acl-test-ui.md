# ADV-06 ACL 流量测试页面

- 状态：已完成
- 阶段：2
- 依赖：[ADV-05](../advance/adv-05-acl-test-api.md)
- 预计工作量：1.5 人天（实现/验证 1.0 + 测试 0.25 + 文档/自检 0.25），依赖就绪后计；超过 2 人天先拆分。
- 共享约束：[架构](../../architecture.md)、[API 契约](../../api-contracts.md)、[前端规范](../../frontend.md)、[运行设计](../../operations.md)、[验收](../../validation.md)。

## 需求与目标

用户通过基础流量表单查看规则动作和命中依据。

- 设备/ACL选择、流量表单、测试结果、命中规则与原始证据。

## 设计与接口

- 使用 test-filters 接口；基础/高级共用已登记参数。
- 第一层区分放行、拒绝、未匹配过滤器、能力不支持。

沿用 api → service → controller；所有跨业务模块调用经过 service。非 SDK 存储由本模块 repository 负责。浏览器不接触 SDK 会话或连接参数。

## 预期改动位置

以下是实现时的目标路径，本次文档编写不创建代码文件：

- `web/frontend/src/features/acl/FilterTest.tsx`
- `web/frontend/src/features/acl/filter-test.test.tsx`

## 实施步骤

- [x] 实现最小输入和规则选择，选项绑定快照。
- [x] 显示动作与命中摘要，详情展开规则、实际 flow 和来源。
- [x] 提供跳转连通性分析入口，传递流量参数但要求选择起点。
- [x] 运行下述验证，记录实际命令与结果，更新本文及索引状态。

## 测试与验收

- filter-test.test.tsx：隐式拒绝没有伪规则号。
- 能力不足/未匹配不显示为通过。
- 高级端口与协议在展开/折叠间保持一致。

前端组件测试在 `web/frontend` 下使用 `pnpm exec vitest run` 指定上述 `.test.tsx` 文件；页面交互同时按前端规范人工检查。

验收成功同时要求：契约与文档一致、失败行为可解释、无跨层/跨模块越界、没有把 mock 验证宣称为真实 SDK 验证。共享约束中的身份、版本、模型覆盖和结果截断规则均适用。

## 非目标与实施边界

- 不做规则编辑、配置下发或自动推荐放行规则。

## 完成记录

2026-09-26：新增 `web/frontend/src/features/acl/` 的流量表单、已解析 ACL 候选、局部动作与分级证据；在 `App.tsx` 增加独立入口，`Results.tsx` 接入专用结果视图。基础输入为当前快照的设备、ACL、源/目的 IPv4；专家表达式、协议、端口在折叠高级区且保留值。结果首层区分放行、显式/隐式拒绝、无匹配、模型不支持和分页/截断不确定；详情只显示实际 SDK Flow、Trace 与来源引用，没有虚构规则号。路径分析入口恢复结果固定快照并预填流量，`TraceForm.tsx` 仍要求用户选择起点。补充单元和真实浏览器测试；修复既有分析浏览器脚本点击导航后未等待目标页面的竞态，不改变原有业务行为。

在 `web/frontend` 执行 `pnpm exec vitest run src/features/acl/filter-test.test.tsx src/features/acl/filter-result.test.tsx src/features/traceroute/traceroute.test.tsx`、全量 `pnpm test`、`pnpm build`、`pnpm check:api`、`pnpm format:check` 和全量 Playwright；在仓库根目录执行 `web/backend/.venv/bin/python web/scripts/lab.py verify`、`smoke`、Ruff lint、离线锁文件检查及隔离 HTTPS 部署恢复。结果：前端70项、真实浏览器20项、后端318项、冒烟12项、恢复后的浅/深主题各3项部署及各1项双用户验收，均通过且0必需skip。Cisco 合成配置实测候选、放行、隐式拒绝、原始来源及路径预填；Huawei/H3C 配置实测拒绝绿色结论，截图人工检查两套主题。原始证据和源码指纹见[ADV-06验收](../../evidence/adv-06-verification.md)。固定引擎 revision `7d0deeeac4a09973b3876327f6aef721ee12f955`，JAR SHA-256 `0927de7c740bc72f999870e842605baad9a7cb6ea66e4b01fb9a6037bea00193`，Pybatfish `2026.9.17.3748`，Python `3.12.12`，迁移0008。ADV-07 依赖已满足。只验证配置模型 Web 功能，不证明现场策略或端到端可达。
