# Huawei VRP 第一阶段回归记录

日期：2026-09-24。分支：`codex/huawei-vrp`。本记录只包含合成配置、对象数量和验证结果，
不包含真实设备地址、认证材料或原始配置片段。能力边界见 [Huawei 模块](modules/huawei-vrp.md)。

## 已验证的基线与公共回归

| 步骤 | 验证 | 结果 |
| --- | --- | --- |
| 1 | 修改前 H3C grammar `:all` | 通过（包含测试与 PMD） |
| 2 | 修改前服务运行 Huawei 合成 API 用例 | 按预期失败：两个配置均为 `UNKNOWN` |
| 3 | 最新公共模型 `//projects/common/...` | 121 / 121 测试目标通过 |
| 4 | 原始 R2 生产加载、提取和 VI 转换 | `PASSED`，无解析告警；263 接口、57 普通 VPN、59 VI VRF、40 VI IPv4 peer；其他对象数量由真实配置测试断言 |
| 5 | H3C 原始 R1、双节点 eBGP、双节点 iBGP、策略、EVPN 边界 API | 五组通过，14 个真实策略用例通过 |
| 6 | H3C API 与修改前基线比较 | 25 份 JSON 查询结果逐行归一排序后完全一致 |
| 7 | `//projects/batfish/...` | 182 / 182 测试目标通过（审查修复前基线；最终版本由全仓库复验覆盖） |
| 8 | R2 单设备 Python/API | `PASSED`；263 接口、40 peer、127 条路由：connected 61、local 55、static 11；40 个外部 BGP 会话未兼容、ISIS 边为 0，符合单设备边界 |
| 9 | R1+R2 Python/API | 两文件 `PASSED`；4 条有向 ISIS 边，R2 有 137 条路由（新增 10 条 ISIS L2）；没有 VNI 或 EVPN RIB |
| 10 | 首轮修复后 `bazel test //...` | 384 / 384 测试目标通过；159 个执行、225 个缓存，442 秒 |
| 11 | 社区策略、空白行修复及三节点用例后的 `bazel test //...` | 384 / 384 测试目标通过；67 个执行、317 个缓存，173 秒；当时 Huawei 39 个实际用例、H3C 28 个 |
| 12 | 最终审查修复后的 `bazel test //...` | 384 / 384 测试目标通过；130 个执行、254 个缓存，274 秒；Huawei 49 个实际用例、H3C 28 个，零跳过、零失败、零错误 |

首轮 Huawei 合成 API 验收在告警白名单处失败，定位为正常 IPv4 地址族触发多余的 BGP
运行态限制告警。修复后已重建、重启服务，并重新执行六组完整场景，全部通过。

## 最终 Python/API 验收

环境：Bazel 9.2.0、Python 3.12.14、Pybatfish `2026.9.17.3748`。使用
`python -O docs/development-guide/examples/huawei_manual_test.py --port 19998 --output <新的仓库外目录>`，
显式 `require()` 检查在优化模式下仍生效；进程退出码为 0，最终 `acceptance=PASS`。

| 场景 | 解析 / 告警 | 邻接、路由和策略结果 |
| --- | --- | --- |
| R2 | `PASSED`；8 条已分类转换限制告警，无解析告警 | 263 接口、59 VRF、40 IPv4 peer；127 条路由；单节点无 ISIS 边，外部 BGP 未建立符合预期 |
| R1+R2 | 两文件 `PASSED`；14 条已分类限制告警 | 4 条有向 ISIS 边；R2 学到 10 条 ISIS L2 路由；不要求缺失的外部 BGP 邻居建立 |
| Huawei eBGP | 两文件 `PASSED`；零初始化告警 | 2 配置 peer、2 已建立会话、2 有向 ISIS 边；R1 为 13 条主 RIB / 4 条 BGP RIB 路由；策略通过 |
| Huawei iBGP | 同上 | 同上，远端路由协议为 iBGP |
| Huawei–H3C eBGP | 两文件 `PASSED`；保留 1 条 H3C 既有普通 VPN 的过宽限制告警 | 同上，跨厂商 ISIS 和 eBGP 通过 |
| Huawei–H3C iBGP | 同上 | 同上，跨厂商 ISIS 和 iBGP 通过 |

四组合成场景均检查：connected、ISIS preference 15、NULL0 static preference 60/75、
远端 BGP preference 255、Next-Table `vrf blue`、direct/static 重分发、MED 77、
community `65000:77`，以及策略 additive 后保留输入 community。所有场景的 VNI/EVPN RIB
查询为空，BGP session 不含 EVPN AF；真实生产 VI 测试额外断言无 EVPN address-family、
无 VrfLeakConfig。API 查询为空本身不能证明后两个内部结构条件。

原始配置仅作为本地可选资源加载；两份文件保持忽略状态。H3C 基线比较仅消除结果行顺序，
没有忽略列或路由属性。真实快照缺少外部设备，因此没有将外部邻居未建邻判为解析失败。

## 自动数据面覆盖

初始 `HuaweiDataPlaneTest` 的 11 项测试通过，并通过独立代码审查。覆盖四组双节点、
三节点 RR 正例与不反射负例、组级 import/export 策略、AF 成员启停覆盖、`network` 起源、
BGP→ISIS 重分发及未启用重分发的负例、EVPN/SRv6 不虚构会话/路由/泄漏。

显式 BGP preference 33/2 不只检查字段，还与 preference 75 的本地 static 竞争，验证
最终主 RIB 选路。BGP→ISIS 学到的路由为 external level-2（`ISIS_EL2`），preference 15。
最初的数据面测试批次没有改动生产代码；部分初次失败来自合成配置与测试预期。
最终审查修复增加了物理接口 router-id 回退、默认路由导入开关、MED/cost、策略 metric
优先级、完整参数验证和 L1/双 Level 原生路由保留的专项覆盖。Huawei 最终为 49 项实际用例。

## 收尾状态

整体审查发现的 router-id 物理接口回退、默认路由重分发和重分发参数验证问题，均已通过
针对性的失败→成功测试及定向复审。普通 import-route 不再导入默认路由；显式 network
和 default-route imported 独立验证。BGP MED 77、ISIS cost 50 及策略覆盖 cost 88 均有断言。

R2 的限制告警从 7 条增至 8 条：新增一条汇总说明 3 个 OSPF 进程路由导入 BGP 的命令
保留但不模拟。不是新的语法失败，也未新增模拟的 OSPF 路由。

既有 VI 的边界：静态路由同时指定 next-hop VRF 和下一跳 IP 时保留、告警、不转换；
裸 VPN/public Next-Table 可转换。ISIS 重分发仅支持 L2-only 进程及 cost 0–63；L1/双 Level
重分发保留、告警、不转换，其原生 ISIS 路由仍支持。allow-as-loop 仅映射为允许本 AS 的
标志，不能精确执行出现次数上限。IPv6/OSPF/EVPN/MPLS/SRv6 数据面不在本阶段支持范围。

社区多值匹配和空白行兼容性修复已通过针对性的失败→成功测试：单条标准 community
规则要求全部值同时存在，允许额外 community；扩展 community 默认匹配不变；空格/Tab
空行不再导致语法错误，原始行号和有效缩进不变。Huawei 共 49 项、H3C 共 28 项测试及
相关 PMD 通过。最终全仓库复验 384 / 384 通过，最新二进制的六组 API 场景再次全部通过。
37 个新增或修改的 Java 文件格式检查通过，7 份相关文档的本地链接均有效，
`git diff --check` 无错误。最终定向复审确认五项发现全部解决，没有新的 Critical/Important 问题。

最终全仓库命令：

```sh
bazel test //... --test_output=errors --noshow_progress --jobs=6 \
  --distdir=/private/tmp/h3c-bazel.l0kCKY
```

`--distdir` 是本次机器已有的依赖缓存目录，其他环境可省略或替换；原始配置缺失时仅
跳过可选的真实配置测试，不跳过合成测试。本次两份私有配置均在，因此真实配置用例实际执行。

本轮临时服务仅绑定 `127.0.0.1:19998`，与已有服务和数据目录隔离。

最终修复版本上再次执行了历史 H3C 五组 API 回归，25 份结果与基线仍完全一致。
最终 API 测试结束后已停止本轮启动的服务，并再次确认 19998 端口无监听。真实配置的
SHA-256 与开始时一致，仍被 Git 忽略；没有提交、合并或推送。
