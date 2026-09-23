# H3C Comware 7 / CR16000

本模块把 H3C 配置接入 Batfish 的配置解析、统一模型、路由计算和问题查询链路。第一阶段以
CR16000、Comware `7.1.075, ESS 8611` 的真实 R1 为回归样本。格式名为
`H3C_COMWARE`，vendor string 为 `h3c_comware`，设备模型为
`H3C_COMWARE_UNSPECIFIED`。配置内容没有可靠硬件标识，因此不会从文件名推断型号。

原始样本 `docs/configuration/NJ_SCT_R1` 仅本地保存；Huawei 样本
`docs/configuration/NJ-SCT-R02` 只用于格式识别反例，未在本阶段适配。
两份采集文件含真实认证材料，已从公开提交历史排除并加入 Git 忽略规则。
原始字节仍在本地保留；安装与测试方式见[私有样本说明](../../configuration/README.md)。

## 1. 支持范围

| 功能 | 提取与转换 | 第一阶段限制 |
| --- | --- | --- |
| 输入 | ICU 字符集识别、GB18030、CRCRLF/CRLF/CR、ANSI CSI、分页覆盖、设备提示符 | 非标准分页器需补充 normalizer fixture |
| 接口 | 物理口、LoopBack、VLAN、聚合与子接口；IPv4、VRF、MTU、描述、shutdown、dot1q、聚合依赖 | IPv6 地址保留；隧道封装/SR/MPLS 不模拟 |
| 二层接口 | route/bridge、access/trunk、允许 VLAN；VLAN interface 的 VLAN ID | 不包含完整二层交换特性 |
| Connected | VI 接口自动产生 IPv4 connected/local 路由 | 接口最终是否 active 由统一后处理和拓扑决定 |
| Static | IPv4 全局/VRF、IP/接口下一跳、NULL0、next-hop VRF、preference、tag、description | IPv6 与 BFD 配置保留；带显式 IP 的跨 VRF 下一跳不转换 |
| ISIS | 全部进程提取；选一个默认 VRF IPv4 进程转换；NET、L1/L2、开销、P2P、静默、持久 overload、BGP 重分发 | 多进程并行、IPv6、SR、LFA/TI-LFA 不模拟；startup-only overload 不永久开启 |
| BGP | IPv4 VRF 邻居、AS、源接口/IP、multihop、AF enable、community、策略、network、direct/static 重分发 | IPv6 邻居/AF、EVPN 会话、额外 instance 保留；timer/BFD/route-limit 不模拟；allow-as-loop 次数只能降为 VI 布尔字段 |
| 路由策略 | 节点排序、首个匹配、同类 OR/异类 AND、最终拒绝；IPv4 prefix/community/RT/SOO/color match；metric、local-pref、IPv4 next-hop、community/color action | RD、IPv6 next-hop match 为 FALSE 并汇总告警；advanced community regex、whole-match 不转换 |
| EVPN | VPN/VSI/xconnect 的 RD/RT、封装类型、locator、service ID、AC；VRF RD 转到 VI | MPLS/SRv6 EVPN 无数据面；不创建 VNI、EVPN peer 或跨 VRF leak |

`PASSED` 表示解析完成，不表示所有命令都已参与仿真。`initIssues` 中的能力边界告警仍必须检查。
尤其不能用本阶段结果证明 IPv6、SRv6、EVPN 跨 PE 可达或 ACL 安全策略正确。

## 2. 模块数据流

```text
snapshot/configs 中的原始字节
  → StreamDecoder：字符集检测和解码
  → VendorConfigurationFormatDetector：Comware ESS 特征/显式格式头
  → ParseVendorConfigurationJob：H3C 分派
  → H3cConfigurationNormalizer：清除终端控制信息，保留缩进/行号
  → H3cLexer + H3cParser：分词、逐行语句及功能分类
  → H3cStatementTree：缩进与 # 视图边界
  → H3cFeatureExtractor：上下文语义验证、厂商对象、定义与引用
  → H3cConfiguration：可序列化的厂商模型
  → H3cConversions：IPv4 VI 接口、VRF、路由、协议、RoutingPolicy
  → ConvertConfigurationJob / postProcessSnapshot：统一校验与拓扑处理
  → incremental dataplane / question：routes、BGP session、策略测试等
```

源代码入口：

- [normalizer、parser、statement tree、extractor](../../../projects/batfish/src/main/java/org/batfish/vendor/h3c/grammar/)
- [ANTLR grammar](../../../projects/batfish/src/main/antlr4/org/batfish/vendor/h3c/grammar/)
- [厂商模型和转换](../../../projects/batfish/src/main/java/org/batfish/vendor/h3c/representation/)
- [测试](../../../projects/batfish/src/test/java/org/batfish/vendor/h3c/grammar/)
- [格式检测](../../../projects/batfish/src/main/java/org/batfish/grammar/VendorConfigurationFormatDetector.java)
- [生产解析分派](../../../projects/batfish/src/main/java/org/batfish/job/ParseVendorConfigurationJob.java)

## 3. 输入归一化与视图树原理

R1 的分页序列包含 `---- More ----`、连续回车、擦除用空格和回车。回车此时表示光标回到
行首，不能直接当作新配置行。normalizer 先清除 ANSI 和完整分页覆盖序列，再统一换行，
最后把提示符、残留命令、纯空白行替换为空行。保留下来的空行保证后续诊断行号不会前移。
`Result.originalLine()` 返回归一化行的原始逻辑行号；CRCRLF 算一个换行。

行首空白由 `INDENT` token 保留；行内空白进入 hidden channel。grammar 按接口、VPN、
static、ISIS、BGP、策略、EVPN 拆分。语句参数和视图是否合法由 extractor 验证：grammar
接受一行 token 不等于该命令已获得语义支持。

例如：

```text
bgp 65000
 ip vpn-instance blue
  peer 192.0.2.2 as-number 65001
  #
  address-family ipv4 unicast
   peer 192.0.2.2 enable
 #
 address-family l2vpn evpn
  peer 2001:db8::2 enable
#
```

缩进为 2 的 `#` 只结束当前 peer 所处的子级；缩进为 1 的 `#` 回到 BGP 视图；顶格 `#`
结束 BGP。使用栈弹出缩进大于等于当前行的节点，避免把后续 VPN 的 AF 误挂到前一个 VPN。

目标视图中的未知语句置 `VendorConfiguration.unrecognized=true` 并记录行号。
非目标 view 通过明确白名单进入 `SilentSyntaxCollection`。诊断只记录命令头和行号，避免把
认证参数等原始值复制到日志。目标语法错误不能通过扩充全局忽略规则解决。

## 4. 厂商对象与转换原理

`H3cConfiguration` 是对象图的根。`H3cModel` 中保存接口、VPN/AF、static、ISIS、
BGP/VRF/peer、policy/node 和 EVPN 对象。暂不能转换的配置保留为带行号的
`H3cStatement`，包含完整子树，例如 SRv6 locator/opcode、IPv6 static 和 operational
BGP 参数。这些对象经过生产序列化/反序列化回归验证。

### 接口、VRF 与静态路由

接口先创建到所属 VI VRF；子接口建立到父接口的 BIND 依赖，聚合口建立到物理成员的
AGGREGATE 依赖。VLAN interface 必须填写 VI `vlan`，bridge 口必须填写匹配的
`SwitchportMode`，否则统一转换校验会删除该接口。connected/local 不在厂商转换中手工造路由，
而是由 dataplane 从 active 接口地址生成。

静态下一跳映射：

| Comware | VI |
| --- | --- |
| `... 192.0.2.2` | `NextHopIp` |
| `... GigabitEthernet1/0/1 192.0.2.2` | `NextHopInterface`，包含 ARP IP |
| `... NULL0` | `NextHopDiscard` |
| `... vpn-instance blue` | `NextHopVrf` |

H3C 默认 administrative cost：connected/local `0`、static `60`、ISIS `15`、
eBGP/iBGP `255`、BGP 本地起源 `130`。显式 static preference 优先。

### ISIS 进程选择

现有 VI 每个 VRF 只有一个 ISIS process。候选进程按默认 VRF 中有 IPv4 地址并启用该
ISIS 进程的接口数排序，数量相同选最小进程号；R1 选中 `10`。未选中的进程仍保留，
通过一条告警列出。LoopBack 默认转 passive，普通口默认 active，未配置开销为 `10`。

`set-overload on-startup` 仅表示启动期状态，静态快照不能把它解释成永久 overload。
BGP 重分发通过生成的 ISIS export policy 实现，route-policy 的 metric 在默认值之后生效。

### BGP 和路由策略

同一 BGP instance 内按 VRF 建立进程；IPv4 AF 下 `peer ... enable` 决定是否建立对应 VI peer。
`connect-interface` 解析到同 VRF 的源接口 IPv4 地址。没有显式 source 时由现有拓扑逻辑
选择源 IP；显式引用不存在的源接口时跳过 peer 并告警。

生成的 export policy 从 main RIB 处理路由：已有 BGP/iBGP 路由、匹配 `network` 的路由、
匹配 direct/static 重分发的路由，再经过邻居 export route-policy。`network` 起源为 IGP，
重分发起源为 INCOMPLETE。`substitute-as` 转为出口 AS 替换语句。

route-policy 节点按数字升序执行；首个匹配节点决定 permit/deny。permit 节点应用属性再
返回，deny 节点不应用属性。未匹配任何节点时拒绝。无 `if-match` 的节点匹配所有路由。
不存在的 prefix/community list 按本阶段依据的 H3C 语义视为匹配，但引用跟踪仍报告
undefined structure，不能把该语义推广为“未知命令也匹配”。

prefix/community/extcommunity 列表均按显式 index 升序求值；省略 index 时使用当前最大值加 10，
相同 index 替换对应条目。数字 `100..199` 的标准 community list 属于 advanced 类型，
不能当作 basic 值解析。`whole-match` 当前保守禁用整个策略节点并告警；不会误把该关键字
当作未定义列表，从而意外匹配所有路由。RT 与 SOO 使用不同的 extended-community subtype。

社区通过统一 `CommunitySet` 运算实现。非 additive 标准社区只替换标准社区，保留 RT；
非 additive color 只替换 color，保留其他 extended/standard 社区。不能求值的 RD/IPv6
next-hop guard 使用 FALSE；存在未知或格式错误操作的策略节点禁用，避免错误放行。

### EVPN 边界

VPN IPv4 AF RD 优先于实例 RD，写入 VI VRF。RT、VSI MPLS/SRv6 封装、xconnect service ID、
attachment circuit、locator/opcode 均保留供后续开发检查。当前 VI 的 EVPN 与 VXLAN/VNI
紧密相关，不能把 H3C MPLS/SRv6 服务 ID 当作 VNI；因此不生成 L2/L3 VNI、EVPN 邻居或
依赖 VNI 的 VRF leaking 配置。

## 5. 配置与客户端示例

最小配置：

```text
#BATFISH_FORMAT: h3c_comware
sysname demo-r1
interface LoopBack0
 ip address 10.0.0.1 32
#
interface GigabitEthernet1/0/1
 ip address 192.0.2.1 30
#
bgp 65000
 peer 192.0.2.2 as-number 65001
 address-family ipv4 unicast
  peer 192.0.2.2 enable
  import-route direct
  import-route static
#
ip route-static 203.0.113.0 24 NULL0
```

必须运行包含本次修改的服务端构建；上游旧 Docker 镜像不会因升级 Pybatfish 自动获得此 parser。
编译与服务启动参见[部署文档](../deployment-guide.md)。本机编译：

```bash
bazel build //projects/allinone:allinone_main
```

下面在临时 snapshot 中复制原始字节，只导入 R1；不会把尚未适配的 Huawei 配置一起加入。
运行位置为仓库根目录：

```python
from pathlib import Path
from tempfile import TemporaryDirectory
from shutil import copyfile
from pybatfish.client.session import Session

bf = Session(host="localhost")
bf.set_network("h3c-cr16000")
with TemporaryDirectory(prefix="h3c-snapshot-") as directory:
    root = Path(directory)
    (root / "configs").mkdir()
    copyfile("docs/configuration/NJ_SCT_R1", root / "configs" / "r1")
    bf.init_snapshot(root, name="r1-phase1", overwrite=True)

print(bf.q.fileParseStatus().answer().frame())
print(bf.q.initIssues().answer().frame())
print(bf.q.interfaceProperties(nodes="nj-sct-r01").answer().frame())
print(bf.q.routes(nodes="nj-sct-r01").answer().frame())
print(bf.q.bgpSessionStatus(nodes="nj-sct-r01").answer().frame())
```

仅导入一台设备不会建立跨节点邻接；上述 BGP 状态不能用于判断真实邻居是否故障。
多节点测试需导入双方配置和必要的 layer1/runtime 数据。Python 的路由策略输入示例见
[客户端手册](../python-client-guide.md)，行为测试见 `H3cPolicyTest`。

## 6. 验证与后续开发

真实原文回归核对：195 接口、41 VPN、4 ISIS、2 BGP stanza、26 route-policy node、
10 VSI、4 xconnect、16 IPv4 static、9 IPv6 static。最初计划的 185 接口/24 策略节点
遗漏了分页符后面的行，修正过程见[实现记录](../h3c-implementation-status.md)。

真实 R1 回归严格检查六类汇总告警：ISIS 进程选择、IPv6 不转换、EVPN/MPLS/SRv6 不转换、
RD/IPv6 next-hop 策略 guard、额外 BGP instance、BGP operational 参数限制。
同时断言不存在伪造的 VNI 和 EVPN address-family。测试日志不复制原始配置值。
公开仓库不附带真实样本：对应文件缺失时，两个真实配置用例明确显示为 skipped；
安装本地样本后执行全部断言。合成测试不依赖私有文件，始终运行。

```bash
# 原始配置、normalizer、策略、接口转换、双节点 ISIS/eBGP/iBGP
bazel test //projects/batfish/src/test/java/org/batfish/vendor/h3c/grammar:tests --test_output=errors

# 格式检测、字符集解码及通用解析任务
bazel test //projects/batfish/src/test/java:batfish_tests \
  --test_filter='org.batfish.grammar.VendorConfigurationFormatDetectorTest|org.batfish.main.StreamDecoderTest|org.batfish.job.ParseVendorConfigurationJobTest' \
  --test_output=errors

# 扩大回归
bazel test //projects/batfish/... --test_output=errors
bazel test //... --test_output=errors
```

新增目标命令的顺序：补小型失败 fixture → 对应 grammar 分类 → extractor 参数验证与字段提取 →
structure 定义/引用 → 能力转换或明确保留告警 → VI 属性/真实路由行为断言 → 原始 R1 回归。
未知语句导致 `PARTIALLY_UNRECOGNIZED` 时，先定位所属视图；不要为了 `PASSED` 放宽目标视图
的忽略范围。后续 IPv6、多 ISIS、SRv6 EVPN 工作需要扩展公共模型和数据面，是独立阶段。

## 7. 参考资料

- [H3C CR16000 路由配置指南](https://www.h3c.com/en/Support/Resource_Center/EN/Routers/Catalog/CR16000-M/CR16000-M/Technical_Documents/Configure___Deploy/Configuration_Guides/H3C_CG-16822/06/)
- [H3C 路由策略说明](https://www.h3c.com/en/Support/Resource_Center/EN/Routers/Catalog/CR16000-M/CR16000-M/Technical_Documents/Configure___Deploy/Configuration_Guides/CR16000-M_CG-R838x/06/202403/2079257_294551_0.htm)
- [H3C EVPN/SRv6 配置指南](https://www.h3c.com/en/Support/Resource_Center/EN/Routers/Catalog/CR16000-M/CR16000-M/Technical_Documents/Configure___Deploy/Configuration_Guides/H3C_CG-29315/10/202510/2664486_294551_0.htm)
- [H3C 路由策略命令参考：列表索引及 advanced 编号](https://www.h3c.com/en/Support/Resource_Center/EN/Home/Public/00-Public/Technical_Documents/Reference_Guides/Command_References/H3C_CR-30059/15/202511/2698565_294551_0.htm)

不同指南对应的发布版本并不完全相同；生产语义仍应以实际 ESS 版本及真实设备输出校验。
