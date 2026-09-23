# 架构与端到端数据流

## 1. 运行时拓扑

Batfish 的核心是“协调器 + worker + 存储”。开发环境常把三者放进同一 JVM：

```text
org.batfish.allinone.Main
  └─ AllInOne.run()
      ├─ new Client(...)                         可选 Java CLI
      ├─ coordinator.Main.main(...)
      │   ├─ FileBasedStorage
      │   ├─ WorkMgr + WorkQueueMgr
      │   └─ Grizzly/Jersey REST /v2 (:9996)
      └─ batfish.main.Driver.main(...)
          └─ BatfishWorkerService
```

组装逻辑位于 [`AllInOne.java`](../../projects/allinone/src/main/java/org/batfish/allinone/AllInOne.java)，
REST 服务器和存储初始化位于
[`coordinator/Main.java`](../../projects/coordinator/src/main/java/org/batfish/coordinator/Main.java)。
默认 v2 路径 `/v2` 和端口 `9996` 定义在
[`CoordConsts.java`](../../projects/common/src/main/java/org/batfish/common/CoordConsts.java)。

同 JVM 不等于直接方法调用的所有层都被绕过：客户端仍可走 HTTP；coordinator 把
`QueuedWork` 转成 worker 参数并通过
[`BatfishWorkerServiceWorkExecutor`](../../projects/coordinator/src/main/java/org/batfish/coordinator/BatfishWorkerServiceWorkExecutor.java)
提交给 worker 服务。这个抽象允许 coordinator 不依赖具体任务进程实现。

## 2. 控制面请求流

以 Pybatfish 执行一个问题为例：

```text
Session.q.routes(...).answer()
  → 上传/引用 question JSON
  → POST /v2/networks/{network}/snapshots/{snapshot}/work
  → WorkMgr 解析 WorkItem
  → WorkQueueMgr 去重、依赖排序和排队
  → WorkExecutor.submit(QueuedWork)
  → worker Driver.runBatfish(...)
  → Batfish 加载/生成所需模型并运行 Answerer
  → StorageProvider 写 answer、metadata、日志
  → client 轮询 work 状态并读取 answer
  → Pybatfish Answer.frame() 转为 pandas DataFrame
```

REST 资源树从
[`WorkMgrServiceV2`](../../projects/coordinator/src/main/java/org/batfish/coordinator/WorkMgrServiceV2.java)
开始，按 network、snapshot、question、work、answer 分到
[`resources`](../../projects/coordinator/src/main/java/org/batfish/coordinator/resources)。任务类型和
依赖关系主要由 [`WorkDetails`](../../projects/coordinator/src/main/java/org/batfish/coordinator/WorkDetails.java)、
[`WorkQueueMgr`](../../projects/coordinator/src/main/java/org/batfish/coordinator/WorkQueueMgr.java)
和 [`WorkItemBuilder`](../../projects/common/src/main/java/org/batfish/common/util/WorkItemBuilder.java)
表达。

### 为什么有任务队列

解析、转换和数据平面都可能昂贵。问题还分为无需 dataplane、需要 dataplane、需要基线与
参考快照等类型。队列负责确保初始化先于依赖它的问题，避免相同工作并发重复，并允许客户端
异步轮询。不要在 REST resource 中直接执行分析；resource 只做协议转换和生命周期操作。

## 3. Snapshot 初始化数据流

初始化不是单次 parse，而是一组可缓存阶段：

```text
输入文件
  │
  ├─ 格式检测 VendorConfigurationFormatDetector
  ├─ 预处理/flatten（需要时）
  ├─ ANTLR lex + parse
  ├─ ControlPlaneExtractor 遍历 parse tree
  v
VendorConfiguration（厂商专用模型）
  │  toVendorIndependentConfigurations()
  v
Configuration（统一 VI 模型）
  │
  ├─ 接口依赖、聚合/冗余接口
  ├─ OSPF/EIGRP cost
  ├─ L1/L2/L3、隧道、IP ownership
  └─ 引用、默认值和状态收敛
  v
序列化配置 + 拓扑 + 初始化答案
  │
  └─ 按需 IncrementalDataPlanePlugin.computeDataPlane()
      ├─ 每 node/VRF 构造 VirtualRouter
      ├─ 协议 RIB 传播到固定点
      ├─ 拓扑、track、IP owner、VXLAN autostate 外层迭代
      └─ 生成 RIB/FIB/DataPlane/TopologyContainer
```

### 3.1 格式检测

[`VendorConfigurationFormatDetector`](../../projects/batfish/src/main/java/org/batfish/grammar/VendorConfigurationFormatDetector.java)
使用显式 `BATFISH_FORMAT`、RANCID 标头和厂商特征正则进行启发式检测。检测顺序是语义的
一部分：同一 token 可能同时像 Cisco、Junos 或另一个层次化语言。新增 detector 时必须写
冲突和负例测试。

### 3.2 解析、预处理与提取

[`ParseVendorConfigurationJob`](../../projects/batfish/src/main/java/org/batfish/job/ParseVendorConfigurationJob.java)
根据 `ConfigurationFormat` 创建具体 combined parser 和 control-plane extractor。层次化或支持
编辑动词的格式可能先 flatten、应用 groups/delete/replace/insert，再交给提取器。

ANTLR parser 只识别句法并生成 parse tree；extractor 把语法事件写入厂商专用对象。把厂商
默认值或跨语句语义塞进 grammar 通常是错误边界：这些逻辑应在表示模型、预处理或转换中实现。

### 3.3 转换与后处理

所有厂商模型继承
[`VendorConfiguration`](../../projects/common/src/main/java/org/batfish/vendor/VendorConfiguration.java)，
通过 `toVendorIndependentConfigurations()` 产出一个或多个
[`Configuration`](../../projects/common/src/main/java/org/batfish/datamodel/Configuration.java)。一个输入文件
可能产生多个逻辑设备，因此返回集合而非单对象。

[`Batfish`](../../projects/batfish/src/main/java/org/batfish/main/Batfish.java) 的
`serializeVendorConfigs()`、`serializeIndependentConfigs()` 和 `postProcessSnapshot()` 构成主要阶段。
后处理依赖网络全局信息，所以不应全部塞进单设备转换：例如接口依赖、二层邻接、IP ownership
与动态接口状态需要跨节点观察。

### 3.4 增量数据平面

[`IncrementalDataPlanePlugin`](../../projects/batfish/src/main/java/org/batfish/dataplane/ibdp/IncrementalDataPlanePlugin.java)
把插件接口适配到
[`IncrementalBdpEngine`](../../projects/batfish/src/main/java/org/batfish/dataplane/ibdp/IncrementalBdpEngine.java)。
引擎按节点/VRF 构造 [`VirtualRouter`](../../projects/batfish/src/main/java/org/batfish/dataplane/ibdp/VirtualRouter.java)，
为 connected、static、OSPF、EIGRP、ISIS、BGP、EVPN 等维护专用 RIB，并把变化表达为
[`RibDelta`](../../projects/batfish/src/main/java/org/batfish/dataplane/rib/RibDelta.java)。

内部协议传播与外部拓扑状态相互影响，算法因此有两层收敛：

1. 给定拓扑和 track 状态，路由进程传播到固定点；
2. 用新的 RIB/FIB 更新拓扑、track、IP owner 和 VXLAN autostate；若任一变化，重做外层迭代。

检测到协议振荡或达到最大拓扑迭代数仍不收敛时，引擎抛出
`BdpOscillationException`，而不是返回看似有效的中间状态。

## 4. 问题执行数据流

一个问题由三层组成：

| 层 | 作用 | 示例 |
| --- | --- | --- |
| JSON template | 用户可见名称、参数类型、默认值和 Java class | [`routes.json`](../../questions/stable/routes.json) |
| `Question` | 反序列化后的类型化请求，声明是否需要 dataplane/差异模式 | [`RoutesQuestion`](../../projects/question/src/main/java/org/batfish/question/routes/RoutesQuestion.java) |
| `Answerer` | 通过 `IBatfish` 读取模型并生成 `AnswerElement` | [`RoutesAnswerer`](../../projects/question/src/main/java/org/batfish/question/routes/RoutesAnswerer.java) |

插件类继承
[`QuestionPlugin`](../../projects/question/src/main/java/org/batfish/question/QuestionPlugin.java)，使用
Google AutoService 注册。`Batfish.answer()` 根据 `Question` 声明预加载当前/参考快照配置和
dataplane，然后创建 `Answerer`。`Answerer` 不应自己操纵 coordinator 或磁盘路径；它通过
[`IBatfish`](../../projects/common/src/main/java/org/batfish/common/plugin/IBatfish.java) 获取稳定接口。

表格问题一般返回 `TableAnswerElement`：先定义列 metadata，再创建 `Row`。转发问题可能返回
flow、trace、hop 与 disposition。Pybatfish 的 `.frame()` 只是在客户端把表格答案投影成
DataFrame，分析本身在服务端完成。

## 5. 转发与符号分析

### 5.1 具体 flow traceroute

[`TracerouteEngineImpl`](../../projects/batfish/src/main/java/org/batfish/dataplane/TracerouteEngineImpl.java)
和 [`FlowTracer`](../../projects/batfish/src/main/java/org/batfish/dataplane/traceroute/FlowTracer.java)
沿 FIB、ACL、NAT、session 和邻接逐跳推进具体流，记录 hop 与分支。结果终止于
`ACCEPTED`、`DELIVERED_TO_SUBNET`、`EXITS_NETWORK`、`DENIED_IN/OUT`、`NO_ROUTE`、
`LOOP` 等 disposition。

### 5.2 BDD 可达性

对“所有可能报文”逐个枚举不可行。Batfish 将报文字段编码为 BDD 变量，把 ACL、NAT 和
转发行为编译为状态间 transition；每个 BDD 表示一组报文。状态类型定义在
[`projects/symbolic`](../../projects/symbolic/src/main/java/org/batfish/symbolic/state)，transition 与
可达性图构造位于
[`projects/batfish/.../bddreachability`](../../projects/batfish/src/main/java/org/batfish/bddreachability)。
底层布尔运算来自仓库内 [`projects/bdd`](../../projects/bdd)。

### 5.3 路由策略符号分析

[`projects/minesweeper`](../../projects/minesweeper) 处理的是“符号路由”而非“符号报文”。
[`TransferBDD`](../../projects/minesweeper/src/main/java/org/batfish/minesweeper/bdd/TransferBDD.java)
把 routing policy 解释为从输入 route 到输出 route 的函数；community 和 AS-path 正则先拆成
原子谓词，再分配 BDD 变量。两条策略的输出约束做异或并求一个满足赋值，就能构造反例。

## 6. 存储与缓存

[`StorageProvider`](../../projects/common/src/main/java/org/batfish/storage/StorageProvider.java) 定义输入对象、
厂商配置、VI 配置、dataplane、拓扑、答案、日志和元数据的持久化契约；默认实现是
[`FileBasedStorage`](../../projects/common/src/main/java/org/batfish/storage/FileBasedStorage.java)。
coordinator 使用 [`StorageBasedIdManager`](../../projects/coordinator/src/main/java/org/batfish/coordinator/id/StorageBasedIdManager.java)
把用户名称映射为持久化 ID。

worker 同时维护配置和 dataplane 的 Caffeine 内存缓存。磁盘存在性与内存缓存是两个层次：
缓存 miss 不一定触发重新解析；先尝试从 storage 反序列化。snapshot 内容变化时必须通过正式的
初始化/fork API 产生新状态，不能直接修改 `containers` 内部文件。

## 7. 错误与可观察性

- `Warnings` 收集 red-flag、unimplemented 和 parse warning，尽量让部分可用模型继续分析。
- `ParseVendorConfigurationAnswerElement` 和转换答案记录文件级状态、警告和结构引用。
- coordinator 保存 work log、work JSON、answer metadata 和终态，客户端通过 work ID 查询。
- `bf.q.initIssues()` 是用户首先应运行的质量门，不应只检查 `init_snapshot()` 是否返回名称。
- 数据平面不收敛、问题反序列化失败或 storage I/O 失败是硬错误，任务应异常终止。

## 8. 扩展边界

- 新厂商：扩展 format detection、grammar、vendor representation、conversion 与测试；见
  [新增厂商开发流程](new-vendor-development.md)。
- 新问题：优先复用 VI model、dataplane 和 `IBatfish`，不要让问题依赖厂商模型；见
  [`docs/question_development`](../question_development/README.md)。
- 新协议：通常同时影响 datamodel、厂商转换、IBDP RIB/进程、拓扑和问题展示，先画清跨模块
  数据所有权。
- 新存储后端：实现 `StorageProvider` 并保持 ID/元数据和原子写入语义；不要泄漏具体路径到
  Answerer。
