# MVP-14 路由与最长前缀匹配接口

- 状态：待开发
- 阶段：1
- 依赖：[MVP-13](../mvp/mvp-13-inventory.md)
- 预计工作量：1.5 人天（实现/验证 1.0 + 测试 0.25 + 文档/自检 0.25），依赖就绪后计；超过 2 人天先拆分。
- 共享约束：[架构](../../architecture.md)、[API 契约](../../api-contracts.md)、[前端规范](../../frontend.md)、[运行设计](../../operations.md)、[验收](../../validation.md)。

## 需求与目标

用户可以按设备、VRF 和目的网络查询模型路由。

- routes、lpmRoutes、过滤、有效参数记录及下一跳结构。

## 设计与接口

- POST S/analyses/routes：nodes 可选，options.vrfs/network/protocols/prefix_match_type/rib。
- POST S/analyses/lpm-routes：ip 必填；nodes/options.vrfs 可选。
- 首版 IPv4、rib 为 main/bgp；前缀匹配枚举按模板，不能把 exact 默认为 longest match。

沿用 api → service → controller；所有跨业务模块调用经过 service。非 SDK 存储由本模块 repository 负责。浏览器不接触 SDK 会话或连接参数。

## 预期改动位置

以下是实现时的目标路径，本次文档编写不创建代码文件：

- `web/backend/app/modules/analysis/schemas/routing.py`
- `web/backend/app/modules/analysis/controllers/routing.py`
- `web/backend/app/modules/analysis/registry.py`
- `web/backend/tests/test_routing.py`

## 实施步骤

- [ ] 增加两个专用请求模型、controller 和目录记录。
- [ ] 过滤参数下推 SDK，保留 NextHop 类型和 VRF，不拍平成丢失语义的单字符串。
- [ ] 接入任务/结果，记录首次数据面计算的等待阶段。
- [ ] 运行下述验证，记录实际命令与结果，更新本文及索引状态。

## 测试与验收

- test_routes_and_lpm_match_sdk：包含默认路由、多 VRF、相同前缀不同协议。
- test_next_hop_variants：IP/接口/丢弃/VRF 下一跳可区分。
- test_unsupported_address_family：IPv6 输入明确拒绝。

后端测试在 `web/backend` 下使用 `uv run pytest` 指定上述测试文件；集成测试连接版本固定的隔离 Batfish 测试网络，不操作团队生产网络。

验收成功同时要求：契约与文档一致、失败行为可解释、无跨层/跨模块越界、没有把 mock 验证宣称为真实 SDK 验证。共享约束中的身份、版本、模型覆盖和结果截断规则均适用。

## 非目标与实施边界

- 不做路由差异、策略模拟或 EVPN RIB。

## 完成记录

当前尚未开发或运行本 spec 的产品测试。实施者完成后在本节记录实际文件、验证命令、结果、引擎/SDK版本（如涉及）和剩余限制；存在验收失败时保持未通过状态。
