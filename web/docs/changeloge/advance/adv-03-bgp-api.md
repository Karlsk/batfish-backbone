# ADV-03 BGP 模型状态与兼容性接口

- 状态：已完成
- 阶段：2
- 依赖：[ADV-02](../advance/adv-02-topology-ui.md)
- 预计工作量：1.0 人天（实现/验证 0.5 + 测试 0.25 + 文档/自检 0.25），依赖就绪后计；超过 2 人天先拆分。
- 共享约束：[架构](../../architecture.md)、[API 契约](../../api-contracts.md)、[前端规范](../../frontend.md)、[运行设计](../../operations.md)、[验收](../../validation.md)。

## 需求与目标

提供可定位配置问题的 BGP 会话与兼容性分析。

- bgpSessionStatus 与 bgpSessionCompatibility，按节点/远端节点筛选。

## 设计与接口

- POST S/analyses/bgp-sessions，options.mode=status|compatibility、nodes、remote_nodes；映射模板实际支持参数。
- 返回 table，保留本地/远端节点接口、VRF、AS、地址、状态和不能识别的字段。
- 字段只表示模型推演，不接设备查询实时 session。

沿用 api → service → controller；所有跨业务模块调用经过 service。非 SDK 存储由本模块 repository 负责。浏览器不接触 SDK 会话或连接参数。

## 预期改动位置

以下是实现时的目标路径，本次文档编写不创建代码文件：

- `web/backend/app/modules/analysis/schemas/bgp.py`
- `web/backend/app/modules/analysis/controllers/bgp.py`
- `web/backend/tests/test_bgp.py`

## 实施步骤

- [x] 验证问题 schema 和状态枚举，登记能力。
- [x] 实现参数/列映射，原始状态与中文标签分离。
- [x] 针对 H3C/Huawei 未模拟地址族附加覆盖限制。
- [x] 运行下述验证，记录实际命令与结果，更新本文及索引状态。

## 测试与验收

- test_bgp_as_mismatch：已知 AS 配置不一致可识别。
- test_bgp_established_semantics：成功状态保留模型标签。
- test_bgp_ipv6_unsupported：不把未模拟会话当正常。

后端测试在 `web/backend` 下使用 `uv run pytest` 指定上述测试文件；集成测试连接版本固定的隔离 Batfish 测试网络，不操作团队生产网络。

验收成功同时要求：契约与文档一致、失败行为可解释、无跨层/跨模块越界、没有把 mock 验证宣称为真实 SDK 验证。共享约束中的身份、版本、模型覆盖和结果截断规则均适用。

## 非目标与实施边界

- 不做 BGP 实时监控、自动修复或完整路由策略分析。

## 完成记录

2026-09-26：固定 SDK 双问题、typed参数与原始结果表格、模型及厂商地址族警告已实现。Cisco同AS/AS错配、Huawei/H3C IPv6 peer派生配置与直接SDK逐行比对通过；MVP及前两篇ADV累计门槛通过。实际命令、计数、源码指纹和限制见 [ADV-03验收](../../evidence/adv-03-verification.md)。
