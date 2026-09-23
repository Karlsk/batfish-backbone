# client 模块（Java CLI）

## 职责与边界

[`projects/client`](../../../projects/client) 是仓库内 Java 命令行客户端，入口目标
`//projects/client:client_main`。它读取交互命令或 command file，管理 network/snapshot/question，
通过 HTTP 调用 coordinator，并轮询 work。它**不是** Python SDK；Pybatfish 见
[`python-client-guide.md`](../python-client-guide.md)。

## 核心类

- [`Client`](../../../projects/client/src/main/java/org/batfish/client/Client.java)：命令解释器、
  question template 参数绑定、答案比较/输出。
- [`Command`](../../../projects/client/src/main/java/org/batfish/client/Command.java)：命令枚举、usage 和
  comparison mode。
- [`BfCoordWorkHelper`](../../../projects/client/src/main/java/org/batfish/client/BfCoordWorkHelper.java)：
  REST 请求、multipart、work 提交和状态轮询。
- [`QuestionHelper`](../../../projects/client/src/main/java/org/batfish/client/QuestionHelper.java)：JSON question
  加载/填参。
- [`LenientJsonParser`](../../../projects/client/src/main/java/org/batfish/client/LenientJsonParser.java)：交互输入的
  宽松 JSON 处理。

## 数据流

```text
stdin / command file
 → Command 识别与参数切分
 → Client 更新本地 network/snapshot/reference 状态
 → QuestionHelper 加载 template、校验必填变量与类型
 → BfCoordWorkHelper 调 /v2 REST
 → queue work → 指数/有界 backoff 轮询状态
 → 下载 Answer JSON
 → pretty/raw/file/test comparison 输出
```

`Client.validateAndSet()` 根据 template 的 `Variable` 描述验证参数并写入 JSON；模板中的
`instanceName` 是用户调用名称，`class` 指向服务端 Java Question。客户端只组装请求，不执行
Answerer。

## 示例

构建并查看帮助：

```bash
bazel run //projects/client:client_main -- -help
```

在 allinone 中执行命令文件更容易保证服务可用：

```bash
bazel run //projects/allinone:allinone_main -- \
  -runclient true \
  -cmdfile /absolute/path/to/batfish.commands
```

命令文件语法和当前命令集以 `Command.java` 与 `Client` 的 usage 输出为准。对新项目和自动化，
Pybatfish 提供更稳定的数据对象/DataFrame 工作流。

## 实现原理

`BfCoordWorkHelper` 构造 `http://host:port/v2`，把 API key 放入约定 header，区分同步资源请求与
异步 work。work 返回 UUID 后客户端定期查询终态；网络临时失败和服务端终止是不同错误类型。

答案测试功能支持把实际 JSON 与期望文件按多种模式比较，适合老式 regression command file。
新增比较模式时必须保证 JSON 顺序、浮点/集合语义明确，避免把表现层差异判成分析变化。

## 测试

```bash
bazel test //projects/client/...
```

应覆盖：command parsing、缺失必填变量、错误参数类型、宽松 JSON 边界、HTTP 非 2xx、work
异常终止、轮询超时和答案比较。

## 修改注意事项

- REST 常量来自 `common/CoordConsts*`，不要复制字符串。
- 新公开 API 通常还需要同步独立 Pybatfish 仓库。
- 不在 client 重做网络分析；逻辑应进入 Question/Answerer。
- 脚本兼容性依赖命令名和输出，修改时检查已有 command-file tests。
