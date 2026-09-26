# Pybatfish / 引擎能力覆盖表

日期：2026-09-26。MVP-01～25 和 ADV-01～11 已完成；登记式专家入口仅开放已有能力。ADV-11 仅建立比较元数据与差异分析上下文，尚未开放差异计算。固定 Pybatfish 2026.9.17.3748，与当前分支引擎的 75 个模板已核验，核心查询已实测；结论、参数与公开方法清单见 [兼容性报告](sdk-compatibility.md) 和 [证据](evidence/mvp-01-sdk-baseline.json)。Web 只开放已经登记并单独适配的能力，其余模板保持范围外。

## 适配原则

- 首先适配公共网络/快照操作与明确用户场景；内部方法、连接配置、任意 Python 执行不对外暴露。
- 常用问题提供专用易用接口；ADV-09 的专家入口只复用已经登记的能力，不能用通用路由绕过参数/权限/模型覆盖限制。
- SDK 公共能力不等于每个厂商可准确模拟；当前分支 H3C/Huawei 的具体边界仍适用。
- stable/experimental 是上游模板所在目录，不直接表示本产品功能成熟度。MVP 使用的 nodeProperties/interfaceProperties/traceroute 在 experimental 目录，必须用当前引擎实测后启用。
- 其余能力明确留在三阶段之外；后续可追加小型 spec，不能把“完整目录”写成“完整实现”。

## 公共 SDK 操作

| 能力 | SDK 接口/机制 | 计划 |
| --- | --- | --- |
| Session 连接及版本/模板 | Session 初始化、运行时问题目录 | MVP-01/02/09；连接参数只在服务端 |
| 网络创建/选择/列表 | set_network、list_networks | MVP-06；UI 仅管理本应用登记资源 |
| 网络删除 | delete_network | MVP-23；管理员、依赖检查 |
| 快照初始化/选择/列表 | init_snapshot、set_snapshot、list_snapshots | MVP-10；不可覆盖 |
| 快照删除 | delete_snapshot | MVP-23；管理员、依赖检查 |
| 派生快照 | fork_snapshot | ADV-16；先只开放节点/接口停用 |
| 问题和答案 | q.<已登记问题>、answer、结构化答案 | MVP-12 起逐项实现 |
| 参考库 | get/put/delete_reference_book 等 | 当前三阶段范围外 |
| 角色/高级输入/云建模等其他公共操作 | 以固定 SDK 版本公开接口核验 | 目录记录但不自动开放 |
| 后台分析/状态/已有答案 | answer(background=True)、get_work_status、get_answer 已实测；初始化仍同步 | MVP-01 记录基线；MVP-09 不因此启用自动接管 |
| 运行中取消/引擎重启后恢复 | 没有公开取消方法；引擎重启后的句柄持久性未验证 | 首版不承诺 |
| SDK 私有方法 | 下划线方法、内部 HTTP helper | 不对外适配 |

公共方法参考：[Batfish Commands](https://pybatfish.readthedocs.io/en/latest/batfish_commands.html)。首次调用与结果语义以当前版本实测为准；快照 SDK 支持 extra_args 不代表 Web 允许任意引擎参数。

## 当前仓库问题模板清单

共 75 个模板。每行链接到仓库实际模板；“范围外”不等于 Batfish 不支持，只表示不包含在这次三阶段工作中。列出的 spec ID 可在 [开发索引](changeloge/README.md) 定位。

| 问题 | 上游目录 | Web 计划 |
| --- | --- | --- |
| [a10VirtualServerConfiguration](../../questions/experimental/a10VirtualServerConfiguration.json) | experimental | 三阶段范围外；未登记不开放 |
| [bgpPeerConfiguration](../../questions/experimental/bgpPeerConfiguration.json) | experimental | 三阶段范围外；未登记不开放 |
| [bgpProcessConfiguration](../../questions/experimental/bgpProcessConfiguration.json) | experimental | 三阶段范围外；未登记不开放 |
| [bgpSessionCompatibility](../../questions/experimental/bgpSessionCompatibility.json) | experimental | ADV-03 |
| [bgpSessionStatus](../../questions/experimental/bgpSessionStatus.json) | experimental | ADV-03 |
| [bidirectionalReachability](../../questions/experimental/bidirectionalReachability.json) | experimental | 三阶段范围外；未登记不开放 |
| [bidirectionalTraceroute](../../questions/experimental/bidirectionalTraceroute.json) | experimental | 三阶段范围外；未登记不开放 |
| [compareFilters](../../questions/experimental/compareFilters.json) | experimental | 三阶段范围外；未登记不开放 |
| [comparePeerGroupPolicies](../../questions/experimental/comparePeerGroupPolicies.json) | experimental | 三阶段范围外；未登记不开放 |
| [compareRoutePolicies](../../questions/experimental/compareRoutePolicies.json) | experimental | 三阶段范围外；未登记不开放 |
| [detectLoops](../../questions/experimental/detectLoops.json) | experimental | 三阶段范围外；未登记不开放 |
| [differentialReachability](../../questions/experimental/differentialReachability.json) | experimental | ADV-14 |
| [evpnL3VniProperties](../../questions/experimental/evpnL3VniProperties.json) | experimental | 三阶段范围外；未登记不开放 |
| [f5BigipVipConfiguration](../../questions/experimental/f5BigipVipConfiguration.json) | experimental | 三阶段范围外；未登记不开放 |
| [filterLineReachability](../../questions/experimental/filterLineReachability.json) | experimental | ADV-07 |
| [filterTable](../../questions/experimental/filterTable.json) | experimental | 三阶段范围外；未登记不开放 |
| [findMatchingFilterLines](../../questions/experimental/findMatchingFilterLines.json) | experimental | 三阶段范围外；未登记不开放 |
| [hsrpProperties](../../questions/experimental/hsrpProperties.json) | experimental | 三阶段范围外；未登记不开放 |
| [interfaceMtu](../../questions/experimental/interfaceMtu.json) | experimental | 三阶段范围外；未登记不开放 |
| [interfaceProperties](../../questions/experimental/interfaceProperties.json) | experimental | MVP-13 |
| [loopbackMultipathConsistency](../../questions/experimental/loopbackMultipathConsistency.json) | experimental | 三阶段范围外；未登记不开放 |
| [mlagProperties](../../questions/experimental/mlagProperties.json) | experimental | 三阶段范围外；未登记不开放 |
| [multipathConsistency](../../questions/experimental/multipathConsistency.json) | experimental | 三阶段范围外；未登记不开放 |
| [namedStructures](../../questions/experimental/namedStructures.json) | experimental | 三阶段范围外；未登记不开放 |
| [nodeProperties](../../questions/experimental/nodeProperties.json) | experimental | MVP-13 |
| [ospfAreaConfiguration](../../questions/experimental/ospfAreaConfiguration.json) | experimental | 三阶段范围外；未登记不开放 |
| [ospfInterfaceConfiguration](../../questions/experimental/ospfInterfaceConfiguration.json) | experimental | 三阶段范围外；未登记不开放 |
| [ospfProcessConfiguration](../../questions/experimental/ospfProcessConfiguration.json) | experimental | 三阶段范围外；未登记不开放 |
| [ospfSessionCompatibility](../../questions/experimental/ospfSessionCompatibility.json) | experimental | 三阶段范围外；未登记不开放 |
| [prefixTracer](../../questions/experimental/prefixTracer.json) | experimental | 三阶段范围外；未登记不开放 |
| [reachability](../../questions/experimental/reachability.json) | experimental | 三阶段范围外；未登记不开放 |
| [resolveFilterSpecifier](../../questions/experimental/resolveFilterSpecifier.json) | experimental | ADV-05 内部选择辅助 |
| [resolveInterfaceSpecifier](../../questions/experimental/resolveInterfaceSpecifier.json) | experimental | 三阶段范围外；未登记不开放 |
| [resolveIpSpecifier](../../questions/experimental/resolveIpSpecifier.json) | experimental | 三阶段范围外；未登记不开放 |
| [resolveIpsOfLocationSpecifier](../../questions/experimental/resolveIpsOfLocationSpecifier.json) | experimental | 三阶段范围外；未登记不开放 |
| [resolveLocationSpecifier](../../questions/experimental/resolveLocationSpecifier.json) | experimental | 三阶段范围外；未登记不开放 |
| [resolveNodeSpecifier](../../questions/experimental/resolveNodeSpecifier.json) | experimental | 三阶段范围外；未登记不开放 |
| [searchFilters](../../questions/experimental/searchFilters.json) | experimental | ADV-07 |
| [searchRoutePolicies](../../questions/experimental/searchRoutePolicies.json) | experimental | 三阶段范围外；未登记不开放 |
| [snmpCommunityClients](../../questions/experimental/snmpCommunityClients.json) | experimental | 三阶段范围外；未登记不开放 |
| [subnetMultipathConsistency](../../questions/experimental/subnetMultipathConsistency.json) | experimental | 三阶段范围外；未登记不开放 |
| [switchedVlanProperties](../../questions/experimental/switchedVlanProperties.json) | experimental | 三阶段范围外；未登记不开放 |
| [testRoutePolicies](../../questions/experimental/testRoutePolicies.json) | experimental | 三阶段范围外；未登记不开放 |
| [traceroute](../../questions/experimental/traceroute.json) | experimental | MVP-15 |
| [transferBDDValidation](../../questions/experimental/transferBDDValidation.json) | experimental | 三阶段范围外；未登记不开放 |
| [viModel](../../questions/experimental/viModel.json) | experimental | 三阶段范围外；未登记不开放 |
| [vrrpProperties](../../questions/experimental/vrrpProperties.json) | experimental | 三阶段范围外；未登记不开放 |
| [vxlanVniProperties](../../questions/experimental/vxlanVniProperties.json) | experimental | 三阶段范围外；未登记不开放 |
| [aaaAuthenticationLogin](../../questions/stable/aaaAuthenticationLogin.json) | stable | 三阶段范围外；未登记不开放 |
| [bgpEdges](../../questions/stable/bgpEdges.json) | stable | ADV-01 |
| [bgpRib](../../questions/stable/bgpRib.json) | stable | 三阶段范围外；未登记不开放 |
| [definedStructures](../../questions/stable/definedStructures.json) | stable | 三阶段范围外；未登记不开放 |
| [edges](../../questions/stable/edges.json) | stable | 三阶段范围外；未登记不开放 |
| [eigrpEdges](../../questions/stable/eigrpEdges.json) | stable | 三阶段范围外；未登记不开放 |
| [evpnRib](../../questions/stable/evpnRib.json) | stable | 三阶段范围外；未登记不开放 |
| [fileParseStatus](../../questions/stable/fileParseStatus.json) | stable | MVP-10/11 |
| [initIssues](../../questions/stable/initIssues.json) | stable | MVP-10/11 |
| [ipOwners](../../questions/stable/ipOwners.json) | stable | 三阶段范围外；未登记不开放 |
| [ipsecEdges](../../questions/stable/ipsecEdges.json) | stable | 三阶段范围外；未登记不开放 |
| [ipsecSessionStatus](../../questions/stable/ipsecSessionStatus.json) | stable | 三阶段范围外；未登记不开放 |
| [isisEdges](../../questions/stable/isisEdges.json) | stable | ADV-01 |
| [layer1Edges](../../questions/stable/layer1Edges.json) | stable | 三阶段范围外；未登记不开放 |
| [layer3Edges](../../questions/stable/layer3Edges.json) | stable | ADV-01 |
| [lpmRoutes](../../questions/stable/lpmRoutes.json) | stable | MVP-14 |
| [ospfEdges](../../questions/stable/ospfEdges.json) | stable | ADV-01 |
| [parseWarning](../../questions/stable/parseWarning.json) | stable | MVP-11 |
| [referencedStructures](../../questions/stable/referencedStructures.json) | stable | 三阶段范围外；未登记不开放 |
| [routes](../../questions/stable/routes.json) | stable | MVP-14；ADV-13 增加差异 |
| [testFilters](../../questions/stable/testFilters.json) | stable | ADV-05 |
| [undefinedReferences](../../questions/stable/undefinedReferences.json) | stable | 三阶段范围外；未登记不开放 |
| [unusedStructures](../../questions/stable/unusedStructures.json) | stable | 三阶段范围外；未登记不开放 |
| [userProvidedLayer1Edges](../../questions/stable/userProvidedLayer1Edges.json) | stable | 三阶段范围外；未登记不开放 |
| [viConversionStatus](../../questions/stable/viConversionStatus.json) | stable | 三阶段范围外；未登记不开放 |
| [viConversionWarning](../../questions/stable/viConversionWarning.json) | stable | MVP-11 |
| [vxlanEdges](../../questions/stable/vxlanEdges.json) | stable | 三阶段范围外；未登记不开放 |

## 版本与覆盖报告

MVP-01 报告需至少列出 SDK 版本、引擎 revision、模板加载、参数 schema、结果列与嵌套类型、公开任务句柄/超时行为的实测结论。新引擎缺失问题时将 capability.enabled=false 并给 disabled_reason；不能到用户运行时才以无解释的500失败。

问题声明支持 differential 并不自动变成 Web 对比功能。ADV-13/14 明确验证方向、结果结构和模型覆盖后才开放。配置文本 diff 是 Web 层对不可变原始文件的比较，不是虚构的 SDK 问题。
