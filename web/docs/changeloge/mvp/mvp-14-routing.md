# MVP-14 路由与最长前缀匹配接口

- 状态：已完成
- 阶段：1
- 依赖：[MVP-13](../mvp/mvp-13-inventory.md)
- 预计工作量：1.5 人天（实现/验证 1.0 + 测试 0.25 + 文档/自检 0.25），依赖就绪后计；超过 2 人天先拆分。
- 共享约束：[架构](../../architecture.md)、[API 契约](../../api-contracts.md)、[前端规范](../../frontend.md)、[运行设计](../../operations.md)、[验收](../../validation.md)。

## 需求与目标

用户可以按设备、VRF 和目的网络查询模型路由。

- routes、lpmRoutes、过滤、有效参数记录及下一跳结构。

## 设计与接口

- [MVP-01](../../sdk-compatibility.md) 实测 `lpmRoutes` 仅返回 Node/VRF/Ip/Network/Num_Routes；不得假定含 Next_Hop。下一跳明细来自 routes；若界面需要从 LPM 查看明细，使用命中前缀与明确 Node/VRF 查询 routes。

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

- [x] 增加两个专用请求模型、controller 和目录记录。
- [x] 过滤参数下推 SDK，保留 NextHop 类型和 VRF，不拍平成丢失语义的单字符串。
- [x] 接入任务/结果，记录首次数据面计算的等待阶段。
- [x] 运行下述验证，记录实际命令与结果，更新本文及索引状态。

## 测试与验收

- test_routes_and_lpm_match_sdk：包含默认路由、多 VRF、相同前缀不同协议。
- test_next_hop_variants：IP/接口/丢弃/VRF 下一跳可区分。
- test_unsupported_address_family：IPv6 输入明确拒绝。

后端测试在 `web/backend` 下使用 `uv run pytest` 指定上述测试文件；集成测试连接版本固定的隔离 Batfish 测试网络，不操作团队生产网络。

验收成功同时要求：契约与文档一致、失败行为可解释、无跨层/跨模块越界、没有把 mock 验证宣称为真实 SDK 验证。共享约束中的身份、版本、模型覆盖和结果截断规则均适用。

## 非目标与实施边界

- 不做路由差异、策略模拟或 EVPN RIB。

## 完成记录

2026-09-25 完成routes/lpm-routes专用接口、routing schemas/controller、能力目录启用和有效参数记录。nodes显式选择器复用MVP-13；VRF字面安全编码，专家模式为Java正则；协议为固定引擎白名单，prefix_match_type严格四枚举且默认EXACT，RIB仅main/bgp。network/ip严格IPv4，IPv6与LPM额外RIB参数在入队前拒绝。

结果保留结构化Next_Hop与VRF；LPM仅保留SDK的Node/VRF/Ip/Network/Num_Routes，详情查询以命中前缀和Node/VRF调用routes。JobsService增加当前运行租约保护的phase更新，AnalysisService仅经service更新checking_cache、querying、dataplane_or_query；不虚构数据面计算百分比，也不宣称能区分引擎已缓存的数据面。

仓库根运行 `web/backend/.venv/bin/python web/scripts/lab.py seed`、`smoke`、`verify`：实际HTTP/CLI worker冒烟 **12 passed**（两套配置均执行四类已开放分析）；MVP-01～14累计 **252 passed、0 skipped**。6项专项测试包括IPv6/未知RIB/匹配枚举拒绝、四种真实SDK下一跳对象结构、两套配置逐行逐列SDK对照、Cisco派生默认路由/BLUE VRF/同前缀不同协议/丢弃路由/四种前缀匹配、空BGP/无LPM命中、阶段更新租约与终态保护。VRF类型下一跳使用SDK对象序列化单测；真实拓扑覆盖IP/接口/丢弃结果，不声称此Cisco样例包含跨VRF转发。见 [验收证据](../../evidence/mvp-14-verification.json)。

独立审查发现地址库接受非CIDR别名并改写原始请求的问题，已先复现再限制规范CIDR，补充三种别名的registry和HTTP拒绝测试；复审通过。Ruff、锁文件、Markdown链接与Git空白检查通过。固定Batfish0.36.0/Pybatfish2026.9.17.3748/JAR，未修改Java；无必需检查遗漏，MVP-15依赖就绪。
