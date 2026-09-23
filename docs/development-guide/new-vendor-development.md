# 新增未适配厂商的开发流程

本流程描述把一个全新的网络操作系统接入 Batfish 的完整路径。新增厂商不是“写一个
ANTLR grammar”即可：成功标准是配置能被可靠检测、语义进入厂商模型、正确转换到统一模型、
在数据平面和问题中产生与真实设备一致的行为，并且未知语法不会静默改变语义。

更长的教学示例和 CoolNOS 脚手架分别位于
[`docs/tutorials/adding_vendor_support.md`](../tutorials/adding_vendor_support.md) 和
[`docs/example_code/new_vendor`](../example_code/new_vendor)。本文强调开发门禁和文件落点。

## 1. 先定义范围与证据

已落地案例：[H3C Comware 7 / CR16000](modules/h3c-comware.md)。该案例展示原始 CLI 采集清洗、
按缩进构建视图树、保留不可转换配置、基于真实字节资源的生产快照回归，以及双节点协议测试。
其 195 个接口和 26 个策略节点的计数说明：先去除分页覆盖再统计，不能只对原文 grep 顶格命令。
两份真实采集文件的原样保留是项目所有者明确批准的个案例外，不应作为其他 fixture 的默认做法。

在写代码前建立厂商特性说明，至少记录：

- OS/固件版本与硬件/虚拟平台；
- 配置的所有合法形态：层次化、扁平化、submode、混合输入；
- 注释、转义、引号、换行和 identifier 规则；
- `set/delete/insert/replace` 等编辑动词；
- 模板、groups、profiles、继承及优先级；
- list 的顺序语义与重复语句处理；
- 未配置字段的默认值；
- 接口、VRF、ACL、NAT、静态路由和协议的语义；
- 可用于真实设备对照的结构化 show/state 输出；
- 许可情况：厂商 schema、配置和手册能否提交。

优先使用可机器读取的 YANG/OpenConfig/schema 作为默认值、key 和 ordering 的证据；私有
schema 放在未跟踪目录，不能提交到公开仓库。配置样例必须脱敏且保留触发语义所需的结构。

## 2. 选择参考实现

按**配置形态**而不是品牌相似度选择：

- 行式/submode：优先研究 Cisco NX-OS/Cisco parser。
- brace 层次化：研究 Junos、Palo Alto nested、Nokia SR OS 的 flatten/statement tree。
- 继承/模板：研究 Junos groups 或 NX-OS BGP peer templates。
- 多文件设备：研究 Cumulus concatenated 与 FRR 组合。
- 结构化 JSON/cloud：研究 AWS/Azure 和 F5 structured 的数据入口。

## 3. 建立纵向最小切片

不要先实现几千条 grammar 再转换。用一个最小配置走通全部阶段：

```text
hostname + 一个启用接口 + 一个地址
  → DETECTED
  → parse tree 无错误
  → VendorConfiguration
  → VI Configuration
  → fileParseStatus/initIssues
  → nodeProperties/interfaceProperties 可见
```

然后按 interface → static route → OSPF → eBGP → iBGP → policy → ACL/NAT 的复杂度阶梯
迭代。每个阶梯都补 parse、conversion 和端到端行为测试。

## 4. 注册配置格式

### 4.1 枚举

在
[`ConfigurationFormat.java`](../../projects/common/src/main/java/org/batfish/datamodel/ConfigurationFormat.java)
增加稳定枚举值：

```java
ACME_NOS("acme_nos"),
```

`vendorString` 用于展示/序列化兼容，不应随营销名称轻易变更。

### 4.2 检测器

在
[`VendorConfigurationFormatDetector.java`](../../projects/batfish/src/main/java/org/batfish/grammar/VendorConfigurationFormatDetector.java)
加入基于厂商唯一标头/版本行的检测：

```java
private static final Tell ACME_NOS_PATTERN =
    Tell.of("(?m)^! ACME NOS version [0-9.]+$", "! ACME NOS version ");

private @Nullable ConfigurationFormat checkAcmeNos() {
  return fileTextMatches(ACME_NOS_PATTERN) ? ConfigurationFormat.ACME_NOS : null;
}
```

在 `identifyConfigurationFormat()` 的正确位置调用。顺序很重要：应放在可能误判它的通用
Cisco/Juniper heuristic 之前，但不要让宽泛规则抢走其他厂商。

在
[`VendorConfigurationFormatDetectorTest`](../../projects/batfish/src/test/java/org/batfish/grammar/VendorConfigurationFormatDetectorTest.java)
添加：真实标头、最小配置、相似厂商负例、空白/BOM/换行变体、显式
`BATFISH_FORMAT`（如适用）测试。

解析器尚未实现时，先将枚举加入 `ParseVendorConfigurationJob` 的未实现集合，使输入得到
确定的 `UNSUPPORTED`，而不是错误识别成其他厂商；解析接通后再移除。

## 5. 创建目录和 Bazel 目标

推荐 vendor-scoped 布局：

```text
projects/batfish/src/main/antlr4/org/batfish/vendor/acme_nos/grammar/
  AcmeNosLexer.g4
  AcmeNosParser.g4
  AcmeNos_common.g4
  BUILD.bazel
projects/batfish/src/main/java/org/batfish/vendor/acme_nos/
  grammar/
    AcmeNosBaseLexer.java
    AcmeNosCombinedParser.java
    AcmeNosControlPlaneExtractor.java
    AcmeNosConfigurationBuilder.java
    BUILD.bazel
  representation/
    AcmeNosConfiguration.java
    AcmeNosConversions.java
    Interface.java
    StaticRoute.java
    BUILD.bazel
projects/batfish/src/test/java/org/batfish/vendor/acme_nos/grammar/
  AcmeNosGrammarTest.java
  BUILD.bazel
projects/batfish/src/test/resources/org/batfish/vendor/acme_nos/grammar/testconfigs/
  BUILD.bazel
  minimal.conf
```

从 [`docs/example_code/new_vendor`](../example_code/new_vendor) 复制结构时，逐项改名并重新核对
`deps`，不要保留示例 vendor 名或过宽 visibility。

## 6. Lexer 与 parser

### 6.1 Lexer 原则

- newline 通常有语义，不要无条件丢弃；
- 关键字优先于通用 identifier；
- 为 interface name、IPv4/IPv6、prefix、uint 等复用公共 fragment；
- 用 mode 隔离 banner、certificate、description 或自由文本区域；
- 未识别行应产生可见 warning，不能用 `.*` 静默吞掉；
- 只在 grammar 表达句法，不在 action 中构建最终 VI 对象。

```antlr
lexer grammar AcmeNosLexer;

HOSTNAME: 'hostname';
INTERFACE: 'interface';
IP: 'ip';
ADDRESS: 'address';
NEWLINE: '\r'? '\n';
WS: [ \t]+ -> channel(HIDDEN);
WORD: ~[ \t\r\n]+;
```

实际 lexer 应使用仓库约定的基类、newline 恢复和错误监听；示例仅表达分词边界。

### 6.2 Parser 原则

将顶层 grammar 拆成按功能命名的 imported grammar：system、interfaces、static route、BGP、
policy 等。这样增量支持和测试定位更清晰。

```antlr
parser grammar AcmeNosParser;

options { tokenVocab = AcmeNosLexer; }

configuration: statement* EOF;
statement
  : hostname_statement
  | interface_statement
  | unrecognized_statement
  ;
hostname_statement: HOSTNAME WORD NEWLINE;
```

`unrecognized_statement` 必须与 warning 机制配合，且范围足够窄，避免吞掉后续合法 stanza。
遵循 [`parser_rule_conventions`](../parsing/parser_rule_conventions.md) 和
[`lexer_mode_patterns`](../parsing/lexer_mode_patterns.md)。

## 7. 厂商专用表示模型

提取目标是 `AcmeNosConfiguration extends VendorConfiguration`，不是直接写
VI `Configuration`。厂商模型应保留：

- 厂商的名字空间、默认值和继承结果；
- 源行与结构定义/引用，用于 warning 和 undefined reference；
- 之后转换所需但 VI 模型没有直接等价物的上下文；
- 配置顺序（当顺序影响语义）。

示意：

```java
public final class AcmeNosConfiguration extends VendorConfiguration {
  private String _hostname;
  private final Map<String, AcmeNosInterface> _interfaces = new TreeMap<>();

  @Override
  public List<Configuration> toVendorIndependentConfigurations() {
    Configuration c = new Configuration(_hostname, ConfigurationFormat.ACME_NOS);
    _interfaces.values().forEach(iface -> AcmeNosConversions.convertInterface(iface, c));
    return ImmutableList.of(c);
  }
}
```

真实代码还需设置 vendor family、默认 cross-zone/inbound action、device model、warnings 和
结构引用。参考相近厂商，不要凭直觉复制默认值。

## 8. Extractor / builder

combined parser 封装 ANTLR lexer/parser；control-plane extractor 暴露 parse tree、warnings
和 vendor configuration；builder 监听或访问 parse tree 并填充厂商模型。

职责分配：

- parser：这段文本能否组成合法语句；
- builder：语句定义/修改了哪个厂商对象；
- representation：厂商对象的状态与默认语义；
- conversion：如何映射到 VI 模型；
- post-processing：需要网络全局信息的派生关系。

遇到未知引用时先记录名称和源行，转换阶段再解析；这样才能报告“定义缺失”而不是在提取时
丢失语义。

## 9. 接入 ParseVendorConfigurationJob

在
[`ParseVendorConfigurationJob`](../../projects/batfish/src/main/java/org/batfish/job/ParseVendorConfigurationJob.java)
的 format switch 中创建 parser、extractor，并配置是否支持 parse tree 输出、是否需要 flatten。
同时更新相应 `BUILD.bazel` 依赖，移除未实现集合里的枚举。

门禁测试应证明：

```java
@Test
public void testMinimalConfigParses() {
  String hostname = parseVendorConfig("minimal.conf").getHostname();
  assertThat(hostname, equalTo("r1"));
}
```

测试 helper 名称以相近 vendor 的现有测试为准；不要发明绕过 Batfish pipeline 的生产专用
helper。

## 10. 转换到统一模型

转换应复用 `projects/common` 中的统一对象：`Configuration`、`Vrf`、`Interface`、
`IpAccessList`、`RoutingPolicy`、各协议 process/neighbor 和 route 类型。

每个功能回答三件事：

1. 厂商配置中的**缺省行为**是什么；
2. 在 VI 模型中用什么对象/策略精确表达；
3. 信息不完整时是 warning、忽略该 feature，还是生成保守模型。

策略转换尤其要保留 first-match、默认 permit/reject、call/return、community/AS-path 变换和
未定义引用行为。不要为了让测试通过而默认 permit。

## 11. 分层测试策略

### 11.1 检测测试

只验证文本 → `ConfigurationFormat`，包括冲突负例。

### 11.2 Grammar/extraction 测试

验证 parse warning、厂商对象字段、结构定义/引用和行号。一个配置文件聚焦一个语法特性。

### 11.3 Conversion 测试

通过完整 parse + convert 获取 VI `Configuration`，断言接口状态、地址、VRF、ACL、policy、
process 等最终语义，而不是调用 private conversion helper。

### 11.4 Data-plane/E2E 测试

至少构造两节点或多节点拓扑，断言：

- 会话建立/不建立的原因；
- RIB 中期望路由和属性；
- FIB 下一跳与 ECMP；
- ACL/NAT 后的 traceroute；
- 错误配置下的 warning/行为。

### 11.5 真实设备验证

用固定 OS 版本和配置生成设备侧结构化状态，与 Batfish 的接口、邻居、RIB/FIB、策略结果和
flow 行为对比。测试通过只证明实现自洽，真实设备对照才验证语义。

## 12. 推荐迭代顺序

| 阶段 | 交付物 | 退出条件 |
| --- | --- | --- |
| 0 | 厂商特性说明和样例许可 | 默认值/顺序/输入形态有证据 |
| 1 | enum + detector | 正例、负例、冲突测试通过 |
| 2 | hostname/interface 最小纵切 | 初始化和 VI 查询可见 |
| 3 | 静态路由与基础 ACL | conversion + traceroute 验证 |
| 4 | IGP | 邻居、RIB、故障测试 |
| 5 | BGP 与策略 | 属性、选择、import/export 对照 |
| 6 | NAT/VPN/EVPN 等高级能力 | 专题 E2E 与真实设备对照 |
| 7 | 文档和支持矩阵 | 限制、版本与告警行为公开 |

## 13. 完成检查表

- [ ] `ConfigurationFormat` 与 detector 已接入，且有冲突负例。
- [ ] `ParseVendorConfigurationJob` 不再把格式视为未实现。
- [ ] grammar 没有宽泛静默吞行规则。
- [ ] 厂商模型与 VI 模型分层清晰。
- [ ] 定义/引用和 source line 可追踪。
- [ ] 默认值、顺序、继承和编辑动词有明确语义。
- [ ] parse、extraction、conversion、dataplane/E2E 测试齐全。
- [ ] 至少一个真实设备/仿真器版本完成行为对照。
- [ ] 根支持列表与开发文档更新，并诚实记录未支持特性。
- [ ] `bazel test` 覆盖新 vendor package 及受影响的公共模块。

## 14. 常见失败模式

- detector 太宽，导致已有厂商回归；
- grammar 接受配置但 `unrecognized` 吞掉关键 stanza；
- extractor 直接创建 VI 对象，丢失厂商语义和源信息；
- 把“字段缺失”一律解释为 permit/启用；
- 只做单文件解析测试，没有验证路由/转发行为；
- 只支持 show 输出的一种形态，忽略 flat/brace 或追加 edit 命令；
- 从另一个 vendor 复制管理距离、默认 policy、接口状态等常量；
- 只看 enum 和 parse success 就宣称平台已支持。
