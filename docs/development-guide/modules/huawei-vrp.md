# Huawei VRP：解析、转换与验收

## 1. 范围和版本

验证样本是本地 `docs/configuration/NJ-SCT-R02` 的原始终端采集，软件版本头为
`!Software Version V800R023C00SPC500`。它不能证明硬件型号：VI 使用
`HUAWEI_VRP_UNSPECIFIED`，格式枚举为 `HUAWEI_VRP`，JSON 值为 `huawei_vrp`。
没有新增 VI schema；既有厂商的格式序列化和管理距离不变。

“解析支持”不等于“数据面支持”。本阶段边界：

| 模块 | IPv4 VI / 数据面 | 仅提取或保留 |
| --- | --- | --- |
| 接口、connected | 接口、启停、描述、MTU、地址、VRF、L2/L3、Eth-Trunk 成员、子接口 VLAN；connected 自然生成 | IPv6 地址、SR/MPLS 和不可表达的二层封装 |
| 静态路由 | 全局/VRF、IP/接口下一跳、NULL0、无显式下一跳 IP 的 next-table VRF、preference | IPv6 static、运行态探测、同时指定 VPN 与下一跳 IP 的跨表递归 |
| ISIS | 一个默认 VRF IPv4 进程，NET、Level、metric、P2P、passive、可表达 BFD；仅 L2-only 进程的 direct/static/BGP 重分发 | 额外进程、L1/双 Level 重分发、IPv6、SR、LFA/TI-LFA |
| BGP | 每 VRF IPv4 process，peer/group、remote-AS、source、multihop、RR、社区、allow-as、substitute-as、策略、network、direct/static 重分发 | IPv6/VPNv4/VPNv6/EVPN/SR-policy AF、OSPF 重分发、不能模拟的运行态命令 |
| Route-policy | 升序 node、首个匹配、默认拒绝；IPv4 prefix/community/extcommunity、cost/local-pref/IPv4 next-hop/community/color action | IPv6 next-hop/RD 等匹配使用 FALSE guard 和告警 |
| EVPN / SRv6 | 可确定的 VRF RD | EVPN instance、BD、EVPL、RD/RT、接口绑定、locator/opcode 等配置 |
| OSPFv2 / OSPFv3 | 不转换、不建立邻接或路由 | 显式识别、保留并汇总说明 |

不能通过虚构 VNI、IPv4 EVPN peer 或 VRF leak config 来近似 MPLS/SRv6 EVPN。
即使配置有 `Nve1` 或 RD/RT，也不代表存在 VXLAN VNI。

## 2. 数据流和代码边界

```text
原始配置字节（UTF-8 / GB18030，包含终端控制序列）
    ↓ 生产快照加载、文本解码
格式检测 → HUAWEI_VRP → ParseVendorConfigurationJob
    ↓
Huawei normalizer：终端噪声清理 + 原始行号映射
    ↓
ANTLR lexer/parser：保留行首缩进和换行
    ↓
statement tree：按缩进、# 建立嵌套视图
    ↓
extractor：按上下文验证 → 厂商模型 + 定义/引用 + silent syntax
    ↓
conversion：默认值、group/AF 继承、能力边界
    ↓
VI Configuration / Vrf / Interface / RoutingPolicy / ISIS / BGP
    ↓
后处理 → 拓扑 → dataplane → Pybatfish 问题答案
```

源码入口：

- [格式检测](../../../projects/batfish/src/main/java/org/batfish/grammar/VendorConfigurationFormatDetector.java)
  与 [parse-job 分派](../../../projects/batfish/src/main/java/org/batfish/job/ParseVendorConfigurationJob.java)。
- [Huawei ANTLR grammar](../../../projects/batfish/src/main/antlr4/org/batfish/vendor/huawei/grammar/)。
- [normalizer、树和提取器](../../../projects/batfish/src/main/java/org/batfish/vendor/huawei/grammar/)。
- [厂商表示与转换](../../../projects/batfish/src/main/java/org/batfish/vendor/huawei/representation/)。
- [模块测试](../../../projects/batfish/src/test/java/org/batfish/vendor/huawei/grammar/)。

Huawei 实现不把文本改写成 H3C，也不调用 H3C 转换器。两者共享 Batfish 的 VI 和协议引擎，
但分别承担命令语义、默认值和继承规则。

## 3. 输入归一化与视图树

R2 的分页覆盖序列可简写为：

```text
两个空格 + ---- More ---- + ESC[16D + 16 个空格 + ESC[16D + 真实配置
```

只去掉 `---- More ----` 会留下两个前导空格，把顶层 `interface` 或 `route-policy` 错放
到上一个视图。先完整消除终端覆盖序列，再保留真实配置自身的缩进。不能对配置每行先做
`trim()`；需要在 lexer 区分行首缩进与行内分隔符。

normalizer 还处理 CRCRLF/CRLF/CR、ANSI、退格、`<设备名>` / `[~设备名]` 提示符及残留
`display current-configuration` / `dis cur`。原始文件不变，源行映射用于解析警告和结构引用。

视图树区分 BGP 主视图、全局地址族和 VPN instance 地址族：同一条 `peer` 命令在不同
视图中的含义不同。`#` 和缩进用于恢复视图边界，不能把所有 peer 扁平化为一个 map。

未知目标命令必须告警。QoS、AAA、Telemetry 等非目标子树通过明确规则进入 silent syntax；
不能把任意 `undo` 或任意未知行都当作无影响操作。认证字段不得进入日志或公开 fixture。

## 4. 默认值、继承和转换原理

### 4.1 接口、静态路由和 ISIS

接口绑定 VRF 后，地址进入对应 VRF；connected/local 路由由统一接口模型派生，不手工添加。
Eth-Trunk 成员指向聚合接口，子接口的 VLAN 封装与物理依赖分别表达。

Huawei 管理距离采用 direct/local 0、static 60、ISIS 15、BGP 255。
显式静态 preference 优先于缺省值，NULL0 转为 discard。无显式下一跳 IP 的
`ip route-static <prefix> <mask> vpn-instance <vrf>` 使用 VI `NextHopVrf` 表达 next-table；
如果同一命令还指定下一跳 IP，VI 不能同时表达目标 VRF 和该 IP，因此配置会保留并告警，
但不进入模拟。[Huawei next-table 命令说明](https://info.support.huawei.com/hedex/api/pages/EDOC1100277644/AEM10221/04/resources/command/yunshan/IPV4ADDROUTENHISPRIVTABLE%28STATICRTOM%29.html)
这些值不能照搬其他厂商。[官方优先级说明](https://info.support.huawei.com/hedex/api/pages/EDOC1100277650/AZM1016J/03/resources/vrp/feature_0003992083.html)

所有 ISIS 进程均保留。默认 VRF 中，按绑定的 IPv4 enabled interface 数最多选择进程，
平局取最小进程号；R2 应选 `10`。其余进程只产生汇总限制提示，不把多个进程混成一个。
若所有进程均位于 VPN 或没有可选 IPv4 进程，也会汇总提示全部保留、不转换。

普通 `import-route` 不引入默认路由。ISIS 在 Level-2-only 进程中支持 direct/static/BGP 重分发及
0–63 的显式 `cost`；源进程筛选、其他 level、cost-type、tag、inherit-cost 及 wide-only
cost 等未实现形式保留、汇总告警并省略，不忽略修饰参数后继续重分发。
已有数据面会把双 Level 进程的重分发初始化为 EL1；当前不改变 VI，故 L1/双 Level
进程的重分发保守省略并告警，不伪造协议与 level 不一致的路由。

### 4.2 BGP peer/group/AF

模型先保存原始配置作用域，转换时才计算 IPv4 peer 的有效属性。成员显式属性覆盖 group，
同一属性的 AF 配置覆盖基础配置；group 不跨 VRF 或地址族串用。显式禁用必须保留为状态，
不能与“未配置、需要继承”混淆。

IPv4 peer 默认激活行为和 `undo peer ... enable` 都影响是否生成 VI session。
VPN instance IPv4 peer 可以没有显式 `enable`；不能按照 H3C 的要求漏掉这些邻居。
[Huawei PE/CE 配置示例](https://support.huawei.com/enterprise/en/doc/EDOC1100419273/5c2f798f)

`preference external internal local` 是路由管理优先级，不能与 `local-preference` 路径属性
混淆。R2 中的 `33 33 33`、`2 2 2` 必须按作用域转换，而不是统一硬编码为缺省值。
IPv6/EVPN transport 与 IPv4 unicast AF 分离；不能为不可表达的会话伪造 IPv4 邻居。
`link-state-family` 也必须独立：在 BGP-LS 中启用某个 peer，不能撤销它在 IPv4 AF 中的禁用。

无显式 router ID 时优先选最大 LoopBack IPv4 地址，否则选所有接口的最大 IPv4 地址。
BGP direct/static 重分发支持 `med` 和 route-policy；普通重分发排除 `0.0.0.0/0`，
`default-route imported` 显式允许导入已存在的默认路由（支持 undo）。显式
`network 0.0.0.0 0` 独立生效。源协议进程筛选、route-filter、exclude vlink 等不可准确
模拟的形式保留、告警并省略；未知、缺值或重复修饰参数产生解析告警，不静默转换。

`allow-as-loop` 目前映射为 VI 的允许本 AS 标志，不能执行精确 AS 出现次数上限；配置计数
会产生 BGP 能力限制提示，不能据此宣称精确计数保真。

### 4.3 Route-policy

节点按编号升序检查；首个匹配节点决定 permit/deny；没有节点匹配时拒绝。不同类型的
`if-match` 是 AND，同类型条件是 OR。permit 节点命中后才执行 apply action。
列表自己的 permit/deny 和顺序仍需保留；引用列表并不意味着所有条目都放行。
标准 community-filter 的一条规则若列出多个值，要求路由同时携带这些值；不同规则按
index 顺序匹配。这与同一 node 中不同 `if-match community-filter` 条件之间的 OR 不同。
[Huawei 路由策略命令参考](https://info.support.huawei.com/enterprise/en/doc/EDOC1100420140/26892fde/routing-policy-configuration-commands)

如果 VI 不能准确判断某个条件，例如 IPv6 next-hop，就以 FALSE guard 保守处理并提示。
不能删掉条件后把整个节点变成无条件 permit。community 替换与 additive 也必须分开测试。
当前 community/extcommunity 列表支持基础精确值及其顺序语义；advanced 正则列表保留并
将对应匹配置为 FALSE、产生告警，不把厂商正则直接套用为另一种匹配语言。一个节点中的多个 community/color
动作顺序组合，后面的动作不得意外恢复前面已被替换的属性。

### 4.4 EVPN 与告警

EVPN instance、bridge-domain、EVPL、RD/RT、locator/opcode、接口绑定保留在厂商对象。
可确定的 L3 VRF RD 可以进入 VI；其余信息不自动变成 VXLAN 或跨 VRF 转发。

限制提示按能力类别汇总：ISIS 选择、IPv6、EVPN/MPLS/SRv6、策略保守处理、OSPF、BGP
运行态限制。普通 VRF 本身不触发 EVPN 限制告警。`PASSED` 只说明配置已正确识别和提取，
仍需查看 `initIssues()` 中明确列出的转换边界。

手动 API 回归验证 Huawei IPv4 peer 的精确数量、会话答案中可见的地址族，以及 VNI、L3 VNI
和 EVPN RIB 为空。生产 raw/unit 测试另外直接验证每个 VI peer 的 EVPN address family 为
`null`、每个 VRF 的 leak config 为 `null`。API 空表本身不能单独证明没有虚构 IPv4 peer 或
VRF leak，必须与这些数量和 VI 断言共同使用。

## 5. 合成配置与 Python 示例

以下配置不来自真实设备，不包含私有认证信息：

```text
#BATFISH_FORMAT: huawei_vrp
sysname vrp-lab
ip vpn-instance blue
 ipv4-family
  route-distinguisher 65000:1
#
interface GigabitEthernet0/0/1
 undo shutdown
 ip binding vpn-instance blue
 ip address 192.0.2.1 30
#
bgp 65001
 router-id 192.0.2.1
 ipv4-family vpn-instance blue
  peer 192.0.2.2 as-number 65002
  peer 192.0.2.2 route-policy EXPORT export
  import-route static
#
route-policy EXPORT permit node 10
 apply cost 77
 apply community 65000:77 additive
#
ip route-static vpn-instance blue 203.0.113.0 24 NULL0
return
```

放入 `snapshot/configs/vrp-lab`，按照[部署指南](../deployment-guide.md)启动最新源码服务后：

```python
from pybatfish.client.session import Session

bf = Session(host="127.0.0.1", port=19998)
bf.set_network("vrp-lab")
bf.init_snapshot("snapshot", name="initial")
print(bf.q.fileParseStatus().answer().frame())
print(bf.q.initIssues().answer().frame())
print(bf.q.interfaceProperties().answer().frame())
print(bf.q.bgpPeerConfiguration().answer().frame())
print(bf.q.routes(vrfs="blue").answer().frame())
```

只有一个节点时，对端不在快照中，BGP 未建立是预期结果，不等于解析失败。

## 6. 自动测试和真实配置门禁

从仓库根执行；Bazelisk 会使用 [`.bazelversion`](../../../.bazelversion) 指定的 9.2.0：

```bash
bazel test //projects/batfish/src/test/java/org/batfish/vendor/huawei/grammar:all --test_output=errors
bazel test //projects/batfish/src/test/java/org/batfish/vendor/h3c/grammar:all --test_output=errors
bazel test //projects/common/... --test_output=errors
bazel test //projects/batfish/... --test_output=errors
bazel test //... --test_output=errors
```

真实文件是可选的本地 classpath 资源，缺失时仅跳过 raw-capture 测试；文件存在但解析失败
不能跳过。公开 fixture 始终使用合成输入。原始字节直接进入生产快照链路，不复制或预清洗
成第二份测试配置。[私有样本约定](../../configuration/README.md)

| R2 厂商模型对象 | 验收数量 |
| --- | ---: |
| 接口 | 263 |
| VPN instance | 57 |
| ISIS / BGP 顶层 stanza | 2 / 1 |
| Route-policy / node | 27 / 51 |
| EVPN instance | 15 |
| Bridge-domain / EVPL | 5 / 2 |
| SRv6 locator | 2 |
| IPv4 static 配置条目 | 13 |

这些是配置对象数量，不是已安装路由或已建立邻接数量。路由下一跳是否可达、协议对端是否
存在以及接口启停都会影响最终 RIB。

R2 的 IPv4 邻居核对：全局 30 个基础 peer 中 3 个在 IPv4 AF 禁用，余下 27 个，加上 VPN
IPv4 的 16 个，共 43 个有效配置。其中 3 个显式源接口没有 IPv4 地址，保守省略并汇总提示，
最终 VI 为 40 个邻居。这与 IPv6、BGP-LS、EVPN AF 的启用状态无关。
VI 的 VRF 数为 59：57 个普通 VPN instance、default，以及由 `ip dcn vpn-instance`
声明的管理 VRF；后者单独记录，不虚构 DCN 动态地址。
13 条 IPv4 static 配置的 preference 为：默认 60 共 10 条，120、123、125 各 1 条；
不能要求它们在缺少所有对端的快照中全部进入 RIB。

## 7. 可重复运行的手动 API 回归

[huawei_manual_test.py](../examples/huawei_manual_test.py) 使用 Pybatfish，创建新的 network 和
快照，执行 R2 单节点、R1+R2、Huawei eBGP/iBGP 及 H3C–Huawei 混合双节点测试。
检查接口、VRF、告警白名单、ISIS、BGP、connected/static、NULL0、next-hop VRF、策略
属性和 EVPN 不虚构边界。合成场景同时检查 static 缺省 preference 60、显式 preference 75
以及后者经 BGP 学习后的 255；R2 单节点检查 40 个 IPv4 peer、3 个无可用源地址的省略摘要，
以及 40 行 `NOT_COMPATIBLE` 会话，双真实节点场景只报告会话而不要求外部对端建立。
每一步输出 JSON 摘要，最后生成 `steps.json`。

本次验证的实际结果与已知边界见[回归记录](../huawei-regression-results.md)。

先启动仅监听本机的独立服务，状态目录必须位于仓库之外：

```bash
bazel build //projects/allinone:allinone_main
vrp_test_root=$(mktemp -d /tmp/vrp-manual.XXXXXX)
bazel-bin/projects/allinone/allinone_main -runclient false -loglevel error \
  -coordinatorargs "-workbindhost 127.0.0.1 -workv2port 19998 \
  -templatedirs $(pwd)/questions -containerslocation $vrp_test_root/state -loglevel error"
```

另一个终端使用已有 Pybatfish 环境运行；输出目录必须尚不存在：

```bash
python docs/development-guide/examples/huawei_manual_test.py \
  --port 19998 --output /tmp/vrp-my-test-results

# 没有授权的 R1/R2 私有样本时，仅运行合成场景
python docs/development-guide/examples/huawei_manual_test.py \
  --port 19998 --output /tmp/vrp-my-synthetic-results --synthetic-only
```

结束后在启动服务的终端按 Ctrl-C，并检查 `lsof -nP -iTCP:19998 -sTCP:LISTEN` 无监听。
不要终止其他端口的服务。状态目录、原始快照副本和查询 JSON 可能包含私有网络信息，
不要上传；脚本不会输出认证字段或原始 `initIssues` 文本。

## 8. 如何扩展一条语法

1. 从官方命令手册确认视图、参数、缺省值及 `undo` 行为，编写最小合成失败测试。
2. 扩展对应功能 grammar/语义校验，确保相邻命令和嵌套视图不被吞掉。
3. 将配置写入 Huawei 厂商模型，并记录源行、结构定义和引用；不要直接写 VI。
4. 只有在 VI 能准确表达时才添加转换；否则保留配置、汇总限制，并补“不虚构对象”测试。
5. 分别验证 extraction、conversion、数据面或策略行为，然后重跑真实 R2 与 H3C 回归。
6. 同步本页支持矩阵、[模块索引](README.md)和[新增厂商流程](../new-vendor-development.md)。

本地配置解析和合成协议测试不替代真实设备 RIB/FIB 对照；本阶段没有在线登录设备或宣称
支持 MPLS/SRv6 EVPN 转发。
