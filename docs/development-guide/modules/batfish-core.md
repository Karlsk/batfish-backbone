# batfish 核心模块

## 职责

[`projects/batfish`](../../../projects/batfish) 是最大模块，负责 worker 任务执行、输入解析、厂商
模型、VI 转换、网络拓扑、增量数据平面、具体与符号转发分析。顶层别名是
`//projects/batfish:batfish`。

主要 package：

| package | 职责 |
| --- | --- |
| `org.batfish.main` | Driver、Batfish 门面、任务生命周期 |
| `org.batfish.job` | 可并行 parse/convert job 与结果归并 |
| `org.batfish.grammar` / `org.batfish.vendor` | 格式检测、ANTLR adapter、厂商模型与转换 |
| `org.batfish.representation` | 传统 vendor-scoped 表示模型 |
| `org.batfish.topology` | L1/L2/L3、隧道、邻接与 IP owner |
| `org.batfish.dataplane.ibdp` | 增量数据平面引擎和协议进程 |
| `org.batfish.dataplane.rib` | 协议/主 RIB、delta 与解析 |
| `org.batfish.dataplane.traceroute` | 具体 flow 逐跳模拟 |
| `org.batfish.bddreachability` | packet-set BDD reachability |

## Worker 核心数据流

```text
Driver.runTask(argv)
 → Settings + NetworkSnapshot IDs
 → new Batfish(... StorageProvider/cache/plugins ...)
 → Batfish.run()
    ├─ serializeVendorConfigs()
    ├─ serializeIndependentConfigs()
    ├─ computeDataPlane()（按任务需要）
    └─ answer()（按任务需要）
 → StorageProvider 保存 answer/log/metadata
```

核心门面是 [`Batfish.java`](../../../projects/batfish/src/main/java/org/batfish/main/Batfish.java)，
但阅读应从具体方法进入，不建议线性通读。插件通过 `PluginConsumer`/AutoService 注册，data-plane
插件通过名称选择。

## 初始化实现

### Parse job

`Batfish` 枚举 snapshot 输入，为文件组创建
[`ParseVendorConfigurationJob`](../../../projects/batfish/src/main/java/org/batfish/job/ParseVendorConfigurationJob.java)。
job 检测/接受期望格式，创建具体 parser/extractor，产出 vendor configuration、parse tree sentence
和 warning。`BatfishJobExecutor` 并行执行并按结果类型归并。

### Vendor → VI

厂商对象的 `toVendorIndependentConfigurations()` 生成统一
[`Configuration`](../../../projects/common/src/main/java/org/batfish/datamodel/Configuration.java)。
转换 job 保留 answer element 和 warnings。随后 `postProcessSnapshot()` 处理跨设备/跨接口派生信息，
并写 VI 配置与拓扑。

### 缓存

内存中缓存配置和 `DataPlane`，storage 中保存序列化产物。`loadConfigurations()` 的次序是：
检查 cache/存储 → 必要时初始化 → 反序列化 → post-process → 放入 cache。修改 storage 文件绕过
snapshot API 会破坏该不变量。

## IBDP 原理

[`IncrementalDataPlanePlugin`](../../../projects/batfish/src/main/java/org/batfish/dataplane/ibdp/IncrementalDataPlanePlugin.java)
加载 VI 配置和初始拓扑，交给
[`IncrementalBdpEngine`](../../../projects/batfish/src/main/java/org/batfish/dataplane/ibdp/IncrementalBdpEngine.java)。

每个 [`Node`](../../../projects/batfish/src/main/java/org/batfish/dataplane/ibdp/Node.java) 持有 VRF 对应的
[`VirtualRouter`](../../../projects/batfish/src/main/java/org/batfish/dataplane/ibdp/VirtualRouter.java)。
协议进程把新增/撤销路由表达为 `RouteAdvertisement`/`RibDelta`，只传播变化而不是每轮复制全表。
主 RIB 决策后生成 FIB；BGP、OSPF、EIGRP、ISIS 与 EVPN 有独立 RIB/状态。

外层固定点还包含拓扑、track reachability/route、IP ownership 和 VXLAN autostate。任何一个变化
都可能反过来改变 connected route 或邻接，所以需重新迭代。

## 转发实现

- 具体流：[`TracerouteEngineImpl`](../../../projects/batfish/src/main/java/org/batfish/dataplane/TracerouteEngineImpl.java)
  构造 context，`FlowTracer` 沿 FIB/ACL/NAT/session 分支，`TraceRecorder` 生成轨迹。
- 全空间：`bddreachability` 把 headerspace 表成 BDD，把每个网络处理步骤表成 `Transition`，
  在 `StateExpr` 图上求可达集合。
- 统一模型查询：通过 `IBatfish` 暴露给 Answerer，避免 question 直接依赖实现字段。

## 示例：运行厂商解析测试

```bash
# 列出一个厂商包目标
bazel query '//projects/batfish/src/test/java/org/batfish/grammar/cisco/...'

# 运行整个包
bazel test //projects/batfish/src/test/java/org/batfish/grammar/cisco/...
```

示例：定位数据平面失败时，先分别验证 VI 转换和 IBDP：

```python
bf.q.interfaceProperties().answer().frame()  # VI 层
bf.q.bgpSessionCompatibility().answer().frame()  # 拓扑/配置层
bf.q.routes().answer().frame()  # dataplane 层
bf.q.traceroute(...).answer().frame()  # forwarding 层
```

## 修改准则

- vendor 特有语义留在 vendor representation/conversion；不要污染 VI 算法。
- VI model 变化放 `common` 并评估 JSON 兼容、equals/hashCode 和所有 vendor。
- 协议传播使用 delta 与固定点框架，避免全表扫描和非确定迭代顺序。
- warning 必须携带文件/行和结构上下文；不可静默纠正配置。
- 新行为至少有单元测试、pipeline conversion 测试，影响路由时再加 dataplane/E2E。

专题文档：[`parsing`](../../parsing/README.md)、[`conversion`](../../conversion/README.md)、
[`data_plane`](../../data_plane/README.md)、[`forwarding_analysis`](../../forwarding_analysis/README.md)。
