# API 与数据契约

所有路径以 `/api/v1` 为前缀。MVP-02 已实现健康路由、统一错误及 Actor/AnalysisContext/JobDTO/ResultEnvelope，MVP-04/05 已实现认证与账号管理路由，MVP-06 已实现网络创建/列表/详情；MVP-07～10 已实现上传、任务、独立 worker 与快照初始化，MVP-11～15 已实现诊断文件、结果目录、设备接口、路由/LPM与虚拟traceroute分析；其余业务接口仍为拟实现契约，不是现有 Batfish REST 的重命名。网络/快照采用 UUID，SDK 内部名称由 service 维护。日期使用 UTC ISO 8601，前端转换为本地时间。

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
| GET /upload-limits | 已登录且完成改密的成员 | 200 当前max_bytes、max_expanded_bytes、max_files；无SDK调用 |
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

MVP-02 DTO 位于 `backend/app/contracts/dto.py`：所有字段拒绝未知项；模型及嵌套 JSON 参数不可变，序列化后仍是标准对象/数组。AnalysisContext 的内部名称字段为 engine_network、engine_snapshot、engine_reference_snapshot；引用快照 ID 和内部名必须同时有值或同时为空。JobDTO.kind 为 upload/initialization/analysis/deletion/fault_scenario；status 为 queued/running/succeeded/failed/cancelled/interrupted；engine_state 为 idle/busy/unknown。nullable 字段默认空，created_at 必填，所有日期必须有时区并归一为 UTC。ResultEnvelope 的 truncated=true 必须同时提供非空 truncation_reason。DTO 结构校验不替代 service 的可信身份、任务状态迁移和权限判断。

模块间固定服务入口：`AuthService.require_actor(session_token) → Actor`；`UsersService.get_identity(user_id) → UserIdentity`；`NetworksService.require_ready(actor, network_id) → NetworkDTO`；`UploadsService.consume(actor, network_id, upload_id) → UploadManifest`；`SnapshotsService.require_analyzable(actor, network_id, snapshot_id) → AnalysisContext`；`JobsService.submit(actor, kind, context, parameters, idempotency_key) → JobDTO`；`JobsService.claim(worker_id) → JobDTO | None`；`ResultsService.publish(context, payload) → ResultEnvelope`；`AnalysisService.submit(actor, context_ids, kind, request) → JobDTO`；`AnalysisService.execute(job) → ResultEnvelope`。诊断读取与配置查看不要求 require_analyzable，使用快照存在性校验。

SDK 边界方法：`SessionFactory.for_job(context)` 返回任务独占上下文；`AnalysisController.run(context, question_id, sdk_parameters) → StructuredAnswer`；`SnapshotController.initialize(context, upload_manifest, options) → InitializationAnswer`；`NetworkController.create/delete(engine_name)`；`SnapshotController.delete(context)`。StructuredAnswer/InitializationAnswer 只含普通类型、列 schema、警告及诊断，不含 requests.Response 或 SDK 实例。

快照初始化状态以 initialization_job_id 对应的任务为运行状态来源，快照 service 通过 JobsService.get(actor, job_id) 读取。初始化 queued/running 对应快照 queued/initializing；cancelled/interrupted/failed 对应快照 failed 并保留具体原因，不能永久显示 queued。重试初始化必须新建快照和任务，复用经校验的原始输入但使用新内部 SDK 名称；返回值同时包含新的 snapshot_id。禁止用通用重试直接覆盖旧快照。分析重试仍使用原快照，重新校验其可用性。

## 第二、三阶段接口增量

此表定义 advance spec 的对接契约；路由随对应 spec 验收后开放。所有 analyses 路由返回 202 JobDTO，并共用幂等、权限和结果读取规则。

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
| POST /comparisons/{id}/analyses/routes-diff | 复用 routes 的 nodes 与 options，返回 job；结果为 table，可分页/导出 | ADV-13 |
| POST /comparisons/{id}/analyses/reachability-diff | destination_ips、start_location；options 流量范围及 max_traces | ADV-14 |
| POST S/fault-scenarios | display_name；deactivate_nodes/deactivate_interfaces 至少一项；返回202 `{snapshot_id,job_id}` | ADV-16 |

ADV-16 的 `deactivate_nodes` 是精确设备名数组，`deactivate_interfaces` 是 `{node,interface}` 数组；空目标、重复目标或不存在的节点/接口返回422。可选 `Idempotency-Key` 限定同一用户、网络和基线下的重复创建；相同键及请求返回同一快照/任务，不同请求返回409。派生快照的 `base_snapshot_id` 指向不可变基线，内部名称全新；SDK `fork_snapshot(overwrite=false)` 在独立 worker 执行，任务完成并通过与普通初始化相同的质量门后才能用于 comparison。任务失败时快照显示 failed，任务保留错误代码；任何未删除派生快照都会阻止删除基线。接口只模拟配置快照故障，不操作设备。

GraphDTO 为 nodes[{id,label,properties}]、edges[{id,source,target,source_interface,target_interface,edge_type,properties}]、edge_type、source（SDK问题名）、scope、truncated。properties保留对应SDK原始行；节点id为快照内主机名，边id为视图与完整原始行规范JSON的SHA-256，方向、接口、IP与AS不同不合并。

ADV-01计算参数：`view` 默认 `layer3`，仅允许 `layer3/bgp/ospf/isis`；options仅 `nodes/remote_nodes`，复用 literal/expression 选择器。节点清单取两侧选择集合并集，任一侧未限制即包括所有节点，保留孤立节点。POST只入队，沿用身份/CSRF/幂等/上下文冻结/版本缓存规则；一个任务内顺序调用节点与边问题并复用同一Session。当前四视图统一标记requires_dataplane=true。

ADV-03 `POST S/analyses/bgp-sessions` 接受 `{}`；`options.mode` 默认 `status`，只允许 `status/compatibility`，分别固定映射公开问题 `bgpSessionStatus/bgpSessionCompatibility`。高级 `options.nodes/remote_nodes` 复用显式节点选择器，拒绝未列出的 status/type/context kwargs。结果为表格，列名、状态枚举及本地/远端节点、接口、VRF、AS、地址和其余 SDK 字段原样保留；模型推演的 `ESTABLISHED` 不等于现场会话健康。对 Huawei/H3C 输入额外标明 IPv6 BGP 会话未建模，空行或模型成功均不能证明该地址族状态。

ADV-05 `POST S/analyses/test-filters` 必须提供 `source_ip`、`destination_ip`（单个 IPv4 地址）及 `filters` 字面/表达式选择器；`nodes` 可选。`options.ip_protocols` 默认 `icmp`，仅开放 traceroute 已登记协议；`source_ports/destination_ports` 仅在协议全为 TCP/UDP 时可用。controller 固定调用 `testFilters` 和 `HeaderConstraints`，不接受任意 SDK 方法、起点、过滤器行为或上下文覆盖。结果保留 SDK `Action`、`Line_Content`、`Flow`、`Trace` 原始字段，另外标明 `Implicit_Deny`（仅对当前固定 SDK 的 `DENY + no-match + 空Trace` 判定）及 `Source_References`（仅收集 Trace 中真实的 vendorStructureId，不臆测行号）。未匹配过滤器返回空结果和“无放行/拒绝结论”，不解释为许可；Huawei/H3C 配置的 ACL 验证拒绝提交。ACL 局部动作不代表端到端可达。

`POST S/analyses/resolve-filters` 接受 `{}`（列出模型已解析 ACL）、可选 `nodes` 与 `filter_expression`，固定映射 `resolveFilterSpecifier`；默认过滤表达式为 `/.*/`。返回 SDK 结构化 `Node`、`Filter_Name` 表格及快照模型覆盖信息，仅用于选择，不用原始配置行猜测 ACL 列表。两个入口都经过任务/结果/缓存/身份/CSRF/版本约束。

ADV-07 `POST S/analyses/search-filters` 必须提供 `nodes` 和 `filters` 两个**字面值**选择器（各1～10项），以及 `options.headers.source_ip`、`destination_ip` 两个精确 IPv4 地址；不接受表达式或省略范围。`action` 默认 `permit`，只允许 `permit`、`deny`、`match_line`。`match_line` 必须同时提供非负的 `options.line_number`，其他动作不能提供该字段；controller 固定转换为 SDK 的 `matchLine N`。headers 可选 `ip_protocols`、`source_ports`、`destination_ports`，端口仅适用于全为 TCP/UDP 的协议列表。不暴露 `startLocation`、`invertSearch`、任意问题名或引擎上下文。`searchFilters` 返回范围内的示例 Flow、Action、Line_Content、Trace 和真实来源引用；0 行只表示当前 ACL/动作/报头条件下未找到示例，不是全网安全证明。

`POST S/analyses/filter-line-reachability` 同样要求 `nodes`、`filters` 字面值选择器各1～10项；`options.ignore_composites` 为严格布尔值，默认 `true`，固定映射 SDK `ignoreComposites`。结果原样保留 `Sources`、`Unreachable_Line`、`Unreachable_Line_Action`、`Blocking_Lines`、`Different_Action`、`Reason`、`Additional_Info`。`BLOCKING_LINES` 与 `INDEPENDENTLY_UNMATCHABLE` 含义不同，不把后者称为前序遮蔽；0 行不推导策略无风险。两个 ADV-07 操作均拒绝 Huawei/H3C ACL 模型验证，沿用任务、身份、版本、缓存、截断和结果读取约束。

图读取 `focus_node` 可选，默认 `hops=1`（范围0～5），默认 `limit=200`（范围1～200），无focus时hops不参与筛选。邻域按双向邻接取距离，但输出边保留SDK方向；未知focus返回404，读取非graph结果返回409。优先focus、再按距离及节点id排序；limit分别限制节点数与边数，不返回悬空边。scope包含focus_node/hops/limit/neighbor_direction、stored_nodes/stored_edges、matched_nodes/matched_edges、returned_nodes/returned_edges及storage_truncated。主动聚焦本身不算截断；读取限额或持久化限额丢弃数据时truncated=true，ResultEnvelope另含存储截断原因。

存储受table_rows（节点、边各自上限）与result_max_bytes限制；节点不足时同步排除相关边。计算过滤保存于effective_parameters，读取范围单独在scope返回，不改变缓存、不调用SDK。JSON导出包含完整已保存图与来源，graph不支持CSV。协议关系与会话健康不同；缺少边不能证明物理断线。

ComparisonDTO 包含 id、network_id、baseline_snapshot_id、candidate_snapshot_id、两侧内容摘要、引擎与 SDK 版本、统一的 engine_version/sdk_version、display_name、coverage、coverage_notes、created_by、created_at。比较创建不触发计算。两侧必须属于同一网络、不同且可分析，引擎或 SDK 版本不同返回409；解析警告、模型限制或配置格式差异使 coverage=limited，并明确提示。删除仅标记内部 deleted_at，已删除记录在列表/详情中不可见；仍保留审计和历史结果来源。后续差异分析中 candidate 映射 SDK snapshot，baseline 映射 reference_snapshot，提交时复核两侧摘要及版本。DiffResult 的 source 始终带 baseline/candidate，不用模糊的 before/after 位置代替真实 ID。路由 diff 保留两侧值及 SDK 原始标记；可达性 diff 按 flow 保存两侧 disposition/traces 及新增/消失方向。

ADV-12 `POST /comparisons/{id}/analyses/config-diff` 接受 `{}` 或 `{"options":{}}`，未知 options 拒绝；返回既有 JobDTO，支持幂等键、取消和重试。worker 仅比较已验证的原始上传文件，不调用 Batfish 问题；提交与执行均复核 comparison 的方向、摘要、版本和状态，缓存键包含两侧摘要及限额。结果 `kind=diff` 的 context.snapshot_id 是候选，context.reference_snapshot_id 是基线，effective_parameters.comparison_id 保留比较来源。`GET /results/{id}/diff/files` 按路径分页列出 added/removed/changed 的摘要：稳定 file_id、两侧 SHA-256/编码/字节数/行数、hunk_count、detail_truncated、warnings。`GET /results/{id}/diff/files/{file_id}` 分页返回差异块，`baseline_start/end` 与 `candidate_start/end` 是从 1 开始、结束位置不包含在内的行号区间，变更行各保留本侧原始行号与展示文本。相同路径匹配；不推断改名。同 SHA 文件不列出；原始字节不同即使标准化行结束后展示行相同也标 changed，并附 `DISPLAY_LINES_EQUAL_RAW_BYTES_DIFFER`。二进制、不可解码、超长行或限额情况以 `warnings`、`detail_truncated` 和结果级 `truncation_reason` 告知，不把缺失差异块解释为无变化。每侧文本详情最多 1 MiB/2000 行，每份结果最多处理 200 个文件及 8 MiB 文本详情，单文件最多 200 个变更块；结果存储还受通用行数/字节上限约束。文本差异不证明网络行为改变。

ADV-13 `POST /comparisons/{id}/analyses/routes-diff` 使用与单快照 routes 完全相同的有类型请求：`nodes` 可选，`options.vrfs/network/protocols/prefix_match_type/rib` 均可选；不允许传入 snapshot/reference、未知 SDK kwargs 或未登记的 RIB。任务固定候选→SDK snapshot、基线→SDK reference_snapshot，提交和执行时均复核比较上下文；幂等、缓存键包含两侧内容摘要及过滤条件。结果 `kind=table`，原有分页、过滤和 JSON/CSV 导出适用，`effective_parameters.comparison_id` 与两侧 ID 可追溯。每条结果保留 SDK `Entry_Presence` 以及 `Snapshot_*`（候选）/`Reference_*`（基线）原始字段，新增 `Change`：当前引擎实测 `Only in Snapshot`→`added`、`Only in Reference`→`removed`、`Changed`→`changed`；SDK 差异回答中附带的 `Unchanged` 行不列入变化结果。同一前缀的多条下一跳逐行保留，不按前缀覆盖。空结果仅表示所选节点/VRF/前缀/协议/RIB 范围内无模型路由差异，不构成策略等价或现场转发结论。结果仍受通用行数与字节上限约束。

ADV-14 `POST /comparisons/{id}/analyses/reachability-diff` 的最小请求为 `{"destination_ips":"10.64.0.4","start_location":"c1"}`。两个字段都必填；`destination_ips` 接受至多 16 个逗号分隔的规范 IPv4 地址或前缀，拒绝 `/0`，不能以空范围启动全网搜索。`options` 白名单为 `source_ips`（同样的 IPv4 范围）、`ip_protocols`（默认 ICMP，支持 ICMP/TCP/UDP/GRE/ESP/AH/OSPF/SCTP/IPINIP）、`destination_ports`（仅 TCP/UDP，0～65535）、`max_traces`（1～20，默认 5）；未知字段、快照/引擎上下文覆盖和非法类型返回 422。起点使用 SDK `PathConstraints.startLocation` 选择器语法；无效选择器在实际执行时返回有明确错误的失败任务，不解释成零影响。任务、缓存和历史沿用双快照比较约束。

结果为可分页、过滤、JSON/CSV 导出的 table。`Flow` 与 `Snapshot_Traces`/`Reference_Traces`、两侧 `TraceCount` 保留 SDK 原始证据；Snapshot 表示候选，Reference 表示基线。新增 `Candidate_Reachable`、`Baseline_Reachable`、两侧 dispositions、`Evidence_Truncated` 和 `Change`（`added`/`removed`/`undetermined`）。可达集合为 ACCEPTED、DELIVERED_TO_SUBNET、EXITS_NETWORK；若全部 trace 已返回且均非可达，才判不可达。截断且未见可达路径的一侧为 null，方向标 `undetermined`，结果 `truncated=true`、`truncation_reason=trace_limit`。`summary.count_scope=sdk_witness_rows_not_all_business_flows`，示例数及方向计数仅针对已存储的 SDK witness，不能推算全部业务流。空结果仅表示提交范围内未找到可达性差异；模型判断不是现场探测、回程证明或全网安全证明。

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

## MVP-11 诊断及文件契约补充

GET S/diagnostics 返回 `{items, offset, limit, total}`，默认50/最大200，severity限info/warning/error。每项包含source（四种公开问题之一）、severity、status（保留原枚举）、description、locations及raw。locations只关联manifest中的真实文件ID、路径及SDK明确给出的正整数行；无源行时为空，不推断第1行。queued/initializing返回409；失败/取消/中断后仍可读取已有诊断及输入，诊断为空不代表初始化成功。

GET S/files 返回 `{items: FileEntry[]}`，不包含存储目录；GET S/files/{file_id} 返回file_id/path/encoding/lines/offset/limit/total/warnings，offset从0计，lines.number从1计。默认50/最大200行，负数及超限422，跨快照ID404，超出末尾返回空页。支持原始UTF-8/GB18030，LF、CR-run及CRLF按引擎相同换行规则保持真实行号；二进制返回空文本和BINARY_CONTENT_NOT_DISPLAYABLE，单行展示最多64KiB并标注LONG_LINE_TRUNCATED，截断多字节字符时另标DECODING_REPLACEMENT。不更改原始字节；每次读取核对原始文件摘要。

质量规则应用于新初始化及既有快照读取：FAILED/UNKNOWN/UNSUPPORTED、Parse error/Convert error阻止分析，部分识别可分析但警告可见。quality_summary包含file_formats、model_limits及coverage。HUAWEI_VRP/H3C_COMWARE即使PASSED也标limited，明确IPv6/SRv6/EVPN转发未模拟、ACL正确性未确认；其他厂商未判定细粒度覆盖时标unknown，不能把PASSED翻译成全部能力完整模拟。后续analysis service还需按具体能力范围拒绝不支持的请求。

FileEntry.line_policy区分lf-v0旧清单及crlf-v1新清单。旧清单读取时从原始文件重新统计以修正历史仅计LF的行数；源行以SDK明确给出的正整数为准，不按旧清单计数裁剪。原始文件字节和内容摘要不变。

## MVP-12 能力目录及结果契约补充

GET /capabilities 要求登录，返回已登记能力数组；本篇 nodes/interfaces/routes/lpm-routes/traceroute 均disabled，专用接口在MVP-13～15逐项启用。options_schema来自对应严格Pydantic options模型，未知字段带安全字段路径返回422；仅装配登记的query callable，不接受调用者提供SDK方法或连接信息。

ADV-09 起每项能力还返回 `parameters_schema`，即该能力完整严格 Pydantic 请求模型的 JSON Schema；`required_fields` 与 `defaults` 供表单显示必要字段及预期有效默认值，`options_schema` 保留为高级选项子集。`POST S/analyses/query` 的请求为 `{question_id, parameters}`，其中 `question_id` 是 `/capabilities` 的能力 ID，而不是任意 SDK 问题或 Python 方法名。API 只校验外层结构；AnalysisService 将 `parameters` 送入同一 Registry 请求模型，沿用专用入口的快照权限、模型限制、任务幂等、结果缓存与 controller。未知/禁用能力分别明确拒绝；字段错误路径在专家入口以 `body.parameters...` 返回。客户端 JSON Schema 仅帮助填写，服务端严格复核始终生效。

GET /results/{id}返回ResultEnvelope；/rows返回columns/rows/offset/limit/total/truncated；/flows返回Flow摘要items；/flows/{flow_id}/traces返回结构化路径items、total（实际已存路径数）、trace_count（SDK报告总数）及truncated。分页默认50/最大200，稳定保留原始顺序；sort为登记列名，前缀“-”降序，数字按数值、文本按文本、嵌套值按规范JSON排序。filters是JSON编码数组，每项column/op/value，op只接受eq或contains，未知列/非法结构422。

RESULT_MAX_BYTES默认100MiB、TABLE_ROWS默认100000；持久化上限触发row_limit/byte_limit，SDK路径返回数不足总数标trace_limit。分页total表示已保存且筛选后的数量；原始行数在summary.total_rows，不能把输出截断解释为引擎计算受限。NaN/无穷转null，集合排序稳定，Flow/Trace/NextHop嵌套结构不字符串化。原始质量说明及厂商限制附着结果来源。

结果文件先原子发布，results元数据、缓存与job成功在共享数据库事务提交；发布或任务完成失败一起回滚，已落盘但数据库未引用的文件保留用于核对，不暴露为结果。worker在发布前后检查预算及引擎未知状态，原任务已中断时成功更新失败并回滚结果。缓存键包含完整上下文/版本/快照内容摘要/问题版本/有效参数和输出限额，命中仍新建当前用户job。旧任务缺少目录字段时明确409，不报内部异常。

worker在查询缓存前核对本次实际引擎及SDK版本。与快照记录不一致时返回CONFLICT，并在job.error.field_errors明确提示重新初始化；旧结果仍可读，不把升级后运行结果标记为旧版本，也不命中旧答案。

### MVP-13 设备与接口参数

两个 POST 分析接口接受 `{}`，默认精简列。nodes 的 `options.nodes`、interfaces 的顶层 `nodes` 与 `options.interfaces` 使用同一选择器：

- 字面名称：`{"mode":"literal","values":["r1","r2"]}`，1～100 个、每个1～255字符；按 Batfish 名称规则不区分大小写、完整匹配，不解释名称中的运算符。
- 专家表达式：`{"mode":"expression","expression":"/^r/"}`，1～4096字符；不接受混合模式或控制字符。
- 不传或传 null 表示不增加该项筛选。接口名筛选与节点筛选共同生效；接口名称不是文件路径。

`options.properties` 是非空属性白名单列表，具体枚举来自固定引擎的 NodePropertySpecifier/InterfacePropertySpecifier，并体现在 OpenAPI/capabilities。设备默认 Hostname、Configuration_Format、Interfaces；接口默认 Description、Active、Primary_Address、VRF。返回列使用 SDK 稳定字段名作 key、SDK 列说明作 label；保留结构化 Node/Interface 值及模型覆盖说明。正常无匹配返回成功、空 rows、稳定列，并附 `No matching rows`。属性中出现 IPv6/ACL 等信息只表示已解析模型属性，不证明具有对应仿真能力。

两类接口均要求写入身份/CSRF，支持 Idempotency-Key，使用不可变快照绑定的任务和结果；路由和 traceroute 继续由后续篇目启用。

分析 worker 使用已验证的公开后台查询/工作状态/答案读取能力，同一 SDK Session 内等待。引擎明确报告终止失败时，任务返回 `ENGINE_QUERY_FAILED` 和脱敏检查提示，释放串行占用，后续任务可继续；SDK 本地参数校验失败返回 `VALIDATION_ERROR`。等待超时、网络异常等无法确认引擎终态时，仍进入 `ENGINE_STATE_UNKNOWN` 并要求对账，不根据异常字符串猜测是否可以释放。

### MVP-14 路由与 LPM 参数

`POST S/analyses/routes` 接受 `{}`；nodes 可选且复用显式选择器。`options.network` 为严格IPv4 CIDR（不接受带主机位前缀），`protocols` 为非空协议/协议组枚举列表；`rib` 仅 main/bgp、默认main；`prefix_match_type` 为 EXACT（默认）、LONGEST_PREFIX_MATCH、LONGER_PREFIXES、SHORTER_PREFIXES。原始与默认补齐后的有效参数分别随任务保存，结果保留有效参数。

`POST S/analyses/lpm-routes` 只要求IPv4字符串 `ip`，可选nodes与options.vrfs。LPM仅main RIB，结果为Node/VRF/Ip/Network/Num_Routes，不补造Next_Hop；需要详情时使用明确Node/VRF和命中Network查询routes。

两类接口的 `options.vrfs` 同样使用 literal/values 或 expression/expression 形状；专家表达式在此是Java正则（例如 `^BLUE$`），不是带斜杠的节点选择表达式。字面VRF使用严格锚定正则；VRF名称按引擎大小写敏感规则匹配。未提供筛选表示全部，正常无命中是成功空表。

数据面分析执行期间JobDTO.phase为 `dataplane_or_query`（可能等待首次数据面计算或查询）；缓存检查阶段为 `checking_cache`，普通查询为 `querying`。这是应用阶段而非引擎百分比；只允许当前运行租约更新，已结束或已中断任务不可更新阶段。所有IPv6输入均在API校验时拒绝，不进入任务队列。

### MVP-15 虚拟 traceroute

`start_location` 为1～4096字符的Batfish location表达式，`destination_ip` 为单个IPv4字符串。options包括可选source_ip、ip_protocols（默认icmp；允许tcp/udp/icmp/gre/esp/ah/ospf/sctp/ipinip）、source_ports/destination_ports（0～65535整数列表，最多100项，必须仅选TCP/UDP）、max_traces（严格整数1～20，默认5）和ignore_filters（严格布尔，默认false）。AH在controller映射为引擎的AHP名称。候选协议/端口约束由SDK选择代表Flow，不表示枚举所有报文组合。

TraceFlow.dispositions按返回路径统计，保留实际headers与起点；Trace详情保留未知disposition/action字符串及嵌套hops/steps。ResultEnvelope.summary.dispositions只统计已保存且可读取的路径（disposition_scope=returned_traces），trace_count/returned_trace_count统计已保存Flow（trace_count_scope=stored_flows）；返回行数与总行数仍分别可见。maxTraces或行/字节限制触发时明确truncated，不从有限样本推断其余路径结论。

summary.ignore_filters及警告明确标注已忽略ACL；摘要同时保留单向模型推演、非在线探测、非回程证明和原快照模型覆盖限制。成功/拒绝/无路由分别按disposition计数，多种结论并存时不简化为全部可达。

已知终态失败后，经公开get_answer读取有限诊断文本并映射固定安全提示：没有活动起点提示start_location；不能推导源地址提示options.source_ip。底层堆栈/完整配置不返回、不持久化到普通日志。诊断文本不参与是否释放引擎的判断，未知工作仍按MVP-09对账规则处理。

MVP-18 增加只读上传限额查询，来源为当前部署Settings而非前端常量；身份经AuthService复验。OpenAPI二进制字段在前端生成时映射Blob，浏览器使用FormData携带实际文件并自动生成multipart boundary。

## MVP-22 保存结果导出

GET `/results/{id}/export?format=json|csv` 默认json；登录且完成密码更新的团队成员可读取共享结果，沿用结果鉴权。JSON下载是 `{metadata: ResultEnvelope, data: {columns,rows,flows}}`，覆盖全部已保存结果（不是页面筛选/分页），保留原始JSON值与模型限制/截断。CSV只允许table，否则409 CONFLICT；未知format为422。文件名仅 `batfish-<UUID>.<format>`，不接受路径。响应private/no-store、nosniff，迭代输出，不执行SDK。

CSV为UTF-8 BOM、标准引号与CRLF；表头 `record_type,metadata_json,data:<原始列key>...`。首个记录为metadata，第二字段包含完整ResultEnvelope JSON，其余空；后续record_type为data、metadata_json为空。对象/数组单元格采用紧凑JSON。公式前缀=+-@（包括前导空白/控制字符）和开头tab/CR/LF以单引号前缀保护，原始JSON导出不变。空表仍包含表头和metadata。当前加载有界保存文件（默认100MiB）后逐行/增量编码响应；不承诺超大文件常量内存。

## MVP-23 资源删除与对账

DELETE `/networks/{network_id}` 或 `/networks/{network_id}/snapshots/{snapshot_id}` 仅管理员，返回202 JobDTO。同一PostgreSQL队列事务边界内校验身份、资源状态及queued/running任务依赖（含reference_snapshot_id），标记deleting并入队；全局引擎unknown也返回409。网络必须已就绪且无未删除快照，不级联。网络创建重试、分析准入和快照初始化/重试同边界重读，防止迟到创建覆盖删除。NetworkDTO/SnapshotDTO增加可空deletion_job_id，固定当前删除任务。

删除不可取消或重试；远端按服务端保存名称通过公开SDK删除并确认不存在后才写deleted。数据库写回失败保留deleting和源文件，原结果始终可读/导出，来源UUID映射保留墓碑。已删网络常规GET为404；网络尚在时已删快照GET返回deleted，列表不显示、源文件404、历史初始化重试409。输入文件只在提交删除标记后且无其他未删快照manifest引用时清理，重试快照共用输入不会被提前清除。

POST `/admin/deletions/{job_id}/reconcile` 接受 `{note: 10..1000字符检查说明}`，仅管理员且原任务failed/interrupted。按当前deletion_job_id核对远端：存在则恢复原状态，不存在则补记deleted，无法确认保持deleting/引擎unknown；旧删除任务不能覆盖后续删除。检查不会重试删除。引擎unknown先按运行手册停旧worker、确认引擎空闲、完成全局引擎对账，再执行资源对账；历史interrupted记录保留。删除与资源对账写审计，说明保存到audit_events.note。对账返回 `{resource_id,state}`，原失败/中断任务保持历史状态。

## LDR-02 业务关注项

`GET/POST /api/v1/business-concerns` 与 `GET/PATCH /api/v1/business-concerns/{id}` 使用共享团队身份；GET 需登录，POST/PATCH 还需管理员、允许的 Origin 和当前会话 CSRF。列表可按 `network_id` 过滤，`offset` 默认 0、`limit` 默认 50/最大 200；默认不列出归档项，`include_archived=true` 可读取。单项 `GET ?version=N` 返回当时不可变版本，归档不影响历史读取。无网络或记录为 404，普通成员写入为 403，版本冲突为 409。

创建体最少为 `network_id`、`name`、`priority`（`high/medium/low`）及 1～10 条 `flows`；`description` 可选。每条流量要求 `start_location` 与单个规范目的 IPv4；`source_ip`、`protocol`、`destination_port` 可选，端口 0～65535 且必须与 TCP/UDP 协议共同指定。此映射不含快照 ID，也不代表自动推断业务依赖。PATCH 要求 `expected_version` 与至少一个修改字段；网络归属、创建者和版本不能从请求覆盖。`description=null` 明确清除说明，其他必要字段不可置空。创建返回 201/版本 1，每次成功修改（含归档）版本加一并保留历史内容、修改人和时间；写入与脱敏审计在同一事务。迁移 `0011` 保存当前记录与历史版本，后续检查才绑定就绪快照。

## LDR-04 跨网络总览

`GET /api/v1/leader/overview?offset=0&limit=20` 面向所有已完成首次改密的登录成员。`limit` 最大 200，`total` 是服务端全部未删除网络数，与当前页大小无关。`counts.network_states` 统计全部未删除网络的当前同步状态；`counts.snapshot_states` 统计全部未删除快照记录的持久状态；`counts.analysis_job_states` 统计历史 analysis 任务的终态/运行态。这三组口径不同，不相加为健康分。

每个网络卡返回最新未删除快照及最新就绪快照，按 `created_at DESC, id DESC` 稳定选择。`readiness=pending` 表示没有就绪快照，`warning` 表示就绪快照带解析警告或另有更新但未就绪的快照；`ready` 仅表示当前最新快照已完成初始化且无解析警告，不表示转发正确。`check_state=not_checked` 不制造结果；最近 analysis 任务仅从该卡的最新就绪快照中选取，失败/中断不算成功。`latest_result` 也只来自同一就绪快照，独立给出 `coverage`、`truncated`、`truncation_reason`、警告数与创建时间；它可能早于最近的失败任务，客户端必须分别标注时间与来源。`result_unavailable` 表示任务记录成功但无可读结果元数据。接口只查询已存 PostgreSQL 事实，不执行 SDK 或触发任务。
