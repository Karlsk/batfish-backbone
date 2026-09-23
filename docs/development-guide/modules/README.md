# 模块介绍

本目录按 [`projects`](../../../projects) 下的 9 个顶层 Bazel 工程拆分。它们不是严格的
微服务：大多数模块最终被 `allinone_main` 装入同一个 JVM，但依赖方向和职责边界仍然重要。

## 依赖与数据流

```text
                        allinone
                       /   |    \
                  client coordinator batfish-core
                           |        |
                           +-- common/datamodel --+
                                    |             |
                                 question      symbolic
                                    |             |
                                    +-------- bdd-+
                                             |
                                         minesweeper
```

这是概念图，不是 Bazel 完整依赖图。实际 `BUILD.bazel` 中 `batfish`、`question` 与
`minesweeper` 会共同依赖 `common`/BDD 相关包，`allinone` 通过 runtime deps 聚合插件。

## 文档索引

| 模块 | 输入 | 输出 | 文档 |
| --- | --- | --- | --- |
| allinone | CLI 参数和模块 classpath | 完整开发服务 | [allinone.md](allinone.md) |
| batfish | snapshot、WorkItem 参数 | VI model、dataplane、answer | [batfish-core.md](batfish-core.md) |
| common | 各模块共享类型需求 | datamodel、接口、序列化契约 | [common.md](common.md) |
| coordinator | HTTP 请求、snapshot zip、question | queued work、answer/status API | [coordinator.md](coordinator.md) |
| client | 命令/JSON/本地 snapshot | REST 请求与终端输出 | [client.md](client.md) |
| question | 类型化 Question + `IBatfish` | `AnswerElement` | [question.md](question.md) |
| bdd | 布尔变量与逻辑函数 | 规范化 BDD | [bdd.md](bdd.md) |
| symbolic | 网络处理位置 | `StateExpr` 状态机节点 | [symbolic.md](symbolic.md) |
| minesweeper | VI routing policy | 符号 route/反例 | [minesweeper.md](minesweeper.md) |
| H3C Comware（batfish 厂商子模块） | CR16000 原始采集配置 | 厂商对象、IPv4 VI/路由、能力告警 | [h3c-comware.md](h3c-comware.md) |

## 何时修改哪个模块

- 新 REST 资源或 snapshot 生命周期：`coordinator`，协议常量放 `common`。
- 新厂商语法/转换：`batfish`，新的 VI 类型放 `common/datamodel`。
- 新问题：`question`；可复用服务接口在 `common/plugin/IBatfish`；模板在 `questions`。
- 新数据平面协议：`common` 的 model + `batfish/dataplane/ibdp` 的进程/RIB。
- 新 packet 可达状态：`symbolic/state` + `batfish/bddreachability` 的 transition/graph。
- 新 route-policy 符号语义：`minesweeper`，底层布尔操作在 `bdd`。
- 启动/参数穿透问题：`allinone` 或各模块 `config/Settings`，不要把业务逻辑放入口。

全局端到端说明见[架构与数据流](../architecture-and-data-flow.md)。
