# coordinator 模块

## 职责

[`projects/coordinator`](../../../projects/coordinator) 是控制平面：暴露 REST v2、管理 network/
snapshot/question、持久化对象与元数据、为初始化和问题创建 `QueuedWork`、调度 worker 并提供
状态/答案/日志查询。它不解释厂商配置，也不计算数据平面。

## 核心对象

| 对象 | 作用 |
| --- | --- |
| [`Main`](../../../projects/coordinator/src/main/java/org/batfish/coordinator/Main.java) | 初始化 Settings、Authorizer、FileBasedStorage、WorkMgr 和 Grizzly/Jersey |
| [`WorkMgrServiceV2`](../../../projects/coordinator/src/main/java/org/batfish/coordinator/WorkMgrServiceV2.java) | `/v2` 根资源 |
| [`resources`](../../../projects/coordinator/src/main/java/org/batfish/coordinator/resources) | network/snapshot/question/work/answer 子资源 |
| [`WorkMgr`](../../../projects/coordinator/src/main/java/org/batfish/coordinator/WorkMgr.java) | 生命周期和 work 构造的业务门面 |
| [`WorkQueueMgr`](../../../projects/coordinator/src/main/java/org/batfish/coordinator/WorkQueueMgr.java) | work 依赖、去重、排队和状态转换 |
| [`WorkExecutor`](../../../projects/coordinator/src/main/java/org/batfish/coordinator/WorkExecutor.java) | worker 提交抽象 |
| [`StorageBasedIdManager`](../../../projects/coordinator/src/main/java/org/batfish/coordinator/id/StorageBasedIdManager.java) | 名称到持久 ID 的映射 |

## 请求数据流

```text
HTTP /v2
 → Jersey resource：验证 path/header/body
 → WorkMgr：解析 network/snapshot ID，写输入/metadata
 → WorkItem + WorkDetails
 → WorkQueueMgr：检查 prerequisites/duplicate，进入 queue
 → WorkExecutor.submit(QueuedWork)
 → TaskHandle 查询 worker Task 状态
 → 更新 QueuedWork 与 snapshot metadata
 → answer/worklog endpoint 从 StorageProvider 返回结果
```

资源类使用 subresource locator 形成路径树。例如 `WorkMgrServiceV2` 返回 `NetworkResource`，
它再返回 `SnapshotsResource`/`WorkResource`。这避免一个巨型 REST 类，但业务一致性仍由
`WorkMgr` 维护。

## 工作依赖原理

问题对初始化产物的需求不同：配置属性问题只需 VI 配置；routes/reachability 需要 dataplane；
差异问题还需 reference snapshot。`WorkDetails` 描述工作类型和 snapshot 集，`WorkQueueMgr`
决定可立即运行、等待前置工作、复用已有结果或拒绝重复请求。

默认 allinone 使用
[`BatfishWorkerServiceWorkExecutor`](../../../projects/coordinator/src/main/java/org/batfish/coordinator/BatfishWorkerServiceWorkExecutor.java)：

1. `QueuedWork.resolveRequestParams()` 解析最终参数；
2. 注入 storage base；
3. 转成 `-key value` argv；
4. 调用 `BatfishWorkerService.runTask()`；
5. 把 `LAUNCHED/BUSY/ERROR` 映射成 `SubmissionResult`。

## 存储

`Main.initWorkManager()` 创建
[`FileBasedStorage`](../../../projects/common/src/main/java/org/batfish/storage/FileBasedStorage.java)。
coordinator 只通过 [`StorageProvider`](../../../projects/common/src/main/java/org/batfish/storage/StorageProvider.java)
契约读写，不应在 resource 中拼内部路径。snapshot 上传应先校验 zip 条目并写临时树，再进入
正式 ID 空间，防止部分写入成为有效 snapshot。

## REST 示例

```bash
# 服务版本
curl -sS http://localhost:9996/v2/version

# network 列表（本地默认 key）
curl -sS \
  -H 'X-Batfish-Apikey: 00000000000000000000000000000000' \
  http://localhost:9996/v2/networks
```

REST header/path 常量在
[`CoordConstsV2`](../../../projects/common/src/main/java/org/batfish/common/CoordConstsV2.java)；调用方
优先使用 Pybatfish，避免手写 multipart 与 work 轮询。

## 扩展示例：新只读资源

通常流程是：

1. 在 `CoordConstsV2` 增加稳定路径常量；
2. 在正确父 resource 增加 subresource locator 或 `@GET`；
3. 业务逻辑进入 `WorkMgr`，存储进入 `StorageProvider`；
4. 对授权、404、空结果、storage failure 和 JSON shape 写 resource/service 测试；
5. 同步 Pybatfish 客户端后再宣称公开支持。

不要直接返回存储实现类或 Java exception stack；使用 bean/DTO 和统一 exception mapper。

## 测试

```bash
bazel test //projects/coordinator/...
bazel test --test_filter=org.batfish.coordinator.WorkMgrServiceTest#getNonExistNetwork$ -- \
  //projects/coordinator:coordinator_tests
```

重点测试并发重复 work、异常终态、删除中的任务、损坏 zip、授权、ID 映射和临时目录清理。
