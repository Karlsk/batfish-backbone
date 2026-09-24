# H3C / Huawei 全量功能冒烟

日期：2026-09-24。分支：`codex/huawei-vrp`。本轮重新执行，不复用上轮测试结论。
测试范围为当前已实现的厂商能力及保守转换边界，不代表验证设备支持的全部命令、
真实硬件转发或未实现协议。未修改产品代码，未提交、合并或推送。

## 1. 执行层次与结果

| 层次 | 内容 | 本轮结果 |
| --- | --- | --- |
| 服务构建 | 当前 checkout 的 allinone | 通过 |
| 全仓自动测试 | `//...`，禁用测试结果缓存 | 384 / 384 个目标实际执行并通过，零缓存结果；退出码 0，耗时 1265.830 秒（约 21 分钟） |
| 厂商专项用例 | 华三 28 项、华为 49 项，含真实原始配置测试 | 77 / 77 实际执行通过，零跳过、零失败、零错误 |
| 华三 Python/API | 真实 R1、eBGP、iBGP、14 个真实策略输入、EVPN 边界 | 五组全部通过 |
| 华为 Python/API | 真实 R2、R1+R2、Huawei eBGP/iBGP、Huawei–H3C eBGP/iBGP | 六组全部通过 |
| H3C 基线对比 | 25 份查询结果，仅归一化行顺序和对象键顺序 | 零差异 |
| 双向逐跳转发 | 六组合成拓扑，每组两方向、每方向七类 | 84 / 84 通过 |

## 2. 功能覆盖

| 功能 | 检查内容 |
| --- | --- |
| 原始输入与识别 | R1/R2 原样生产加载、厂商不误判；GB18030、ANSI、分页符、换行、缩进与行号映射 |
| 接口与 connected | IPv4、VRF、启停、MTU、聚合成员、子接口；直连/本地路由及实际转发 |
| Static | 全局/VRF、默认及显式 preference、NULL0、Next-Table；不可表达组合保留并告警 |
| ISIS | 进程选择、NET、Level、metric、P2P、可表达 BFD、邻接/RIB；华为 L2 重分发与 L1/双 Level 保守边界 |
| BGP | eBGP/iBGP、remote-AS/source、地址族、network、direct/static 重分发、MED、管理距离；华为 group/AF 继承、RR、启停覆盖、router-id 回退及默认路由导入 |
| 路由策略 | 节点顺序、首个匹配、AND/OR、默认拒绝、prefix/community/extcommunity、metric/local-pref/next-hop/community/color、无效或不可表达条件不放行 |
| EVPN/SRv6 等 | 配置保留；无虚构 VNI、EVPN 会话或跨 PE 数据面；华为无虚构 VRF leak |
| 诊断 | 目标未知/畸形命令告警，明确非目标 silent syntax，定义引用与转换限制告警 |

以上由既有专项测试与本轮 API/转发检查共同覆盖；并非每个细项均通过 API 单独验证。
华为专属特性的测试结果不外推为华三也实现了相同能力。

## 3. 真实配置结果

| 指标 | R1 单设备 | R2 单设备 | R1+R2 |
| --- | --- | --- | --- |
| 解析 | `PASSED`、无解析告警 | `PASSED`、无解析告警 | 两文件 `PASSED` |
| VI 接口 / VRF / IPv4 peer | 195 / 42 / 6 | 263 / 59 / 40 | R2 数量不变 |
| 主 RIB | 115：connected 60、local 50、static 5 | 127：connected 61、local 55、static 11 | R2 为 137，增加 10 条 ISIS L2 |
| 有向 ISIS 边 | 0 | 0 | 4 |
| 已分类转换限制告警 | 6 | 8 | 14 |

真实快照缺少外部 BGP 邻居，单设备的 `NOT_COMPATIBLE` 不作为解析失败。
R2 的 8 条限制告警包括不模拟的 OSPF 重分发汇总；不是未识别语法。
原始字节复制校验通过；原文件保持 Git 忽略，不在本报告中列出地址、策略内容或认证材料。

## 4. 合成拓扑与转发结果

H3C、Huawei、Huawei–H3C 各自的 eBGP/iBGP 共六组拓扑，均建立两个方向的 BGP 会话
和两个方向的 ISIS 邻接。检查 VRF connected/static、NULL0、Next-Table、重分发、
MED 77、community `65000:77`；华为额外检查显式 static preference 75 与策略 additive。

每组拓扑从 R1 和 R2 各发起七种 traceroute，同时验证终态和跳数：

| 类型 | 预期终态 / 跳数 | 通过数 |
| --- | --- | --- |
| ISIS 远端 LoopBack | `ACCEPTED` / 2 | 12 |
| BGP VPN 远端 LoopBack | `ACCEPTED` / 2 | 12 |
| VRF connected 远端接口 | `ACCEPTED` / 2 | 12 |
| 本地 NULL0 static | `NULL_ROUTED` / 1 | 12 |
| BGP 学习的远端 NULL0 static | `NULL_ROUTED` / 2 | 12 |
| 全局经 Next-Table 到 VPN | `ACCEPTED` / 2 | 12 |
| 不存在的目标路由 | `NO_ROUTE` / 1 | 12 |

总计：48 个正常接收、24 个预期 NULL0 丢弃、12 个预期无路由，全部符合断言。

## 5. 命令与边界

环境：Bazel 9.2.0、Python 3.12.14、Pybatfish `2026.9.17.3748`。

```sh
bazel build //projects/allinone:allinone_main --jobs=6
bazel test //... --nocache_test_results --test_output=errors --noshow_progress --jobs=6
python -O docs/development-guide/examples/huawei_manual_test.py \
  --port 19998 --output <新的仓库外目录>
```

本机 Bazel 命令额外使用已有依赖缓存 `--distdir=/private/tmp/h3c-bazel.l0kCKY`。
本轮详细日志、临时转发检查脚本与私有快照位于 `/private/tmp/vendor-smoke.JBLZUF`；
该目录含私有设备查询结果，不应发布或提交。

仍适用的能力限制：IPv6/OSPF/EVPN/MPLS/SRv6 数据面不模拟；Huawei ISIS 重分发仅支持
L2-only 进程及 cost 0–63；静态 next-hop VRF 与显式下一跳 IP 的组合不转换；
allow-as-loop 不精确执行 AS 出现次数上限。H3C 普通 VPN 的既有过宽 EVPN 限制告警
仍记录为已知告警，不表示创建了 EVPN 对象。详见 [Huawei 模块](modules/huawei-vrp.md)
与 [H3C 模块](modules/h3c-comware.md)。

本轮临时服务只绑定 `127.0.0.1:19998`，API 检查结束后已关闭，确认端口无监听。
两份原始配置 SHA-256 与测试前相同，仍被 Git 忽略；`git diff --check` 通过。

最终结论：当前已实现能力的全量专项、真实配置、API 与转发冒烟全部通过，未发现新增回归。
已知未实现能力及限制仍按上述边界处理；不能据此宣称支持相应数据面。
