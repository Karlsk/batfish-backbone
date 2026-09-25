# API 与数据契约

所有路径以 `/api/v1` 为前缀。MVP-02 已实现健康路由、统一错误及 Actor/AnalysisContext/JobDTO/ResultEnvelope，MVP-04/05 已实现认证与账号管理路由，MVP-06 已实现网络创建/列表/详情；MVP-07～10 已实现上传、任务、独立 worker 与快照初始化；其余业务接口仍为拟实现契约，不是现有 Batfish REST 的重命名。网络/快照采用 UUID，SDK 内部名称由 service 维护。日期使用 UTC ISO 8601，前端转换为本地时间。

## 最小参数与专家扩展

每种分析提供独立路由及 Pydantic 请求模型。常用参数显式定义，专家参数置于有类型的 options。核心请求和 options 均拒绝未知字段；禁止 options 覆盖身份、网络、快照、版本、连接地址、文件路径、overwrite 或资源限额。可支持的 SDK 参数先登记，再通过适配层展开 kwargs，不做任意 getattr 或 Python eval。

能力目录字段为 id、label、stage、enabled、disabled_reason、required_fields、options_schema、defaults、result_kind、requires_dataplane、schema_version。Pydantic 请求模型是校验来源，JSON Schema 用于前端高级表单；跨字段业务约束仍由 service 校验。SDK 有新参数时需升级映射和测试，不静默启用。

示例：

```http
POST /api/v1/networks/{network_id}/snapshots/{snapshot_id}/analyses/traceroute
Idempotency-Key: <客户端生成的唯一值>
Content-Type: application/json
```

```json
{
  "start_location": "core-01",
  "destination_ip": "10.0.0.10",
  "options": {
    "source_ip": "10.0.0.1",
    "ip_protocols": ["tcp"],
    "destination_ports": [443],
    "max_traces": 5,
    "ignore_filters": false
  }
}
```

SDK 映射：start_location→startLocation；destination_ip/source_ip/protocols/ports→HeaderConstraints 对应字段；max_traces→maxTraces；ignore_filters→ignoreFilters。此处 source_ip 可选；未提供时由 SDK 推导，结果必须展示实际生成的 Flow，不能假设其等于某个管理地址。IPv4 目标为单地址，协议默认为 icmp；指定端口时必须选择 TCP/UDP。max_traces 默认 5、范围 1～20。ignore_filters=true 是有效专家选择，但结论旁必须显示“已忽略 ACL”。

## 认证和权限

采用服务端可撤销会话，浏览器 Cookie 存随机 token，数据库只存 token 哈希。生产 Cookie 使用 HttpOnly、Secure、SameSite=Lax、Path=/，默认 8 小时绝对有效期。写请求要求受信 Origin 和会话绑定 CSRF token；登录也检查 Origin。前端不把长期凭证存 localStorage。登录失败统一返回，不泄露账号是否存在；失败限流可配置。

密码使用 Argon2id；默认至少 12 字符、最多 128 字符，允许密码短语；管理员创建/重置时传入临时密码，用户首次登录必须修改。必须改密的会话仅允许 me/password/logout。用户停用、重置密码或自己改密后撤销既有会话。禁止停用/降级最后一个有效管理员。

MVP-04 实现细节：Cookie 名为 `batfish_session`，CSRF 头为 `X-CSRF-Token`；登录/me 响应字段为 user_id、username、role、must_change_password、csrf_token，设 no-store。精确 Origin 白名单由环境配置，默认空；缺 Origin（含脚本调用）一律拒绝登录/写请求。本机 HTTP 测试显式关闭 Secure。失败默认按用户名及实际连接地址组合计数，1 分钟内最多 5 次失败，随后返回 429 RATE_LIMITED；成功不清除窗口内失败计数，防止用成功请求绕过限流。PostgreSQL 事务锁保证多实例一致。内部用户与会话 session_version 用于全设备撤销，不进入 API 响应。

| 接口 | 参数/结果 | 权限 |
| --- | --- | --- |
| POST /auth/login | username、password → 当前用户、csrf_token、must_change_password；设置 Cookie | 匿名 |
| POST /auth/logout | 撤销当前会话，204 | 登录用户 |
| GET /auth/me | 当前用户、角色、csrf_token、must_change_password | 登录用户 |
| POST /auth/password | current_password、new_password；撤销会话，204 后重新登录 | 登录用户 |
| GET/POST /users | 分页用户列表；创建 username、temporary_password、role | 管理员 |
| PATCH /users/{id} | enabled、role；不允许改密码字段混入 | 管理员 |
| POST /users/{id}/reset-password | temporary_password；强制下次改密 | 管理员 |

MVP-05 用户管理响应：创建 201/PATCH 200 返回 `{id, username, role, enabled, must_change_password, created_at}`；列表返回 `{items, offset, limit, total}`，默认 limit=50、最大 200；重置返回 204。重复 username 和最后有效管理员停用/降级返回 409；空 PATCH、null 或未知字段返回 422。用户不可由请求体传入 actor_id。自己停用或降级在仍有其他有效管理员时允许，下一请求权限立即变化。所有管理变更以数据库事务锁串行校验最后管理员，并与脱敏审计同事务；停用/重置递增会话版本，重新启用不恢复旧会话。

## 首版业务接口

`N=/networks/{network_id}`，`S=N/snapshots/{snapshot_id}`，仅用于下表缩写。

| 接口 | 最小输入 | 响应/行为 |
| --- | --- | --- |
| GET /health/live、/health/ready | 无 | live 不访问 SDK；ready 检查数据库/worker/最近引擎探测，不执行分析 |
| GET /capabilities | 无 | 已登记能力和可用状态，不暴露连接凭证 |
| GET/POST /networks | 创建 display_name | 列表；创建 201 NetworkDTO；SDK 状态失败保留可诊断记录 |
| GET N | 无 | 共享网络详情和 sync_state |
| POST N/uploads | multipart files 或一个 ZIP，二选一 | 201 UploadDTO；不触发初始化 |
| POST N/snapshots | display_name、upload_id、options | 202 {snapshot_id, job_id} |
| GET N/snapshots、GET S | 无 | 列表/详情含解析状态、内容摘要、来源和创建者 |
| GET S/diagnostics | limit、offset、severity 可选 | 初始化诊断分页；未完成返回 409 状态错误 |
| GET S/files | 无 | 文件元数据；不返回服务器绝对路径 |
| GET S/files/{file_id} | offset、limit 可选 | 按行分页的原始配置文本；保留真实行号 |
| POST S/analyses/nodes | options 可选 | 202 JobDTO，nodes/properties 筛选 |
| POST S/analyses/interfaces | nodes 可选、options 可选 | 202 JobDTO，interfaces/properties 筛选 |
| POST S/analyses/routes | nodes 可选、options 可选 | 202 JobDTO；options 包括 vrfs、network、protocols、prefix_match_type、rib |
| POST S/analyses/lpm-routes | ip、nodes 可选、options 可选 | 202 JobDTO；options.vrfs |
| POST S/analyses/traceroute | start_location、destination_ip、options | 202 JobDTO |
| GET /jobs、GET /jobs/{id} | 筛选 status/network_id/created_by 可选 | 分页历史/单任务；含来源与运行阶段 |
| POST /jobs/{id}/cancel | 无 | 仅可取消的 queued 任务，所有者或管理员可操作；running 或删除任务返回 409 |
| POST /jobs/{id}/retry | 无 | 复制已保存参数创建新任务；重新校验身份、资源和引擎状态 |
| GET /results/{id} | 无 | 元数据、摘要、警告和结果类型 |
| GET /results/{id}/rows | limit/offset/sort/filters | 表格分页；filters 使用登记过的列及操作符 |
| GET /results/{id}/flows | limit/offset | Flow 摘要；路径通过下述接口展开 |
| GET /results/{id}/flows/{flow_id}/traces | limit/offset | 路径、逐跳 actions、总数/截断状态 |
| GET /results/{id}/export | format=json 或 csv | 导出当前已保存结果；JSON 保留结构，CSV 仅用于表格 |
| DELETE N、DELETE S | 无 | 管理员；202 删除任务；有依赖/在途任务时 409 |
| GET /admin/engine | 无 | 管理员读取引擎占用与未知任务记录 |
| POST /admin/engine/reconcile | resolution、note | 管理员记录外部检查/受控重启证据并解除未知占用；不是远程强杀接口 |

所有分析的查询过滤在 SDK 参数中尽早下推；分页接口不承诺降低引擎计算量。前端列表分页默认 50，最大 200。routes 的 rib 首版限定 main/bgp，evpn 不因 SDK 接受字符串就自动开放。重试不是再次领取原 Job；旧记录保持不可变。

MVP-06 网络创建可省略 Idempotency-Key，由服务器生成并在成功/业务错误响应头回传；键限1～128个可打印 ASCII 字符。客户端应预生成并保留键以覆盖“未收到响应”的断网重试。NetworkDTO 增加可空 sync_error，仅保存 ENGINE_BUSY/ENGINE_UNKNOWN/ENGINE_UNAVAILABLE/WRITEBACK_FAILED 等安全码。网络列表返回 items/offset/limit/total。

Idempotency-Key 用于上传之外的任务提交和网络创建：服务端按用户、路由、资源、key 记录请求摘要；相同摘要返回同一任务/资源，不同摘要返回 409。网络创建若此前未完成SDK操作，可在同一资源身份下恢复创建；不生成另一个内部网络名。幂等记录至少保留 24 小时。结果缓存与任务提交幂等是不同机制；命中缓存仍生成归属于当前用户的任务记录，指向相同不可变结果。

## 公共数据结构

| DTO / 表 | 必要字段与约束 |
| --- | --- |
| Actor | user_id、role、enabled；只能从可信身份构造 |
| User / Session | UUID、username 唯一、password_hash、role、enabled、must_change_password；session token_hash 唯一、expires_at、revoked_at、csrf_secret |
| NetworkDTO | id、display_name、engine_name 唯一、sync_state(pending/ready/failed/deleting/deleted)、created_by、created_at |
| UploadDTO | id、network_id、owner_id、manifest、content_hash、storage_key、expires_at；未消费上传默认 24 小时清理 |
| SnapshotDTO | id、network_id、engine_name 唯一、display_name、content_hash、initialization_job_id、status(queued/initializing/ready/ready_with_warnings/failed/deleting/deleted)、quality_summary、created_by、base_snapshot_id 可空 |
| AnalysisContext | network_id、snapshot_id、reference_snapshot_id 可空、内部 engine names、engine_version、sdk_version、schema_version；service 构造 |
| JobDTO | id、kind、resource_ids、requested_parameters、effective_parameters、created_by、status、phase、attempt、lease_owner、heartbeat_at、engine_state、cancel_allowed、result_id、error、created/started/finished_at |
| ResultEnvelope | id、kind(table/traces/graph/diff)、schema_version、context、effective_parameters、summary、warnings、coverage(complete/limited/unknown)、truncated、truncation_reason、created_at |
| TablePage | columns[{key,label,type}]、rows、offset、limit、total；无法确定总数为 null，不假装完整 |
| TraceFlow | flow_id、headers、start_location、trace_count、returned_trace_count、truncated；每条 Trace 带 disposition、hops、steps |
| AuditEvent | actor_id、action、resource_id、outcome、request_id、timestamp；不记录密码、会话或完整配置 |

数据库保存 UUID 外键与已删除资源的来源摘要。上传消费、快照及任务创建和结果发布可共享基础设施事务句柄，业务模块不共享 ORM 实体；事务由基础设施提供，service 仍通过其他模块的公共方法协作。

MVP-02 DTO 位于 `backend/app/contracts/dto.py`：所有字段拒绝未知项；模型及嵌套 JSON 参数不可变，序列化后仍是标准对象/数组。AnalysisContext 的内部名称字段为 engine_network、engine_snapshot、engine_reference_snapshot；引用快照 ID 和内部名必须同时有值或同时为空。JobDTO.kind 为 upload/initialization/analysis/deletion；status 为 queued/running/succeeded/failed/cancelled/interrupted；engine_state 为 idle/busy/unknown。nullable 字段默认空，created_at 必填，所有日期必须有时区并归一为 UTC。ResultEnvelope 的 truncated=true 必须同时提供非空 truncation_reason。DTO 结构校验不替代 service 的可信身份、任务状态迁移和权限判断。

模块间固定服务入口：`AuthService.require_actor(session_token) → Actor`；`UsersService.get_identity(user_id) → UserIdentity`；`NetworksService.require_ready(actor, network_id) → NetworkDTO`；`UploadsService.consume(actor, network_id, upload_id) → UploadManifest`；`SnapshotsService.require_analyzable(actor, network_id, snapshot_id) → AnalysisContext`；`JobsService.submit(actor, kind, context, parameters, idempotency_key) → JobDTO`；`JobsService.claim(worker_id) → JobDTO | None`；`ResultsService.publish(context, payload) → ResultEnvelope`；`AnalysisService.submit(actor, context_ids, kind, request) → JobDTO`；`AnalysisService.execute(job) → ResultEnvelope`。诊断读取与配置查看不要求 require_analyzable，使用快照存在性校验。

SDK 边界方法：`SessionFactory.for_job(context)` 返回任务独占上下文；`AnalysisController.run(context, question_id, sdk_parameters) → StructuredAnswer`；`SnapshotController.initialize(context, upload_manifest, options) → InitializationAnswer`；`NetworkController.create/delete(engine_name)`；`SnapshotController.delete(context)`。StructuredAnswer/InitializationAnswer 只含普通类型、列 schema、警告及诊断，不含 requests.Response 或 SDK 实例。

快照初始化状态以 initialization_job_id 对应的任务为运行状态来源，快照 service 通过 JobsService.get(actor, job_id) 读取。初始化 queued/running 对应快照 queued/initializing；cancelled/interrupted/failed 对应快照 failed 并保留具体原因，不能永久显示 queued。重试初始化必须新建快照和任务，复用经校验的原始输入但使用新内部 SDK 名称；返回值同时包含新的 snapshot_id。禁止用通用重试直接覆盖旧快照。分析重试仍使用原快照，重新校验其可用性。

## 第二、三阶段接口增量

此表定义 advance spec 的对接契约；首版不注册这些路由。所有 analyses 路由返回 202 JobDTO，并共用幂等、权限和结果读取规则。

| 接口 | 参数/结果 | 归属 |
| --- | --- | --- |
| POST S/analyses/topology | view=layer3/bgp/ospf/isis；options.nodes/remote_nodes | ADV-01 |
| GET /results/{id}/graph | focus_node、hops=1、limit≤200；节点/边和范围/截断说明 | ADV-01 |
| POST S/analyses/bgp-sessions | options.mode=status/compatibility、nodes、remote_nodes | ADV-03 |
| POST S/analyses/test-filters | nodes、filters、source_ip、destination_ip；options 协议/端口 | ADV-05 |
| POST S/analyses/resolve-filters | nodes、filter_expression 可选；用于过滤器选择的受限查询 | ADV-05 |
| POST S/analyses/search-filters | nodes、filters、action；options.headers | ADV-07 |
| POST S/analyses/filter-line-reachability | nodes、filters；options.ignore_composites | ADV-07 |
| POST S/analyses/query | question_id、parameters；仅已登记且启用的问题 | ADV-09 |
| POST /networks/{id}/comparisons | baseline_snapshot_id、candidate_snapshot_id、display_name 可选 | ADV-11 |
| GET /networks/{id}/comparisons、GET /comparisons/{id} | 比较列表/详情 | ADV-11 |
| DELETE /comparisons/{id} | 管理员；有在途分析则409，否则删除标记后204；保留结果来源 | ADV-11 |
| POST /comparisons/{id}/analyses/config-diff | options 可选，首版该 options 无扩展字段 | ADV-12 |
| GET /results/{id}/diff/files | 分页文件变化摘要 | ADV-12 |
| GET /results/{id}/diff/files/{file_id} | 两侧行号与变更块，分页及截断说明 | ADV-12 |
| POST /comparisons/{id}/analyses/routes-diff | 复用 routes 请求字段 | ADV-13 |
| POST /comparisons/{id}/analyses/reachability-diff | destination_ips、start_location；options 流量范围及 max_traces | ADV-14 |
| POST S/fault-scenarios | display_name；deactivate_nodes/deactivate_interfaces 至少一项 | ADV-16 |

GraphDTO 为 nodes[{id,label,properties}]、edges[{id,source,target,source_interface,target_interface,edge_type}]、scope、truncated；图读取过滤范围与计算问题范围分别保存。

ComparisonDTO 为 id、network_id、baseline_snapshot_id、candidate_snapshot_id、baseline/candidate 内容摘要与引擎版本、display_name、created_by、created_at、deleted_at。比较创建不触发计算。DiffResult 的 source 始终带 baseline/candidate，不用模糊的 before/after 位置替代真实 ID。配置 diff 包含文件变化种类与两侧行号；路由 diff 保留两侧值及 SDK 原始标记；可达性 diff 按 flow 保存两侧 disposition/traces 及新增/消失方向。

故障派生关系在 SnapshotDTO.base_snapshot_id 保存。删除仍被有效 comparison 或未删除派生快照引用的基线返回409；先删除比较记录/派生快照再删除基线。ResourceLifecycleService 通过各模块service执行引用检查和删除，不引入 snapshots→changes→snapshots 循环。删除历史不会重写旧结果。

## 错误约定

统一返回 `{error: {code, message, field_errors, request_id, retryable}}`。401 未登录，403 权限不足，404 不存在，409 状态/幂等/删除冲突，413 输入过大，422 参数或能力范围不合法，429 请求限流，503 引擎不可用/调度阻塞。SDK 算出“不通”是正常分析结果，不是 HTTP 500。

MVP-02 的 field_errors 为 `[{path: ["body", "options", "字段名"], message: "Invalid value"}]`，路径也可包含数组下标；没有字段错误时为空数组。不包含输入值、validator 原始消息或异常上下文。request_id 是每个请求独立生成的 UUID，并对应 `X-Request-ID` 响应头；客户端同名头不被信任。当前错误代码为 VALIDATION_ERROR、UNAUTHORIZED、FORBIDDEN、NOT_FOUND、METHOD_NOT_ALLOWED、CONFLICT、NOT_READY、INTERNAL_ERROR 和兜底 HTTP_ERROR；领域专用代码随所属 spec 增补。

健康响应：live 返回 200 `{"status":"alive"}`；ready 仅在 database/worker/engine 三份观测均可用且时间不超过 READINESS_MAX_AGE_SECONDS 时返回 200 `{"status":"ready"}`。缺失、失败、过期、未来时间或状态源异常返回 503 NOT_READY，retryable=true。当前未接入观测生产者，默认 503；健康请求不构造 SDK Session。

扩展参数类型错误定位为 options 字段路径；SDK 拒绝表达式返回 SDK_PARAMETER_REJECTED，不返回堆栈和凭证。后台失败写入 job.error；查询失败任务本身仍返回 HTTP 200 和失败状态。引擎状态不明时 error code 为 ENGINE_STATE_UNKNOWN，retryable=false，直到管理员完成对账。

MVP-07 已实现上传：multipart重复字段 `files` 或单字段 `archive`，二选一且不接收其他字段；需要write身份和ready网络。UploadDTO.manifest为UploadManifest（upload_id、network_id、storage_key、files）；每项文件含id、path（逻辑相对路径）、sha256、size_bytes、encoding（utf-8/gb18030/binary）及line_count（按LF计数，binary为null）。content_hash按排序逻辑路径/文件SHA256/字节数计算，不依赖随机文件ID。storage_key是内部UUID，不是客户端可指定的路径。上传不使用幂等键，不初始化SDK快照。实际大小超限413 UPLOAD_TOO_LARGE；无效ZIP/路径/冲突422 VALIDATION_ERROR。内部consume校验网络、所有者或管理员、过期时间及单次消费；跨用户403、网络不匹配404、已消费/过期409。

ZIP压缩算法支持 STORED/DEFLATED；其他算法及损坏压缩流受控返回422。

MVP-08 已实现任务分页、详情及排队取消：列表支持status/network_id/created_by，默认50最大200；取消成功200 JobDTO，running/终态/deletion返回409，非发起人且非管理员403。cancel_allowed按kind+当前状态派生。JobDTO新增context（ExecutionContext或null）及retry_of（UUID或null）；ExecutionContext沿用AnalysisContext的资源名/版本字段，允许network级任务的snapshot_id/engine_snapshot同时为空，身份与名称仍成对出现。新任务context必填，旧记录兼容null；requested/effective参数独立冻结。JobsService.submit无通用HTTP入口，由各业务service校验资源后调用；可共享事务保证业务资源与排队原子提交。重试执行与worker仍在MVP-09。

JobsService.submit 接纳既有 AnalysisContext 和 ExecutionContext，均规范化并重新验证为不可变ExecutionContext，保持SnapshotsService.require_analyzable的返回契约可直接提交。

MVP-09：POST /jobs/{id}/retry → 202 JobDTO，仅所有者/管理员、failed/interrupted/cancelled、非deletion且已登记handler；同键重放返回同新任务，retry_of保留旧任务ID。未登记/不可重试409，unknown503 ENGINE_STATE_UNKNOWN。GET /admin/engine 返回state/owner/updated_at/interrupted_jobs（最多200个最近未知中断任务ID）；POST /admin/engine/reconcile 接收resolution（confirmed_idle/restarted）、note（5～1000字符），成功200同状态结构。必须先停止旧worker并确认引擎空闲；服务端同时检查worker与SDK执行锁，处理记录/审计/解除占用同事务。处理依据只存管理员对账表，不输出原始配置或异常。

## MVP-10 初始化契约补充

快照创建的 options 可省略；仅接受严格布尔 ignore_management_interfaces（默认 true）和 parse_reuse（默认 false），分别映射 extra_args.ignoremanagementinterfaces / parsereuse，固定 overwrite=false。创建与重试支持 Idempotency-Key；首次创建原子消费上传、保存 manifest/内容摘要/初始化 options、创建快照与 job。失败事务不会消费上传。初始化 task 的版本暂为 pending，成功后快照保存实际版本，require_analyzable 返回实际版本上下文。

SnapshotDTO 列表/详情包含 engine_version、sdk_version、quality_summary；原始 manifest、内部文件位置和诊断不直接进入列表。诊断/文件详情由 MVP-11 提供。ready 表示解析门通过，不是对真实设备行为一致性的证明；无可用节点、没有解析记录或 FAILED 为 failed，PARTIALLY_UNRECOGNIZED/其他非 PASSED 或初始化问题为 ready_with_warnings。初始化取消、中断、失败优先按关联 job 派生 failed。

重试返回新 JobDTO，id 是新 job_id，resource_ids.snapshot_id 是新 snapshot_id，retry_of 关联旧任务。复用已消费且不可变的输入 manifest，建立私有临时目录副本交给控制器，不再次消费上传，也不复用旧内部 snapshot 名称。未知引擎占用先停旧 worker 并完成管理员对账；历史 interrupted job 保留原状态。上传公共 DTO 移至 contracts/uploads.py 并保留原模块导出；UploadsService.consume 可使用共享 transaction，materialize 只接受服务端已存 manifest 并验证文件类型、大小和摘要。
