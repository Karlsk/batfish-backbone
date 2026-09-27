# Batfish Web 后端

MVP-02 提供 FastAPI 工厂、健康接口、统一错误、公共 DTO 和分层检查；MVP-03 增加 PostgreSQL 迁移、业务初始表及受控文件存储。Python 3.12；实际依赖由 `uv.lock` 固定，Pybatfish 为 MVP-01 实测的 `2026.9.17.3748`。

## 安装与启动

在 `web/backend` 执行：

```bash
uv sync --locked
uv run --locked uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000 --no-access-log --no-proxy-headers
```

访问 `/docs` 查看 OpenAPI 文档。配置数据库后提供认证、账号、网络、上传、任务与健康接口；独立worker另行启动，分析业务待后续实现。日志关闭默认访问记录，避免含敏感参数的 URL 被记录。默认禁用代理头，客户端不能自行声明限流来源地址；反向代理部署须另行明确可信代理边界。

| 接口 | 当前行为 |
| --- | --- |
| `GET /api/v1/health/live` | 200 `{"status":"alive"}`，不连接数据库或 Batfish |
| `GET /api/v1/health/ready` | database/worker/engine观测全部健康且未过期返回200；缺依赖、停止worker或观测过期返回503 `NOT_READY` |

每个 HTTP 响应都有服务端生成的 `X-Request-ID`；不采用客户端传入值。错误格式见 [API 契约](../docs/api-contracts.md)。

## 配置

通过进程环境变量读取，不自动加载 `.env`；不要打印完整配置或 Pydantic `ValidationError.errors()`，其中可能包含原始输入。

| 环境变量 | 默认值 / 约束 |
| --- | --- |
| `DATABASE_URL` | 创建持久化资源、运行迁移时必需，格式 `postgresql://…`；仅启动 live 健康接口允许不配置，不代表 ready |
| `BATFISH_HOST` / `BATFISH_PORT` | `localhost` / `9996`；端口 1～65535 |
| `BATFISH_API_KEY` / `BATFISH_TLS` | 空 / `false`；空key使用SDK默认值，会话仅由controller/factory创建 |
| `SDK_REQUEST_TIMEOUT` | 120 秒，必须大于 0；controller/factory显式传入SDK |
| `SDK_CONCURRENCY` | 固定 1 |
| `READINESS_MAX_AGE_SECONDS` | 60 秒，必须大于 0；状态缺失、过期或时间在未来均不 ready |
| `AUTH_ALLOWED_ORIGINS` | JSON 数组，如 `["https://batfish.example"]`；默认空，所有登录/写请求拒绝；只允许精确 HTTP(S) Origin，不允许通配符、路径或 null |
| `AUTH_COOKIE_SECURE` | 默认 true；仅本机 HTTP 开发时显式 false，生产通过 HTTPS |
| `AUTH_FAILURE_LIMIT` / `AUTH_FAILURE_WINDOW_SECONDS` | 默认 5 次失败 / 60 秒；按用户名和连接地址组合限制，保存在 PostgreSQL，跨进程生效 |

数据库 URL、引擎地址/端口和 API key 不进入配置 repr/model_dump。公共 DTO 拒绝未知字段，时间要求时区并输出 UTC，JSON 参数深层不可变；需要普通 JSON 时使用 `model_dump(mode="json")` 或 `model_dump_json()`。

## 测试

需要一并启动真实服务并使用 r1/r2、Cisco 四设备配置时，使用 [功能测试环境](../docs/test-lab.md)。该入口负责本机隔离服务、快照、上传 ZIP 和包含集成测试的全量回归。

```bash
uv run --locked pytest -m "not integration" -q
uv run --locked ruff check app tests
uv lock --check
```

首个命令显式选择无需引擎的测试；SDK 集成测试没有静默跳过逻辑。直接运行全部 `pytest` 时，必须准备隔离引擎环境变量，否则失败。

真实 SDK 验证沿用 [MVP-01 复现步骤](../docs/sdk-compatibility.md#复现) 创建全新临时引擎、版本清单和证据文件，然后使用本工程锁文件运行：

```bash
uv run --locked pytest tests/integration/test_sdk_baseline.py -q
```

每次使用新的 `BATFISH_TEST_EVIDENCE` 路径，测试完成后关闭本次引擎。不得连接团队生产网络。

当前 Starlette TestClient 对 httpx 发出一条弃用提示，不影响断言和实际 HTTP 验证；测试依赖随锁文件升级时再迁移。

## 分层

`api → service → controller → Pybatfish`，跨模块只允许 service 调用 service。`composition.py` 是装配例外；`contracts/` 不依赖业务模块，`infrastructure/` 提供配置和 HTTP 适配。健康模块没有 SDK 操作，因此没有空 controller。

`tests/architecture_rules.py` 通过 AST 检查绝对/相对/别名导入、跨模块 service 循环以及模块内动态导入；新增层或基础设施例外必须同时更新 [架构规则](../AGENTS.md) 与违规/合法样例测试。它是静态开发约束，不是运行时隔离沙箱。

## 持久化与文件发布

数据库版本通过 Alembic 管理。在受控环境注入 `DATABASE_URL` 后，于本目录执行 `uv run --locked alembic upgrade head`。初始迁移 `0001` 创建用户、会话、网络、上传、快照、任务、结果、审计和幂等记录；不可对团队数据执行测试降级。lab 启动会自动迁移自己的临时数据库；测试使用独立随机 schema，验证升级、降级重建、约束和模型一致性。

ORM 归各业务模块，composition 统一注册 metadata。repository 返回普通不可变记录或 DTO，不跨模块传递 ORM。`Database.transaction()` 提供事务句柄，跨模块协作仍通过 service；内部 repository 不自行 commit。SQLAlchemy 参数日志隐藏，但底层异常仍可能含约束值，不应直接作为 API 错误或日志输出。

`FileStore` 仅接受服务端生成的单层 storage key；根目录要求 0700、文件 0600。临时文件不可通过 read 读取，写入并 fsync 后使用不覆盖已有文件的原子发布；所有读写绑定已打开的目录，拒绝路径穿越和符号链接。禁止将 Batfish 内部卷作为根目录。

结果发布顺序：外层 `store.stage(key, bytes)`，内层 `database.transaction()` 中插入并 flush 结果元数据，调用 `pending.publish()`，随后退出事务提交。发布前失败会清理临时文件并回滚元数据；已发布文件不可覆盖。文件与 PostgreSQL 并非一个分布式事务：发布后崩溃、提交失败或提交结果未知可能留下未引用文件，不能盲目删除或声称成功；后续清理需先确认数据库引用。原子性不等于跨两种存储的同时提交。

真实数据库检查包含在 `lab.py verify` 中；可在已运行的隔离 lab 上设置 `BATFISH_LAB_MANIFEST` 为其 current.json 路径后，单独运行 `uv run --locked pytest tests/test_persistence.py -q`。该变量仅用于测试，不是生产数据库配置入口。

## 管理员初始化与认证

在迁移完成且数据库环境已注入后执行 `uv run --locked python -m app.bootstrap_admin`，交互输入用户名及至少 12、最多 128 字符的临时密码。密码通过 getpass 隐藏，不放入命令行参数；自动化可注入 `BOOTSTRAP_USERNAME` / `BOOTSTRAP_PASSWORD` 受保护环境变量。命令仅在不存在管理员时成功，数据库锁防止并发重复初始化，并记录脱敏审计。

认证路径均在 `/api/v1/auth`：`POST /login`、`GET /me`、`POST /password`、`POST /logout`。登录体为 username/password，响应包含 user_id、username、role、must_change_password 和 csrf_token。Cookie `batfish_session` 为 HttpOnly、SameSite=Lax、Path=/，默认 Secure、8 小时绝对过期；数据库只存 token 的 SHA256。密码使用 Argon2id。不存在、停用或密码错误均返回相同 401；达到失败阈值后返回 429，窗口结束后恢复。

登录要求 Origin；后续写请求同时要求相同白名单中的 Origin 与 `X-CSRF-Token`。缺 Origin 一律拒绝，包括脚本客户端。仅绑定当前会话的 CSRF 值有效；`me` 和登录响应设 `Cache-Control: no-store`。首次登录必须更换临时密码，只能访问 me/password/logout。改密成功返回 204、清 Cookie、撤销该用户所有会话；随后重新登录。退出后的旧 Cookie 即使重放也无效。

UsersService 每次查询实时身份与 session_version。改密增加版本并撤销会话；后续用户管理可以通过版本失效机制实现停用/重置撤销，避免 users 与 auth 相互依赖。会话和失败计数位于迁移 `0002`。数据库不可用不能认证成功；无 DATABASE_URL 的健康骨架不注册业务认证路由。

测试环境 `serve` 自动创建随机临时管理员，凭证仅保存在本次运行目录的 `auth.json`（0600）。真实 HTTP 冒烟会登录两个独立客户端、改密、检查旧会话失效、重新登录并退出，同时更新该受保护文件；可重复运行累计验收。

## 账号管理与审计

完成首次改密的管理员可通过 `GET/POST /api/v1/users`、`PATCH /api/v1/users/{id}` 和 `POST /api/v1/users/{id}/reset-password` 管理团队。列表默认 50、最大 200 项，返回 items/offset/limit/total；创建默认 member，要求 username 与 temporary_password，返回 201 用户；PATCH 只允许非空 enabled/role，返回用户；重置传 temporary_password，返回 204。用户响应不含密码哈希或会话版本。写请求沿用 Origin/CSRF。

管理 service 重新核对数据库实时身份，不信任请求声明的角色。停用/重置会使所有设备上的旧 Cookie 失效，重新启用也不会恢复旧 Cookie；角色变化在下一请求生效。重置后重新登录必须更换临时密码。

用户变更共用 PostgreSQL 事务锁，检查最后一个 enabled admin，禁止停用或降级该管理员（409）。自己停用/降级遵循相同规则：有其他有效管理员时允许，随后即时失去相应权限。并发操作不会使有效管理员数变成零。

创建、更新、重置和初始化记录 actor、action、resource、outcome、请求 ID 与时间。审计与成功变更在同一事务；审计失败时不提交业务变更。进入管理 service 的权限/业务拒绝记录 failed，HTTP 参数/CSRF 拒绝发生在调用 service 前。审计不存临时密码、会话或完整请求体；当前无审计查询页面。

## 共享网络与 SDK 占用

已改密的团队成员可 `POST /api/v1/networks`（body 仅需 display_name）、`GET /api/v1/networks` 和 `GET /api/v1/networks/{id}`。创建返回 201，列表返回 items/offset/limit/total，默认50、最大200；只列本应用管理的网络。内部名由 UUID 生成，显示名重复不影响身份；用户不可覆盖 engine_name、actor_id 或连接参数。

创建先提交 pending 映射，再调用独占 SDK Session 的公开 set_network，最后写 ready。可传 `Idempotency-Key`（1～128 个可打印 ASCII 字符），同用户、路由和资源作用域内同键/同请求复用原资源，不同请求返回409；至少保留24小时。API 会在成功/业务错误响应头回传有效键，未提供时生成。客户端应提前生成并保存键，尤其是需要处理断网且未收到任何响应的场景；普通忙碌503可使用收到的键重试。

sync_error 仅包含安全错误码。SDK 成功但资源数据库写回失败保留 pending/WRITEBACK_FAILED；同键重试用原内部名选择已有网络并完成写回。引擎忙碌时保留 pending/ENGINE_BUSY，返回503 NOT_READY，retryable=true。

数据库级 advisory lock 与持久 engine_slot 约束所有应用 SDK 工作；每次新建独占 Session，任务间不共享上下文。SDK 结果未知时保留 unknown，返回503 ENGINE_STATE_UNKNOWN、retryable=false。锁已释放但遗留 busy 也转 unknown，不能据此自动重放远端工作。迁移0003提供槽位和网络诊断字段；worker 与管理员对账入口在 MVP-09 接入，本篇不提供强杀或自动解除未知状态。正常 SDK 完成后释放占用，资源写回失败不等于引擎仍在计算。

MVP-06 在 jobs 模块增加最小幂等 service/repository，网络 service 通过其公共方法共享事务；任务队列与执行仍待 MVP-08/09，不把幂等记录误称为已实现后台任务。

## 配置上传与清理

`POST /api/v1/networks/{id}/uploads` 使用 multipart：多个 `files` 配置文件或一个 `archive` ZIP，二选一；带 Cookie、Origin 与 CSRF。返回201 UploadDTO及文件manifest，不初始化快照。网络必须ready，原始文件保持字节不变；文件ID、逻辑路径、SHA256、大小、编码与行数用于后续诊断。UTF-8/GB18030以外的内容保留并标记binary；不在日志/错误返回配置内容。

ZIP需要一个包含configs文件的快照根，允许该根下其他Batfish输入目录；拒绝穿越、绝对路径、链接、加密、嵌套ZIP、重复/文件目录冲突和多个根。多个普通文件自动包装configs。文件名大小写或Unicode规范化后的冲突均拒绝，实际文件以UUID保存，不用上传路径写磁盘。

服务端配置 `DATA_DIR`、`UPLOAD_MAX_BYTES`（100MiB）、`UPLOAD_MAX_EXPANDED_BYTES`（500MiB）、`UPLOAD_MAX_FILES`（5000）、`UPLOAD_TTL_SECONDS`（86400）。按实际流计数，multipart编码总开销另限1MiB。超字节上限413，格式/路径不合法422。上传目录0700、文件0600，默认开发数据目录为 `web/.runtime/data`；团队部署应指定专用持久卷。测试环境使用运行目录下的data。

UploadsService.consume仅所有者/管理员可调用，绑定网络、未过期且只能消费一次；行锁防止并发重复消费。尚无公开消费API，后续由快照service调用。已消费文件不按上传TTL清理。

在backend目录、注入DATABASE_URL与DATA_DIR后运行 `uv run --locked python -m app.cleanup_uploads`。它清理过期未消费记录及超过TTL的孤立暂存/发布目录，跳过已引用、新目录和链接。文件准备失败或DB flush失败清理暂存；DB提交结果未知时保留已发布文件，后续根据数据库引用清理，避免误删可能已提交的数据。文件卷与数据库无分布式事务，需按运行文档共同备份。

ZIP压缩算法支持 STORED/DEFLATED；其他算法及损坏压缩流受控返回422。

## 任务记录与排队取消

`GET /api/v1/jobs` 返回共享分页历史（items/total/offset/limit），可筛选status/network_id/created_by；`GET /api/v1/jobs/{id}` 返回详情。`POST /api/v1/jobs/{id}/cancel` 仅允许发起人或管理员取消queued且非deletion的任务，成功200 JobDTO，running/终态/删除任务409，越权403。写请求沿用Origin/CSRF，取消与领取通过行锁和原子条件更新互斥，不能把已运行任务显示为已取消。

业务模块经JobsService.submit持久化任务；本篇不提供任意任务/SDK方法提交HTTP接口。requested/effective参数与ExecutionContext冻结保存，后者包含服务器资源映射及版本；JobDTO新增context和retry_of（兼容旧记录可空）。迁移0004添加上下文与重试父任务引用；实际重试由MVP-09接入，旧任务不复活。

幂等作用域为用户、kind与网络/快照/引用快照，同键同规范化请求返回同任务，不同内容409。新任务和幂等记录同事务；默认`MAX_QUEUED_JOBS_PER_USER=10`、`MAX_QUEUED_JOBS_GLOBAL=100`，达到上限429且不留下半条记录。并发提交通过短事务锁核对限额，已存在的幂等重放不消耗新名额；不把排队限额当作引擎执行并发。MVP-08仅任务元数据，尚无worker，不能宣称后台计算完成。

## 独立 worker 与未知占用恢复

迁移0005后在独立进程运行 `uv run --locked python -m app.worker`，使用与API相同的DATABASE_URL、DATA_DIR和Batfish连接配置。单worker进程锁和任务原子领取共同防止重复执行；误启动第二worker会退出。dispatcher只使用composition登记的业务service handler，未登记操作明确失败；快照/分析业务handler由后续MVP接入，MVP-09没有把虚拟handler当作分析结果。

默认心跳10秒、失联阈值60秒、轮询1秒、空闲SDK版本探测30秒、任务等待预算1800秒；对应 `WORKER_HEARTBEAT_SECONDS`、`WORKER_STALE_SECONDS`、`WORKER_POLL_SECONDS`、`ENGINE_PROBE_SECONDS`、`JOB_WAIT_BUDGET_SECONDS`。worker在执行前重新读取发起人身份；停用或必须改密时不调用handler。SIGTERM/SIGINT停止领取，当前任务收敛前继续心跳；外部强制终止会在后续扫描中形成interrupted/unknown。

超预算、失联及SDK结果未知不等于引擎已经停止。unknown阻止后续调度；状态进入SDK及完成时使用条件更新，迟到完成不能自行解除unknown。处理方式：停止旧worker，检查Batfish诊断/必要时受控重启并确认空闲，然后管理员调用 `GET /api/v1/admin/engine` 和 `POST /api/v1/admin/engine/reconcile`（resolution为confirmed_idle/restarted，note为5～1000字处理依据，需Origin/CSRF）。对账同事务取得worker和引擎锁、写处理记录与审计，再解除unknown；有活跃worker/SDK或审计失败时不解除。随后重新启动worker、由用户决定重试，不自动重放。

`POST /api/v1/jobs/{id}/retry` 返回202新JobDTO，支持Idempotency-Key；仅发起人/管理员可重试failed/interrupted/cancelled且有登记重试handler的任务，删除/成功/运行中任务拒绝。新记录通过retry_of关联旧记录，旧记录不改写；业务handler重新校验资源，初始化新建快照由MVP-10负责。引擎未知时禁止重试；尚未登记的未来业务明确409。

ready现读取真实数据库和最近worker/引擎观测；停止worker、观测过期或引擎unknown时503。健康请求本身不调用SDK。引擎忙碌期间复用上次探测，过期时保守不ready。

## 快照初始化、诊断与文件（MVP-10/11）

迁移至head（0006）后，上传得到upload_id，再调用 `POST /api/v1/networks/{id}/snapshots`，提交display_name、upload_id和可选options，返回202的snapshot_id/job_id。options仅支持布尔ignore_management_interfaces（默认true）和parse_reuse（默认false）。独立worker已注册初始化handler；每次新建不可变SDK快照，质量门通过才可分析。任务取消/失败/中断对应快照failed；通过任务retry入口创建新快照及任务。

`GET /api/v1/networks/{id}/snapshots/{snapshot_id}/diagnostics` 提供四类诊断分页；`/files` 列出原始文件；`/files/{file_id}` 按行分页（offset从0计、默认50、最大200）。只返回原始逻辑路径，不暴露磁盘目录。支持UTF-8/GB18030及LF/CR/CRLF换行，缺失源行不推断；超长行与二进制有明确说明。H3C/Huawei模型限制独立于解析PASSED展示；UNKNOWN/UNSUPPORTED等状态禁止分析。具体业务分析handler从MVP-13起加入。

## 能力目录与标准结果（MVP-12）

迁移0007增加版本化结果缓存；`GET /api/v1/capabilities` 显示已登记能力及开关，本篇具体查询仍禁用。`GET /api/v1/results/{id}`、`/rows`、`/flows`、`/flows/{flow_id}/traces` 提供已存结果及分页，默认50/最大200。嵌套Flow/Trace/NextHop保留结构，空结果、截断、模型限制分别表达。`RESULT_MAX_BYTES` 默认100MiB、`TABLE_ROWS` 默认100000，仅限制Web持久化输出。

analysis handler支持执行和发布两个阶段；结果元数据、缓存和任务成功共同事务提交，发布失败/中断不暴露新结果。缓存命中仍生成当前用户的任务。执行前核对实际SDK/引擎版本，与快照初始化版本不同则要求重新初始化；旧结果保持可读。原子文件发布后数据库提交不确定可能保留未引用文件，需要按备份/清理设计核对，不能直接当作有效结果。

## 当前进阶分析接口

已登记的 `POST /api/v1/networks/{network_id}/snapshots/{snapshot_id}/analyses/bgp-sessions` 接受 `{}`（默认模型状态）或 `{"options":{"mode":"compatibility"}}`。可选 `options.nodes/remote_nodes` 为现有字面/表达式节点选择器；不接受任意 SDK 方法、状态或类型参数。结果沿用任务轮询和 `/results/{id}/rows`，完整保留 SDK 原始列与状态，并标注这是配置模型推演。Huawei/H3C 输入额外提示 IPv6 BGP 会话未建模；空表及模型 `ESTABLISHED` 均不证明现场会话情况。

ADV-05 增加 `POST /api/v1/networks/{network_id}/snapshots/{snapshot_id}/analyses/test-filters`（必需源/目标 IPv4、过滤器选择器，可选节点和有类型协议/端口）与同作用域 `resolve-filters`（可选节点/过滤器表达式）。前者仅评估局部 ACL，保留 SDK 原始动作、命中行、Flow 与 Trace，并额外提供隐式拒绝和实际可用的来源引用；找不到过滤器绝不当作放行。Huawei/H3C ACL 转换未验证，测试接口返回409及字段解释；辅助列表仍带模型覆盖标记。两者都返回任务，结果沿用现有分页 API，不向浏览器公开 SDK 会话。

## 领导端业务关注项（LDR-02）

迁移 `0011` 增加网络级业务关注项当前表与不可变版本表。`GET/POST /api/v1/business-concerns`、`GET/PATCH /api/v1/business-concerns/{id}` 提供共享读取、管理员维护、归档及历史版本读取。请求只接受有类型的名称、重要程度和 1～10 条显式关键流量；修改须提供 `expected_version`，冲突返回 409。API 不调用 SDK；业务模块通过 NetworksService 核对网络，版本写入和审计同事务。完整字段见 [API 契约](../docs/api-contracts.md#ldr-02-业务关注项)。

## 领导端跨网络总览（LDR-04）

`GET /api/v1/leader/overview?offset=0&limit=20` 对已登录成员提供最多 200 项的分页网络卡与服务端全量总数。卡片区分最新快照和最新就绪快照，分析任务和结果只绑定后一来源；无结果返回“未检查”，结果保留覆盖与截断警告。汇总计数明确区分当前网络、未删除快照记录和历史分析任务，均不代表业务健康分。leader service 仅调用各来源 service 的批量只读投影，不直接调用 SDK；详见 [API 契约](../docs/api-contracts.md#ldr-04-跨网络总览)。
