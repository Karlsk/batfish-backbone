# ADV-07 ACL 条件搜索与无效规则接口

- 状态：已完成
- 阶段：2
- 依赖：[ADV-06](../advance/adv-06-acl-test-ui.md)
- 预计工作量：2.0 人天（实现/验证 1.25 + 测试 0.5 + 文档/自检 0.25），依赖就绪后计；超过 2 人天先拆分。
- 共享约束：[架构](../../architecture.md)、[API 契约](../../api-contracts.md)、[前端规范](../../frontend.md)、[运行设计](../../operations.md)、[验收](../../validation.md)。

## 需求与目标

补充特定条件下的匹配流量搜索和不可达规则诊断。

- searchFilters、filterLineReachability；区分流量搜索和规则可达性。

## 设计与接口

- POST S/analyses/search-filters：nodes、filters、action、options.headers；限制查询范围。
- POST S/analyses/filter-line-reachability：nodes、filters、options.ignore_composites。
- 不可达规则可能来自前序遮蔽或空匹配条件，不统一命名为遮蔽。

沿用 api → service → controller；所有跨业务模块调用经过 service。非 SDK 存储由本模块 repository 负责。浏览器不接触 SDK 会话或连接参数。

## 预期改动位置

以下是实现时的目标路径，本次文档编写不创建代码文件：

- `web/backend/app/modules/analysis/schemas/filters.py`
- `web/backend/app/modules/analysis/controllers/filters.py`
- `web/backend/tests/test_filter_search.py`

## 实施步骤

- [x] 登记两个问题的独立 schema 和成本/数据面要求。
- [x] 实现受限 headers 和 action 映射，不向用户开放任意引擎控制参数。
- [x] 保留 SDK 的阻挡行/原因字段，不能返回字段缺失的肯定判断。
- [x] 运行下述验证，记录实际命令与结果，更新本文及索引状态。

## 测试与验收

- test_search_filter_witness：返回示例 flow 可由 testFilters 复核。
- test_shadowed_and_empty_condition：两种不可达原因不混淆。
- test_no_witness：在查询条件下无匹配，不代表全网无风险。

后端测试在 `web/backend` 下使用 `uv run pytest` 指定上述测试文件；集成测试连接版本固定的隔离 Batfish 测试网络，不操作团队生产网络。

验收成功同时要求：契约与文档一致、失败行为可解释、无跨层/跨模块越界、没有把 mock 验证宣称为真实 SDK 验证。共享约束中的身份、版本、模型覆盖和结果截断规则均适用。

## 非目标与实施边界

- 不做全网无限制策略证明、规则自动合并或自动修复。

## 完成记录

2026-09-26：在 `schemas/filters.py` 建立设备/ACL各1～10个字面值、精确源/目的 IPv4、协议端口和动作/行号的独立请求契约；`api.py`、`registry.py`、`service.py`、`controllers/filters.py`、`controller.py` 分别完成入口、成本登记、模型边界、固定SDK映射与证据/警告保留。`test_filter_search.py` 使用真实 Cisco 四设备派生配置核验示例 Flow 可重测、遮蔽与空条件不同、空搜索不等于安全、厂商限制；并更新累计能力清单断言、OpenAPI 生成类型和共享契约。完整命令、325项后端/12项冒烟/70项前端/20项浏览器/恢复后双主题生产验收与修复过的环境问题见[ADV-07验收](../../evidence/adv-07-verification.md)。固定引擎 revision `7d0deeeac4a09973b3876327f6aef721ee12f955`，Pybatfish `2026.9.17.3748`，Python `3.12.12`；ADV-08 依赖已满足。只验证配置模型的 Web 功能，不证明现场策略安全。
