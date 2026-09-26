# ADV-05 ACL 流量测试接口

- 状态：已完成
- 阶段：2
- 依赖：[ADV-04](../advance/adv-04-bgp-ui.md)
- 预计工作量：1.5 人天（实现/验证 1.0 + 测试 0.25 + 文档/自检 0.25），依赖就绪后计；超过 2 人天先拆分。
- 共享约束：[架构](../../architecture.md)、[API 契约](../../api-contracts.md)、[前端规范](../../frontend.md)、[运行设计](../../operations.md)、[验收](../../validation.md)。

## 需求与目标

检查指定流量在指定 ACL 下的动作并保留命中证据。

- testFilters、节点/规则选择、HeaderConstraints、隐式拒绝表示。

## 设计与接口

- POST S/analyses/test-filters：nodes、filters、source_ip、destination_ip；options 协议/端口。
- 过滤器可用列表仅通过已验证结构查询获取；无原始规则行时不猜测源行。
- POST S/analyses/resolve-filters 使用已登记 resolveFilterSpecifier 作为选择器辅助；先验证其实际字段和作用域，不能绕过 registry。返回任务和表格结果，供ACL页面复用。
- 不支持准确 ACL 转换的厂商/范围拒绝验证或标记受限，不能给安全通过结论。

沿用 api → service → controller；所有跨业务模块调用经过 service。非 SDK 存储由本模块 repository 负责。浏览器不接触 SDK 会话或连接参数。

## 预期改动位置

以下是实现时的目标路径，本次文档编写不创建代码文件：

- `web/backend/app/modules/analysis/schemas/filters.py`
- `web/backend/app/modules/analysis/controllers/filters.py`
- `web/backend/tests/test_filters.py`

## 实施步骤

- [x] 登记最小流量条件及 options，复用 HeaderConstraints 转换。
- [x] 增加过滤器选择数据来源和 testFilters 结果适配。
- [x] 归一化命中规则、动作、隐式拒绝和可用源引用。
- [x] 运行下述验证，记录实际命令与结果，更新本文及索引状态。

## 测试与验收

- test_permit_deny_implicit_deny：三类结果与 SDK 一致。
- test_no_such_filter：未匹配过滤器不解释为允许。
- test_vendor_acl_coverage：已知模型缺失不能绿色通过。

后端测试在 `web/backend` 下使用 `uv run pytest` 指定上述测试文件；集成测试连接版本固定的隔离 Batfish 测试网络，不操作团队生产网络。

验收成功同时要求：契约与文档一致、失败行为可解释、无跨层/跨模块越界、没有把 mock 验证宣称为真实 SDK 验证。共享约束中的身份、版本、模型覆盖和结果截断规则均适用。

## 非目标与实施边界

- 不把 ACL 局部放行当端到端可达证明。

## 完成记录

2026-09-26：在 `web/backend/app/modules/analysis/` 新增 ACL 请求模型、固定 SDK 适配与两个 API/能力登记；生成 `web/frontend/src/api/schema.d.ts`。`testFilters` 必填源/目的 IPv4 与 ACL 选择器，节点可选，高级参数限制协议与 TCP/UDP 端口；`resolveFilterSpecifier` 提供已解析 ACL 列表。结果保留 SDK 原始 Action、Line_Content、Flow、Trace，仅依据实际 Trace 补来源引用，固定 SDK 的 `DENY + no-match + 空 Trace` 标记为隐式拒绝，不猜行号。未匹配返回空结果及无结论提示，Huawei/H3C ACL 验证以 409 拒绝。补充 `web/backend/tests/test_filters.py` 和能力目录预期，后端 README/API 契约同步。

在仓库根目录执行 `web/backend/.venv/bin/python web/scripts/lab.py verify`、`smoke`、Ruff 检查与格式检查、离线 `uv lock --check`、`web/backend/.venv/bin/python web/scripts/verify_deployment.py --state web/.runtime/deploy-adv05-batch`；在 `web/frontend` 执行 `pnpm test`、`pnpm build`、`pnpm check:api`、`pnpm format:check`、全量 Playwright，以及恢复后生产构建明暗两主题的部署与双用户验收。后端 318 项、冒烟 12 项、前端 58 项、浏览器 18 项、生产浏览器每主题 3+1 项均通过，0 必需 skip。固定引擎 revision `7d0deeeac4a09973b3876327f6aef721ee12f955`，JAR SHA-256 `0927de7c740bc72f999870e842605baad9a7cb6ea66e4b01fb9a6037bea00193`，Pybatfish `2026.9.17.3748`，Python `3.12.12`，迁移0008。真实 API 与独立 worker 另验证 Cisco ACL DENY 和来源引用；详情见[ADV-05验收](../../evidence/adv-05-verification.md)。ADV-06 依赖已满足。结果只代表配置模型的 ACL 局部计算，不证明端到端可达或现场转发。
