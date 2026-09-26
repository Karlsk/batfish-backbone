# 技术架构与模块边界

## 技术选择

前端使用 React、TypeScript、Vite、Ant Design、TanStack Query；二阶段加入 Cytoscape.js。后端使用 FastAPI、Pydantic、Pybatfish、SQLAlchemy/Alembic、PostgreSQL。后台为单独的 Python worker 进程；不使用 API 进程内临时 BackgroundTasks 承载分析，不在首版引入 Redis/Celery。版本在 MVP-01/02 验证后固定到锁文件，不直接追随 latest。

选择 PostgreSQL 是团队共享下对账号、任务领取和并发状态一致性的设计默认值；单机部署即可。数据库保存业务元数据，Batfish 保存其原生网络/快照/答案，不复制或直接读取引擎内部存储结构。

## 分层规则

```text
HTTP → 模块 api → 模块 service → 模块 controller → Pybatfish → Batfish
                         ↓
                 本模块 repository / 文件存储
                         ↓
                   数据库 / 文件卷
```

- api：Pydantic 校验、可信身份提取、调用 service、HTTP 状态映射。业务代码不接收 FastAPI Request。
- service：业务权限、生命周期、上下文绑定、任务编排及摘要计算；返回公共 DTO，不返回 SDK 对象。
- controller：唯一导入/操作 Pybatfish 的业务边界，将普通 DTO 映射为 SDK 参数，将 SDK 返回转换为可序列化结构，转换底层异常。
- repository：封装本模块 SQL 和事务；跨模块不允许直接访问。文件读写通过注入的存储接口进行。
- 公共类型放 contracts；日志/时钟/数据库连接等放 infrastructure，不在 shared 中堆业务。
- composition 是应用和 worker 的装配入口，负责依赖注入，不提供业务服务。

controller 的职责是 SDK 适配，并非 HTTP controller。无 SDK 操作的模块可只有 api/service/repository。共享 SDK session factory 属于 infrastructure/sdk，且只允许 controllers 和兼容性测试使用。通过导入约束测试验证这些规则。

## 代码结构与实施状态

MVP-01～25 与 ADV-01～13 已完成；ADV-11 增加比较记录、双快照上下文及删除引用保护，ADV-12 增加受控文件比较与不可变差异结果，ADV-13 经 analysis.service 与独占 SDK controller 增加路由差异。可达性差异由后续规格实施。实际启动与测试见 [后端 README](../backend/README.md)。

```text
web/backend/app/
  main.py
  composition.py
  contracts/           # Actor、AnalysisContext、结果和错误 DTO
  infrastructure/      # 数据库、文件、时钟、日志、SDK factory
  modules/
    health/            # 已实现 api/service：存活及依赖状态快照判断
    auth/              # 登录、会话和业务权限
    users/             # 用户生命周期
    networks/          # network 生命周期和 SDK 映射
    uploads/           # 输入文件校验与存储
    snapshots/         # snapshot 生命周期和诊断状态
    jobs/              # 持久化任务与执行调度
    results/           # 不可变结果、分页、导出
    analysis/          # 能力目录、参数映射、专用分析
    lifecycle/         # 跨资源删除编排；二/三阶段追加引用保护
    changes/           # 双快照比较、配置文件和路由差异；后续扩展其他差异分析
  worker.py
web/frontend/src/
  app/                 # 路由、主题、全局网络/快照上下文
  api/                 # 从 OpenAPI 生成的类型及请求封装
  features/            # auth/networks/snapshots/jobs/inventory/routes/traces 等
  components/          # 参数展开、结果表格、详情抽屉、状态提示
```

每个业务模块内部按需要设 api.py、schemas.py、service.py、controller.py、repository.py；文件过大按职责拆文件，不提前引入无用途的抽象基类。

## 依赖与任务装配

基础方向：users → 本模块存储；auth → users.service；networks → auth.service；uploads → auth.service；snapshots → networks.service / uploads.service / jobs.service；analysis → snapshots.service / jobs.service / results.service / auth.service；changes → snapshots.service / analysis.service / jobs.service。jobs 与 results 不反向导入业务模块；jobs.service 使用公共 Actor 和数据契约执行通用任务所有权规则。

UsersService 初始化审计通过 audit.service 写入。用户 session_version 与会话版本匹配才能认证，停用和版本变更每次请求生效；users 不反向依赖 auth，以便后续管理重置/停用保持模块依赖无环。bootstrap 命令通过 composition 装配 UsersService，不绕过 service 直接写 ORM。

跨资源删除统一由 lifecycle.service（ResourceLifecycleService）编排，依赖 networks/snapshots/jobs.service，第三阶段增加 changes.service 检查比较引用。DELETE 路由由 lifecycle.api 提供但URL不变。snapshots/changes 不反向依赖 lifecycle；比较引用与派生依赖的删除检查在同一资源锁/事务边界完成，避免先检查后并发新增引用。所有删除入口必须经过 lifecycle.service。

worker 从 jobs.service 领取 JobDTO 后，由 composition 中的已登记 dispatcher 调用对应业务 service 的执行入口。业务 service 执行 SDK 后通过 results.service 发布结果，再通过 jobs.service 提交状态。dispatcher 不是 jobs.service 的反向业务依赖；业务代码不能动态导入用户指定模块或函数。

取消/重试同样由装配层登记的业务 service handler 处理上下文变化，jobs.service 不反向导入 snapshots/analysis。初始化快照展示状态从初始化任务派生，任务被取消后快照立即体现失败原因。初始化重试创建新快照；analysis 重试创建新任务；删除任务一旦进入队列不允许取消或通用重试，失败时走删除对账，避免资源一直停留在 deleting。

统一方法契约：业务入口接收 `actor: Actor`、显式资源 ID 和有类型的请求 DTO；执行入口接收不可变 `JobDTO`；controller 接收 `AnalysisContext` 与已归一化参数。结果统一为 ResultEnvelope。方法名与具体类型在 [API 契约](api-contracts.md) 中固定。

## SDK 上下文

每个在执行任务创建独占 Session，在该任务内复用，不让线程/任务共用可变 network/snapshot。上下文包含 SDK network name、snapshot name、reference snapshot name 和引擎版本；这些来自服务端资源映射，不来自 options。所有问题显式指定目标 snapshot；差异问题明确 candidate 与 reference 方向。

只使用经 MVP-01 确认的公共 SDK 能力。源码中存在 REST work 接口，不等于 SDK 暴露了公共取消/恢复句柄。首版只承诺取消未开始的 Web 任务；运行中不显示“已取消”。不得为了实现按钮而调用未经验证的私有 Session 方法。若公开 SDK 缺失必要功能，先记录证据并修订受影响 spec；本设计不授权绕过 SDK 编写第二套 REST 客户端。

## 任务执行与故障恢复

Job 状态：queued、running、succeeded、failed、cancelled、interrupted。只有 queued 可取消；running 中浏览器断开无影响。上传、初始化、分析和删除分别有 kind。

worker 使用数据库事务原子领取 queued 任务，记录 lease owner、heartbeat、attempt。单 Batfish 实例所有 SDK 工作默认串行，Web 元数据读写仍可并发。同步的网络创建也通过基础设施获取同一引擎执行锁；忙碌时返回503并保留可重试资源状态，不长时间占用 HTTP 请求。引擎繁忙时健康读取复用最近探测状态，不再插入 SDK 调用。没有 Redis 队列；新 worker 不能仅因租约过期就重复执行可能已提交到引擎的工作。

分析/初始化进程失联时置 interrupted，记录 `engine_state=unknown` 并阻止新 SDK 工作调度。管理员通过引擎诊断或受控重启确认空闲后解除阻塞，再手动重试。只有“尚未调用 SDK”的失败可自动安全重试。不会承诺精确一次远程执行或自动接管 SDK 阻塞调用。

SDK 客户端超时不等于引擎停止；未知状态必须保留占用。worker 优雅停止先暂停领取并等待当前任务；超过关闭期限则按失联处理。错误处理要展示下一步操作，而不是永久转圈。

## 数据一致性

资源映射先写 pending 记录，再操作 SDK，最后写 ready/failed。网络创建使用稳定内部名称；SDK 完成而数据库写回失败时可按该名称对账。快照使用唯一内部名称，初始化永远 overwrite=false；失败不重用旧名字。

结果先写临时文件、校验，再原子发布；results 元数据与 job 成功更新在可协调的事务中完成。发布失败不显示成功；遗留临时文件可清理。缓存键包含引擎/SDK 版本、快照内容标识、基线、问题版本及归一化参数；不使用“当前快照”这种可变键。

解析结果和能力限制作为来源元数据附着于所有分析结果；升级后旧结果仍标明原来的引擎版本，不能与新结果混作同一缓存。

## 参考

- [仓库 Coordinator 说明](../../docs/development-guide/modules/coordinator.md)
- [Pybatfish 公共命令](https://pybatfish.readthedocs.io/en/latest/batfish_commands.html)
- [FastAPI 长任务说明](https://fastapi.tiangolo.com/tutorial/background-tasks/)

外部文档用于确认 SDK 与框架机制；本文中的 Web 接口和任务状态是本项目设计，不是 Batfish 已存在的 API。

MVP-07 的 uploads.archive 是本模块 repository 使用的纯文件解析辅助，仅允许 repository→archive→schemas，不扩大跨模块入口。HTTP multipart流限制位于 infrastructure，api只校验字段组合并传递文件流，service处理身份、网络绑定和消费规则，repository处理受控文件与ORM。原始文件按服务端UUID保存，ZIP路径只进入经过验证的逻辑manifest。

MVP-09以execution.service编排jobs/auth/audit和composition登记的handler；jobs不反向依赖snapshots/analysis。infrastructure.WorkerRunner只持有装配回调，不导入业务模块。app.worker仅通过composition启动，API与worker为独立进程。数据库记录worker观测，health通过装配回调读取；SDK版本探测在execution.controller，所有会话共用EngineGate。worker进程锁、领取状态条件、SDK锁与unknown持久状态分别约束进程、任务和远端调用，不把租约到期当作远端停止证明。
