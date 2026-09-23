# common 模块

## 职责

[`projects/common`](../../../projects/common) 是跨模块契约层，包含：

- `org.batfish.datamodel`：厂商无关配置、协议、路由、ACL、flow、answer 等对象；
- `org.batfish.common`：日志、常量、WorkItem、NetworkSnapshot 和公共工具；
- `org.batfish.common.plugin`：`IBatfish`、PluginConsumer、Question/DataPlane 插件接口；
- `org.batfish.storage`：持久化接口和默认文件实现；
- `org.batfish.specifier`：node/interface/IP/filter/location 等选择语言；
- 公共 parser 基类、BDD 编码工具和拓扑类型。

它是其他模块的公共语言，不应依赖 coordinator resource 或某个具体 vendor parser。

## 模型数据流

```text
VendorConfiguration（抽象契约）
 → Configuration
    ├─ Vrf → protocol process / route policies
    ├─ Interface → address / ACL / transformation
    ├─ IpAccessList / IpSpace
    └─ vendor family metadata
 → DataPlane interface / Topology / Flow
 → AnswerElement / TableAnswerElement
 → Jackson JSON → REST/Pybatfish
```

[`Configuration`](../../../projects/common/src/main/java/org/batfish/datamodel/Configuration.java) 是
单个逻辑节点的 VI 根对象；[`NetworkSnapshot`](../../../projects/common/src/main/java/org/batfish/common/NetworkSnapshot.java)
仅保存 network/snapshot ID，不承载整个模型。

## 设计原理

### 不可变值对象

IP、Prefix、SubRange、route 属性等大量类型作为 map key、cache value 或 BDD 输入使用，
`equals/hashCode/compareTo` 是算法契约。新增字段时必须决定：

- 是否参与相等性和排序；
- JSON 是否必填、默认或可空；
- 是否可序列化跨版本读取；
- builder/toBuilder 是否保留；
- 是否影响 route preference/FIB 行为。

### 插件反转依赖

[`IBatfish`](../../../projects/common/src/main/java/org/batfish/common/plugin/IBatfish.java) 为 Answerer
提供加载配置、dataplane、specifier context、traceroute 等能力。问题模块只依赖接口；核心模块
实现它。这样 question 不需了解 storage/cache/job 细节。

### 存储契约

[`StorageProvider`](../../../projects/common/src/main/java/org/batfish/storage/StorageProvider.java) 使用
NetworkId/SnapshotId/AnswerId 等类型而非用户路径；
[`FileBasedStorage`](../../../projects/common/src/main/java/org/batfish/storage/FileBasedStorage.java)
负责具体目录、压缩与对象序列化。

### Specifier

specifier 把 `/regex/`、集合运算和 `@function(...)` 解析为 AST，再针对 `SpecifierContext`
解析成节点、接口、位置或 IP 空间。问题参数应尽量复用它，避免每个 Answerer 发明筛选语法。

## 示例：构造统一模型对象

```java
Configuration c =
    Configuration.builder()
        .setHostname("r1")
        .setConfigurationFormat(ConfigurationFormat.CISCO_IOS)
        .build();

Vrf vrf = Vrf.builder().setName(Configuration.DEFAULT_VRF_NAME).setOwner(c).build();
Interface.builder()
    .setName("Loopback0")
    .setOwner(c)
    .setVrf(vrf)
    .setAddress(ConcreteInterfaceAddress.parse("192.0.2.1/32"))
    .build();
```

具体 builder signature 以当前类为准；生产转换还需设置接口类型、active 状态、依赖和厂商默认。
测试中优先使用现有 `NetworkFactory`/builder helper，避免漏掉不变量。

## 示例：通过 IBatfish 编写 Answerer

```java
public AnswerElement answer(NetworkSnapshot snapshot) {
  SortedMap<String, Configuration> configs = _batfish.loadConfigurations(snapshot);
  // 只依赖公共 Configuration，而不是某个 vendor representation。
  return toTable(configs);
}
```

`Answerer` 基类位于
[`Answerer.java`](../../../projects/common/src/main/java/org/batfish/common/Answerer.java)。若需要新增
`IBatfish` 方法，先确认该能力适合所有问题且不会泄漏核心内部状态。

## 构建与测试

```bash
bazel build //projects/common:common
bazel test //projects/common/...
```

公共模型改动的风险面大，除本模块测试外，应运行使用者模块；路由/ACL/flow 类型变化通常至少
覆盖 `batfish` 和 `question`。

## 修改注意事项

- 不把厂商专有 enum/字段加入通用类，除非分析算法确实需要统一表达。
- Jackson property 改名可能破坏已存 snapshot/answer 和 Pybatfish。
- `@Nullable` 是契约，不应以“当前调用方不传 null”为由删除。
- 大集合对象进入 cache 前考虑序列化体积与不变性。
- 公共常量注释要求同步 Python/JavaScript client 时，必须跨仓库协调。
