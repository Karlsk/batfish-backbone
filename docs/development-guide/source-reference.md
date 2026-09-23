# Codebase 源码导航

本页用于从“我要理解/修改什么”快速跳转到代码、构建目标、测试和专题文档。文件结构与
数量基于当前 checkout；包会持续变化，最终以 `BUILD.bazel` 和 `bazel query` 为准。

## 1. 仓库根目录

| 路径 | 内容 | 修改时注意 |
| --- | --- | --- |
| [`BUILD.bazel`](../../BUILD.bazel) | 根级 annotation processor 等目标 | 影响全仓 Java 编译 |
| [`MODULE.bazel`](../../MODULE.bazel) | Bzlmod、Java/Python rules、Maven/pip 依赖 | 与 lockfile 同步 |
| [`MODULE.bazel.lock`](../../MODULE.bazel.lock) | Bazel 模块解析锁 | 由 Bazel 更新 |
| [`maven_install.json`](../../maven_install.json) | Maven artifact pin | 不手工编辑 |
| [`.bazelrc`](../../.bazelrc) | Java 语言/runtime、Error Prone | 本地与 CI 共同生效 |
| [`.bazelversion`](../../.bazelversion) | Bazel `9.2.0` | Bazelisk 读取 |
| [`README.md`](../../README.md) | 用户入口、平台支持和 Docker 快速启动 | 支持矩阵变更需同步 |
| [`CONTRIBUTING.md`](../../CONTRIBUTING.md) | 贡献入口 | 细节链接到 docs |
| [`LICENSE`](../../LICENSE) | Apache 2.0 与第三方说明 | 新依赖需核对许可 |

## 2. `projects/` 工程

### 2.1 allinone

- 构建：[`projects/allinone/BUILD.bazel`](../../projects/allinone/BUILD.bazel)
- 入口：[`Main`](../../projects/allinone/src/main/java/org/batfish/allinone/Main.java)
- 组装：[`AllInOne`](../../projects/allinone/src/main/java/org/batfish/allinone/AllInOne.java)
- 参数：[`Settings`](../../projects/allinone/src/main/java/org/batfish/allinone/config/Settings.java)
- 说明：[modules/allinone](modules/allinone.md)

### 2.2 batfish core

- 任务入口：[`Driver`](../../projects/batfish/src/main/java/org/batfish/main/Driver.java)
- 核心门面：[`Batfish`](../../projects/batfish/src/main/java/org/batfish/main/Batfish.java)
- 格式检测：[`VendorConfigurationFormatDetector`](../../projects/batfish/src/main/java/org/batfish/grammar/VendorConfigurationFormatDetector.java)
- parse 分派：[`ParseVendorConfigurationJob`](../../projects/batfish/src/main/java/org/batfish/job/ParseVendorConfigurationJob.java)
- parse 执行框架：[`BatfishJobExecutor`](../../projects/batfish/src/main/java/org/batfish/job/BatfishJobExecutor.java)
- 拓扑 provider：[`TopologyProviderImpl`](../../projects/batfish/src/main/java/org/batfish/topology/TopologyProviderImpl.java)
- 数据平面插件：[`IncrementalDataPlanePlugin`](../../projects/batfish/src/main/java/org/batfish/dataplane/ibdp/IncrementalDataPlanePlugin.java)
- 数据平面引擎：[`IncrementalBdpEngine`](../../projects/batfish/src/main/java/org/batfish/dataplane/ibdp/IncrementalBdpEngine.java)
- VRF 路由状态：[`VirtualRouter`](../../projects/batfish/src/main/java/org/batfish/dataplane/ibdp/VirtualRouter.java)
- RIB delta：[`RibDelta`](../../projects/batfish/src/main/java/org/batfish/dataplane/rib/RibDelta.java)
- traceroute：[`TracerouteEngineImpl`](../../projects/batfish/src/main/java/org/batfish/dataplane/TracerouteEngineImpl.java)
- flow 推进：[`FlowTracer`](../../projects/batfish/src/main/java/org/batfish/dataplane/traceroute/FlowTracer.java)
- BDD 可达工厂：[`BDDReachabilityAnalysisFactory`](../../projects/batfish/src/main/java/org/batfish/bddreachability/BDDReachabilityAnalysisFactory.java)
- 说明：[modules/batfish-core](modules/batfish-core.md)

厂商代码有两种历史布局：

- `org/batfish/grammar/<vendor>` + `org/batfish/representation/<vendor>`：较早模块；
- `org/batfish/vendor/<vendor>/grammar|representation`：推荐的新 vendor-scoped 布局。

新厂商应遵循后者，参考 [`docs/example_code/new_vendor`](../example_code/new_vendor)。

### 2.3 common

- VI 根模型：[`Configuration`](../../projects/common/src/main/java/org/batfish/datamodel/Configuration.java)
- 格式枚举：[`ConfigurationFormat`](../../projects/common/src/main/java/org/batfish/datamodel/ConfigurationFormat.java)
- snapshot identity：[`NetworkSnapshot`](../../projects/common/src/main/java/org/batfish/common/NetworkSnapshot.java)
- 公共常量：[`BfConsts`](../../projects/common/src/main/java/org/batfish/common/BfConsts.java)
- REST 常量：[`CoordConsts`](../../projects/common/src/main/java/org/batfish/common/CoordConsts.java)、
  [`CoordConstsV2`](../../projects/common/src/main/java/org/batfish/common/CoordConstsV2.java)
- worker service：[`BatfishWorkerService`](../../projects/common/src/main/java/org/batfish/common/BatfishWorkerService.java)
- 问题服务接口：[`IBatfish`](../../projects/common/src/main/java/org/batfish/common/plugin/IBatfish.java)
- 问题基类：[`Question`](../../projects/common/src/main/java/org/batfish/datamodel/questions/Question.java)
- Answerer 基类：[`Answerer`](../../projects/common/src/main/java/org/batfish/common/Answerer.java)
- storage 契约：[`StorageProvider`](../../projects/common/src/main/java/org/batfish/storage/StorageProvider.java)
- 文件存储：[`FileBasedStorage`](../../projects/common/src/main/java/org/batfish/storage/FileBasedStorage.java)
- specifier 入口：[`SpecifierFactories`](../../projects/common/src/main/java/org/batfish/specifier/SpecifierFactories.java)
- 说明：[modules/common](modules/common.md)

### 2.4 coordinator

- 服务启动：[`Main`](../../projects/coordinator/src/main/java/org/batfish/coordinator/Main.java)
- REST 根：[`WorkMgrServiceV2`](../../projects/coordinator/src/main/java/org/batfish/coordinator/WorkMgrServiceV2.java)
- REST 子资源：[`resources/`](../../projects/coordinator/src/main/java/org/batfish/coordinator/resources)
- 生命周期门面：[`WorkMgr`](../../projects/coordinator/src/main/java/org/batfish/coordinator/WorkMgr.java)
- 队列：[`WorkQueueMgr`](../../projects/coordinator/src/main/java/org/batfish/coordinator/WorkQueueMgr.java)
- queued work：[`QueuedWork`](../../projects/coordinator/src/main/java/org/batfish/coordinator/QueuedWork.java)
- executor：[`WorkExecutor`](../../projects/coordinator/src/main/java/org/batfish/coordinator/WorkExecutor.java)
- 同 JVM worker adapter：[`BatfishWorkerServiceWorkExecutor`](../../projects/coordinator/src/main/java/org/batfish/coordinator/BatfishWorkerServiceWorkExecutor.java)
- ID：[`StorageBasedIdManager`](../../projects/coordinator/src/main/java/org/batfish/coordinator/id/StorageBasedIdManager.java)
- 说明：[modules/coordinator](modules/coordinator.md)

### 2.5 client

- Java CLI：[`Client`](../../projects/client/src/main/java/org/batfish/client/Client.java)
- REST helper：[`BfCoordWorkHelper`](../../projects/client/src/main/java/org/batfish/client/BfCoordWorkHelper.java)
- 命令定义：[`Command`](../../projects/client/src/main/java/org/batfish/client/Command.java)
- 模板 helper：[`QuestionHelper`](../../projects/client/src/main/java/org/batfish/client/QuestionHelper.java)
- 说明：[modules/client](modules/client.md)

### 2.6 question

- 聚合构建：[`projects/question/BUILD.bazel`](../../projects/question/BUILD.bazel)
- 各问题实现：[`org/batfish/question`](../../projects/question/src/main/java/org/batfish/question)
- 典型属性问题：[`ipowners`](../../projects/question/src/main/java/org/batfish/question/ipowners)
- 典型路由问题：[`routes`](../../projects/question/src/main/java/org/batfish/question/routes)
- 典型转发问题：[`traceroute`](../../projects/question/src/main/java/org/batfish/question/traceroute)
- ACL 搜索：[`searchfilters`](../../projects/question/src/main/java/org/batfish/question/searchfilters)
- 路由策略搜索：[`searchroutepolicies`](../../projects/minesweeper/src/main/java/org/batfish/minesweeper/question/searchroutepolicies)
- 说明：[modules/question](modules/question.md)

### 2.7 bdd / symbolic / minesweeper

- BDD 抽象：[`BDD`](../../projects/bdd/src/main/java/net/sf/javabdd/BDD.java)
- BDD 实现：[`JFactory`](../../projects/bdd/src/main/java/net/sf/javabdd/JFactory.java)
- 符号状态：[`symbolic/state`](../../projects/symbolic/src/main/java/org/batfish/symbolic/state)
- route transfer：[`TransferBDD`](../../projects/minesweeper/src/main/java/org/batfish/minesweeper/bdd/TransferBDD.java)
- 原子谓词：[`ConfigAtomicPredicates`](../../projects/minesweeper/src/main/java/org/batfish/minesweeper/ConfigAtomicPredicates.java)
- 说明：[bdd](modules/bdd.md)、[symbolic](modules/symbolic.md)、
  [minesweeper](modules/minesweeper.md)

## 3. `questions/` 模板

[`questions/stable`](../../questions/stable) 包含用户可见的稳定 JSON template；
[`questions/experimental`](../../questions/experimental) 是实验模板。一个 template 包含：

- `class`：服务端 Java Question 的全限定类名；
- `differential`：模板是否支持差异模式；
- `instance.instanceName`：Pybatfish `bf.q.<name>`；
- `instance.variables`：参数、schema、optional/default 等元数据。

模板由 coordinator 从 `-templatedirs` 加载，Pybatfish Session 初始化时请求并动态暴露问题。
修改 template 要同时测试 Java 反序列化与 Pybatfish 调用。

## 4. `networks/` 样例输入

| 路径 | 场景 |
| --- | --- |
| [`networks/example`](../../networks/example) | 入门多厂商/多协议示例，文档和 SDK 常用 |
| [`networks/cloud-azure`](../../networks/cloud-azure) | Azure 输入 |
| [`networks/hybrid-cloud-aws`](../../networks/hybrid-cloud-aws) | AWS 与传统配置组合 |
| [`networks/iptables-firewall`](../../networks/iptables-firewall) | 主机/iptables 场景 |

这些是可读示例，不替代 `projects/**/src/test/resources` 的精确回归 fixture。

## 5. `tests/` 顶层集成测试

[`tests`](../../tests) 包含 parsing、questions、AWS、roles、logging 等 shell/Python 或资源驱动
测试。Java 单测更多位于各项目 `src/test/java`。定位策略：

```bash
rg -n "要定位的配置行或问题名" tests projects/*/src/test
bazel query 'tests(//projects/batfish/...)' | rg 'vendor|grammar'
```

解析 vendor 的主要行为规范通常是：

```text
projects/batfish/src/test/java/.../<vendor>/
projects/batfish/src/test/resources/.../<vendor>/
```

## 6. `tools/`

| 路径 | 用途 |
| --- | --- |
| [`tools/bazel_run.sh`](../../tools/bazel_run.sh) | 开发环境构建并启动 allinone |
| [`tools/format`](../../tools/format) | 格式化入口 |
| [`tools/run_checkstyle.sh`](../../tools/run_checkstyle.sh) | Java style 检查 |
| [`tools/profiling`](../../tools/profiling) | async-profiler 与结果分析 |
| [`tools/benchmarks`](../../tools/benchmarks) | JMH benchmarks |
| [`tools/dd`](../../tools/dd) | 使用 Pybatfish 做 snapshot delta debugging |
| [`tools/jol`](../../tools/jol) | Java Object Layout 内存检查 |
| [`tools/stress_tests`](../../tools/stress_tests) | 压力测试 |

层次化配置调试还可使用根 BUILD/工具中提供的 flatten、preprocess、annotate 目标；具体命令见
新增厂商教程与 parsing 文档。

## 7. `skylark/`

[`skylark`](../../skylark) 存放自定义 Bazel/Starlark rule 和宏，例如 Java/JUnit/PMD 约定及
[`thin_jar.bzl`](../../skylark/thin_jar.bzl)。当普通 `java_library/java_test` 无法解释 target
行为时，从加载的 `.bzl` 宏继续追踪。修改宏可能影响数百个 package，应通过 `bazel query` 和
广泛构建验证。

## 8. `python/`

[`python/requirements.in`](../../python/requirements.in) 与
[`python/requirements.txt`](../../python/requirements.txt) 服务于本仓库 Bazel Python 工具；
[`python/BUILD.bazel`](../../python/BUILD.bazel) 暴露 lockfile/requirements。它不是 Pybatfish
SDK，客户端源码位于外部仓库。

## 9. `docs/`

文档按 pipeline 和开发活动组织：

- 架构：[`architecture`](../architecture/README.md)
- 解析：[`parsing`](../parsing/README.md)
- 提取：[`extraction`](../extraction/README.md)
- 转换：[`conversion`](../conversion/README.md)
- 后处理：[`post_processing`](../post_processing/README.md)
- 数据平面：[`data_plane`](../data_plane/README.md)
- 转发：[`forwarding_analysis`](../forwarding_analysis/README.md)
- 符号引擎：[`symbolic_engine`](../symbolic_engine/README.md)
- 问题开发：[`question_development`](../question_development/README.md)
- 开发规范：[`development`](../development/README.md)

## 10. CI 与仓库自动化

[`.github/workflows`](../../.github/workflows) 包含 pre-commit、构建、测试、
artifact 与漏洞扫描工作流。重点文件：

- [`pre-commit.yml`](../../.github/workflows/pre-commit.yml)：Python tests、Bazel 构建和 JAR artifact；
- [`reusable-vulnerability-scan.yml`](../../.github/workflows/reusable-vulnerability-scan.yml)：镜像扫描。

本地“测试通过”不自动代表 CI 全绿；变更构建宏、依赖、格式或镜像时应对照 workflow 的实际
命令。

## 11. 常用查询

```bash
# 文件/符号
rg --files projects/batfish | rg 'Vendor|Configuration|Parser'
rg -n 'class IncrementalBdpEngine|computeDataPlane' projects

# 构建目标
bazel query '//projects/allinone:*'
bazel query '//projects/question/...'

# 依赖与反向依赖
bazel query 'deps(//projects/allinone:allinone_main)'
bazel query 'rdeps(//..., //projects/common:common)'

# 测试
bazel query 'tests(//projects/coordinator/...)'
```

大型 `rdeps(//...)` 查询可能较慢，优先缩小到受影响子树。
