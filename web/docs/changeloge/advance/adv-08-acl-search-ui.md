# ADV-08 ACL 高级诊断与证据分层

- 状态：已完成
- 阶段：2
- 依赖：[ADV-07](../advance/adv-07-acl-search-api.md)
- 预计工作量：1.5 人天（实现/验证 1.0 + 测试 0.25 + 文档/自检 0.25），依赖就绪后计；超过 2 人天先拆分。
- 共享约束：[架构](../../architecture.md)、[API 契约](../../api-contracts.md)、[前端规范](../../frontend.md)、[运行设计](../../operations.md)、[验收](../../validation.md)。

## 需求与目标

专家可以执行 ACL 条件搜索并审阅无效规则证据。

- ACL 页面增加搜索与规则诊断两个标签，复用表格/详情/流量组件。

## 设计与接口

- 参数从能力 schema 驱动；search-filters 与 filter-line-reachability 使用独立表单状态。
- 证据不足时显示未知，不展示想象的遮蔽链。

沿用 api → service → controller；所有跨业务模块调用经过 service。非 SDK 存储由本模块 repository 负责。浏览器不接触 SDK 会话或连接参数。

## 预期改动位置

以下是实现时的目标路径，本次文档编写不创建代码文件：

- `web/frontend/src/features/acl/FilterSearch.tsx`
- `web/frontend/src/features/acl/RuleReachability.tsx`
- `web/frontend/src/features/acl/acl-advanced.test.tsx`

## 实施步骤

- [x] 添加两个入口及用途解释，避免普通用户误选。
- [x] 展示反例 flow、阻挡规则和查询范围，可一键带参数进入流量测试。
- [x] 在第一层保留覆盖不足、无匹配和截断提示。
- [x] 运行下述验证，记录实际命令与结果，更新本文及索引状态。

## 测试与验收

- acl-advanced.test.tsx：不同模式参数不会混发。
- 搜索示例跳转测试保持原始协议/IP/端口。
- 没有证据链时仍能打开原始结果。

前端组件测试在 `web/frontend` 下使用 `pnpm exec vitest run` 指定上述 `.test.tsx` 文件；页面交互同时按前端规范人工检查。

验收成功同时要求：契约与文档一致、失败行为可解释、无跨层/跨模块越界、没有把 mock 验证宣称为真实 SDK 验证。共享约束中的身份、版本、模型覆盖和结果截断规则均适用。

## 非目标与实施边界

- 不做策略编辑器、全量规则语言解析或配置重写。

## 完成记录

2026-09-26 已完成：`FilterTest.tsx` 在既有流量测试旁增加条件搜索、规则诊断标签，独立保存三个草稿；提交进行中或状态未知时保持原标签和幂等请求标识。`FilterSearch.tsx`、`RuleReachability.tsx` 使用能力目录开关/默认值、OpenAPI 生成类型和有界字面范围校验；`AdvancedResults.tsx` 分层显示查询范围、示例 Flow、阻挡规则/不可匹配原因与原始 SDK 行。示例 Flow 回测保持原协议、IP 和端口，并重新绑定原结果的网络/快照。无样本、部分结果与缺少阻挡证据均不推断安全或捏造遮蔽链。

新增组件/请求单测 `acl-advanced.test.tsx`、`advanced-results.test.tsx` 及真实浏览器 `tests/acl-advanced.spec.ts`。本篇和此前 MVP-01～25、ADV-01～08 累计验证：后端325项、真实冒烟12项、前端78项、真实浏览器21项，均0必需跳过；全新 HTTPS 部署、worker 失联对账及备份新卷还原通过，恢复后的生产构建明暗主题各3项、双用户闭环各1项通过。运行 `lab.py verify/smoke`、`pnpm test/build/check:api/format:check`、`pnpm exec playwright test`、`verify_deployment.py` 和两套生产浏览器配置。固定 Batfish revision `7d0deeeac4a09973b3876327f6aef721ee12f955`、JAR SHA-256 `0927de7c740bc72f999870e842605baad9a7cb6ea66e4b01fb9a6037bea00193`、Pybatfish `2026.9.17.3748`、Python `3.12.12`，迁移0008。完整证据见[ADV-08验收](../../evidence/adv-08-verification.md)。仍只验证合成配置下的模型功能，不声称与现场转发一致或已覆盖完整 SDK。
