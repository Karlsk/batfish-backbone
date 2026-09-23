# allinone 模块

## 职责

[`projects/allinone`](../../../projects/allinone) 是可执行组装层。它不实现解析或网络算法，
而是在一个 JVM 中启动 Java client、coordinator 与 worker，并确保 coordinator 能调用同进程
worker service。Bazel 主目标是 `//projects/allinone:allinone_main`。

## 入口与组成

- [`Main.java`](../../../projects/allinone/src/main/java/org/batfish/allinone/Main.java)：极薄的
  `public static void main`。
- [`AllInOne.java`](../../../projects/allinone/src/main/java/org/batfish/allinone/AllInOne.java)：参数拆分、
  三个组件的生命周期和线程启动。
- [`Settings.java`](../../../projects/allinone/src/main/java/org/batfish/allinone/config/Settings.java)：
  allinone 自身参数以及 client/coordinator/worker 参数字符串。
- [`BUILD.bazel`](../../../projects/allinone/BUILD.bazel)：runtime plugin 聚合、deploy JAR 和 thin JAR。

## 启动数据流

```text
argv
 → allinone Settings
 → 拼装 client args → new Client
 → runCoordinator()
     → coordinator.Main
     → BatfishWorkerServiceWorkExecutor(Driver.getBatfishWorkerService())
 → runBatfish()
     → 新线程 → Driver.main
 → runclient=true ? Client.run() : 主线程定期 sleep 保活
```

`BindPortFutures` 解决端口为 `0` 时的启动竞争：coordinator 绑定实际端口后完成 future，内置
client 再获取该端口。worker 与 coordinator 在不同线程中启动；异常主要写日志，进程入口负责
初始化失败时退出。

## 实现原理

`AllInOne` 接收三段嵌套参数：`clientargs`、`coordinatorargs` 和 `batfishargs`。当前实现通过
空白拆分字符串，因此包含空格的嵌套参数必须按既有 CLI 约定传递；不要把这里当通用 shell
parser。`runclient=false` 时仍会构造 Client，以获得共享 logger，并注入 dummy command file
绕过 client 初始化约束。

coordinator 获得的 `WorkExecutorCreator` 构造
[`BatfishWorkerServiceWorkExecutor`](../../../projects/coordinator/src/main/java/org/batfish/coordinator/BatfishWorkerServiceWorkExecutor.java)，
其底层 service 由 [`Driver`](../../../projects/batfish/src/main/java/org/batfish/main/Driver.java)
提供。因此开发模式不需要额外 worker discovery。

## 示例

```bash
bazel run //projects/allinone:allinone_main -- \
  -runclient false \
  -coordinatorargs "-templatedirs $(pwd)/questions -containerslocation $(pwd)/containers"
```

用命令文件运行内置 Java client：

```bash
bazel run //projects/allinone:allinone_main -- \
  -runclient true \
  -cmdfile /absolute/path/to/commands.txt
```

面向用户的自动化优先使用 Pybatfish；内置 client 更适合兼容性测试和开发诊断。

## 构建与测试

```bash
bazel build //projects/allinone:allinone_main
bazel build //projects/allinone:allinone_main_deploy.jar
bazel build //projects/allinone:batfish_thin.jar
bazel test //projects/allinone/...
```

`allinone_main_deploy.jar` 是含运行时依赖的 Java deploy JAR；`batfish_thin.jar` 只聚合 Batfish
自有模块，嵌入者必须提供第三方依赖。

## 修改注意事项

- 算法/业务逻辑应放回所属模块，allinone 只负责 wiring。
- 新 `Plugin` 若依赖 AutoService 发现，必须确保其模块出现在 runtime classpath。
- 新增参数应判断属于 allinone 还是应原样下传，避免三处 Settings 重复定义。
- 生命周期测试要覆盖动态端口和 `runclient=false`，否则容易出现本地可用、CI 端口竞争。
