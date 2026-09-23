# Batfish 开发指南

本文档面向准备阅读、构建、调试或扩展 Batfish 的开发者。内容以本仓库当前
checkout 为准：Batfish `0.36.0`（见 [`projects/VERSION`](../../projects/VERSION)），
而不是对线上镜像或 Pybatfish 最新发布版的泛化描述。

## 阅读路径

1. 先读[架构与端到端数据流](architecture-and-data-flow.md)，理解快照如何变成答案。
2. 按职责进入[模块介绍](modules/README.md)，定位代码所有者和构建目标。
3. 使用[开发与部署](deployment-guide.md)启动服务，再按
   [Python 客户端手册](python-client-guide.md)提交快照和问题。
4. 要扩展平台支持时，遵循[新增厂商开发流程](new-vendor-development.md)。
5. 用 [Codebase 源码导航](source-reference.md)从功能跳到实现、测试和构建目标。
6. 已有专题资料仍以 [`docs/README.md`](../README.md) 为入口；本目录侧重把分散资料
   与当前源码连接起来，而不替代算法专题文档。

## Batfish 是什么

Batfish 是一个**离线网络配置分析与验证引擎**。它不需要登录设备；输入是设备配置、
云平台对象以及可选的拓扑、路由和运行状态补充数据。系统将厂商配置归一化为统一的
Java 数据模型，计算路由与转发表，再通过问题插件回答配置合规、连通性、安全性、
可靠性和变更影响等问题。

主要能力包括：

- 配置质量：解析状态、未定义/未使用结构、转换警告、接口与协议属性。
- 拓扑与会话：L1/L2/L3、BGP、OSPF、EIGRP、ISIS、IPsec、VXLAN/EVPN 边。
- 路由：RIB、LPM、路由策略测试、路由策略搜索和前缀传播。
- 转发：traceroute、双向可达性、差异可达性、环路和流处置结果。
- 策略：ACL/防火墙规则测试、不可达规则、匹配流搜索和规则等价比较。
- 变更分析：同一 network 下基线与候选 snapshot 的差异问题，以及 fork snapshot
  模拟节点/接口故障。
- 云网络：AWS、Azure 模型与传统网络配置可共同进入统一分析流程。

问题模板位于 [`questions/stable`](../../questions/stable)，Java 实现在
[`projects/question`](../../projects/question)。二者不是一一对应关系：多个模板可以
为同一个 Java `Question` 提供不同的预置参数。

## 总体架构

```text
Pybatfish / Java Client / REST caller
                |
                v
       Coordinator (REST v2 :9996)
       资源、存储、排队、状态轮询
                |
                v
       Batfish worker / Driver
                |
     +----------+-----------+
     |                      |
配置初始化流水线          问题执行流水线
检测→解析→提取→转换       Question→Answerer
→后处理→拓扑→数据平面      →表格/对象/流轨迹答案
     |                      |
     +----------+-----------+
                v
     FileBasedStorage + 内存缓存
```

本仓库的默认开发进程由 [`AllInOne`](../../projects/allinone/src/main/java/org/batfish/allinone/AllInOne.java)
在一个 JVM 中启动 coordinator、worker 和可选 Java CLI。生产式调用通常由
Pybatfish 连接 coordinator 的 REST v2 API。更详细的阶段与缓存边界见
[架构与端到端数据流](architecture-and-data-flow.md)。

## 工程模块

| 模块 | 主要职责 | 详细说明 |
| --- | --- | --- |
| `projects/allinone` | 单 JVM 组装与可执行入口 | [allinone](modules/allinone.md) |
| `projects/batfish` | 解析、转换、拓扑、数据平面、转发和任务执行核心 | [batfish-core](modules/batfish-core.md) |
| `projects/common` | 公共协议、统一数据模型、插件与存储接口 | [common](modules/common.md) |
| `projects/coordinator` | REST API、网络/快照生命周期、任务队列与持久化编排 | [coordinator](modules/coordinator.md) |
| `projects/client` | 仓库内 Java 命令行客户端；不是 Pybatfish | [client](modules/client.md) |
| `projects/question` | 标准问题、Answerer 和插件注册 | [question](modules/question.md) |
| `projects/bdd` | 仓库内 JavaBDD 实现 | [bdd](modules/bdd.md) |
| `projects/symbolic` | 符号转发状态表达式 | [symbolic](modules/symbolic.md) |
| `projects/minesweeper` | 路由策略的符号化/BDD 分析 | [minesweeper](modules/minesweeper.md) |

## 支持的设备与输入类型

“支持”不是布尔值：能识别文件、能解析某些语法、能准确转换某个功能以及经过真实设备
验证，是不同层级。以下生产/有限支持分类来自仓库根
[`README.md`](../../README.md)；精确的格式枚举来自
[`ConfigurationFormat`](../../projects/common/src/main/java/org/batfish/datamodel/ConfigurationFormat.java)。

### 主要支持平台

- A10 Networks ACOS
- Arista EOS
- Cisco ASA、IOS、IOS-XE、IOS-XR、NX-OS
- Check Point Gateway
- Cumulus Linux/NCLU
- F5 BIG-IP
- Fortinet FortiOS
- FRRouting（通常与主机/Cumulus 输入组合）
- iptables
- Juniper Junos（MX、EX、QFX、SRX、T、PTX 等）
- Nokia SR OS / SR-SIM（MD-CLI）
- Palo Alto Networks PAN-OS
- SONiC
- AWS 与 Azure 云网络对象

### 有限支持平台

- H3C Comware 7 / CR16000：IPv4 接口、static、ISIS、BGP、策略；EVPN/SRv6 配置保留。
  详见[H3C 模块、数据流与验证](modules/h3c-comware.md)。
- ArubaOS
- Dell Force10
- Foundry

### 代码中存在的其他格式

枚举还包含 Alcatel AOS、Blade Network、Cadant、FastPath、IBM BNT、Metamako、MRV、
MSS、Ruckus ICX、VyOS、VxWorks 等历史或局部支持格式，以及 `HOST`、`EMPTY`、
`IGNORED`、`UNKNOWN`、`UNSUPPORTED` 等流程控制值。不要仅凭枚举常量判断功能覆盖；
应同时检查：

1. [`VendorConfigurationFormatDetector`](../../projects/batfish/src/main/java/org/batfish/grammar/VendorConfigurationFormatDetector.java)
   是否能可靠检测；
2. [`ParseVendorConfigurationJob`](../../projects/batfish/src/main/java/org/batfish/job/ParseVendorConfigurationJob.java)
   是否分派到真实解析器，而非未实现集合；
3. 相应 `grammar`、`representation`、转换和测试目录；
4. `bf.q.initIssues()`、`fileParseStatus()` 与转换警告在真实配置上的结果。

## 数据与目录约定

一个 snapshot 是某一时刻或某个候选变更的网络输入集合。典型结构如下：

```text
snapshot/
├── configs/                 # 设备文本配置
├── hosts/                   # 主机 JSON（可选）
├── iptables/                # 主机防火墙输入（可选）
├── batfish/                 # 补充数据
│   ├── layer1_topology.json
│   └── runtime_data.json
├── aws_configs/             # AWS 对象（可选）
└── azure_configs/           # Azure 对象（可选）
```

可直接参考 [`networks/example`](../../networks/example)、
[`networks/cloud-azure`](../../networks/cloud-azure) 和
[`networks/hybrid-cloud-aws`](../../networks/hybrid-cloud-aws)。输入规范以
Pybatfish 的 snapshot 文档以及 [`BfConsts`](../../projects/common/src/main/java/org/batfish/common/BfConsts.java)
中的目录常量为准。

## 当前构建与软件版本

以下值均来自当前仓库文件，不代表其他 tag：

| 组件 | 当前值 | 版本来源 |
| --- | --- | --- |
| Batfish | `0.36.0` | [`projects/VERSION`](../../projects/VERSION) |
| Bazel | `9.2.0` | [`.bazelversion`](../../.bazelversion) |
| Java 源语言级别 | `21` | [`.bazelrc`](../../.bazelrc) |
| Java 构建运行时 | `remotejdk_25` | [`.bazelrc`](../../.bazelrc) |
| Bazel Python 工具链 | `3.14` | [`MODULE.bazel`](../../MODULE.bazel) |
| Pybatfish 用户环境 | Python `3.10+` | [`docs/building_and_running`](../building_and_running/README.md) |
| ANTLR | `4.13.2` | [`MODULE.bazel`](../../MODULE.bazel) |
| Jackson BOM | `2.22.2` | [`MODULE.bazel`](../../MODULE.bazel) |
| Guava BOM | `33.7.1-jre` | [`MODULE.bazel`](../../MODULE.bazel) |
| Jersey | `2.48` | [`MODULE.bazel`](../../MODULE.bazel) |
| Grizzly | `2.4.4` | [`MODULE.bazel`](../../MODULE.bazel) |
| Log4j | `2.26.1` | [`MODULE.bazel`](../../MODULE.bazel) |
| Caffeine | `3.2.4` | [`MODULE.bazel`](../../MODULE.bazel) |
| JUnit | `4.13.2` | [`MODULE.bazel`](../../MODULE.bazel) |
| Mockito | `5.23.0`（inline `5.2.0`） | [`MODULE.bazel`](../../MODULE.bazel) |
| PMD | `7.27.0` | [`MODULE.bazel`](../../MODULE.bazel) |
| Checkstyle | `13.11.0` | [`MODULE.bazel`](../../MODULE.bazel) |

注意三个容易混淆的版本：Bazel 的 Python 工具链服务于本仓库 Bazel 目标；
`python/requirements.txt` 是仓库工具依赖锁文件；用户安装的 `pybatfish` 是独立发布的
SDK。它们不是同一个环境，参见 [Python 客户端手册](python-client-guide.md)。

## 常用构建目标

```bash
# 构建/启动完整服务
bazel build //projects/allinone:allinone_main
bazel run //projects/allinone:allinone_main -- -runclient false

# 生成可部署 fat JAR 和供嵌入使用的 thin JAR
bazel build //projects/allinone:allinone_main_deploy.jar
bazel build //projects/allinone:batfish_thin.jar

# 全量、模块和单测方法
bazel test //...
bazel test //projects/coordinator/...
bazel test --test_filter=org.batfish.coordinator.WorkMgrServiceTest#getNonExistNetwork$ -- \
  //projects/coordinator:coordinator_tests
```

本地启动必须配置问题模板和持久化位置时，使用[部署指南](deployment-guide.md)中的完整
命令，不要只复制这里的最短示例。

## 源码规模与定位建议

当前 checkout 约有 3,972 个主 Java 文件、1,625 个 Java 测试文件、348 个 ANTLR
grammar 文件和 341 个 `BUILD.bazel`。阅读时不要从 `Batfish.java` 第一行顺序向下：

- 从请求入口开始：`WorkMgrServiceV2` → resource → `WorkMgr` → `WorkExecutor`。
- 从初始化开始：`Batfish.run()` → vendor config 序列化 → VI config 序列化 → dataplane。
- 从问题开始：JSON 模板 → `QuestionPlugin` → `Question` → `Answerer.answer()`。
- 从厂商语法开始：format detector → parse job switch → combined parser → extractor →
  vendor `Configuration.toVendorIndependentConfigurations()`。
- 使用相邻测试作为行为规范；厂商解析测试通常比类注释更能说明已支持语法。

## 已有专题文档

- [`docs/parsing`](../parsing/README.md)：解析框架、lexer mode 与 grammar 规范。
- [`docs/extraction`](../extraction/README.md)：parse tree 到厂商模型。
- [`docs/conversion`](../conversion/README.md)：厂商模型到统一模型。
- [`docs/post_processing`](../post_processing/README.md)：统一模型后处理。
- [`docs/data_plane`](../data_plane/README.md)：增量数据平面算法。
- [`docs/forwarding_analysis`](../forwarding_analysis/README.md)：转发分析。
- [`docs/question_development`](../question_development/README.md)：问题开发。
- [`docs/symbolic_engine`](../symbolic_engine/README.md)：BDD/符号分析。
- [`docs/development`](../development/README.md)：编码、测试和 PR 工作流。

## 文档维护规则

- 版本只写可追溯到仓库文件的值，并附相对链接。
- 命令应从仓库根目录执行；另有说明时再切换目录。
- 新增模块时同时更新本页和 [`modules/README.md`](modules/README.md)。
- 支持矩阵变化时同时核对根 README、`ConfigurationFormat`、parse-job 分派和测试。
- 外部 SDK/镜像行为应链接官方仓库，并注明其不由当前 checkout 固定。
