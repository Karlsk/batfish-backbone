# Batfish Web 后端

MVP-02 提供 FastAPI 工厂、健康接口、统一错误、公共 DTO 和分层检查；MVP-03 增加 PostgreSQL 迁移、业务初始表及受控文件存储。Python 3.12；实际依赖由 `uv.lock` 固定，Pybatfish 为 MVP-01 实测的 `2026.9.17.3748`。

## 安装与启动

在 `web/backend` 执行：

```bash
uv sync --locked
uv run --locked uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000 --no-access-log --no-proxy-headers
```

访问 `/docs` 查看 OpenAPI 文档。配置数据库后提供认证与健康接口，尚无 worker 或分析入口。日志关闭默认访问记录，避免含敏感参数的 URL 被记录。默认禁用代理头，客户端不能自行声明限流来源地址；反向代理部署须另行明确可信代理边界。

| 接口 | 当前行为 |
| --- | --- |
| `GET /api/v1/health/live` | 200 `{"status":"alive"}`，不连接数据库或 Batfish |
| `GET /api/v1/health/ready` | 默认 503 `NOT_READY`；后续注入 database/worker/engine 状态生产者后，全部健康且未过期才返回 200 `{"status":"ready"}` |

每个 HTTP 响应都有服务端生成的 `X-Request-ID`；不采用客户端传入值。错误格式见 [API 契约](../docs/api-contracts.md)。

## 配置

通过进程环境变量读取，不自动加载 `.env`；不要打印完整配置或 Pydantic `ValidationError.errors()`，其中可能包含原始输入。

| 环境变量 | 默认值 / 约束 |
| --- | --- |
| `DATABASE_URL` | 创建持久化资源、运行迁移时必需，格式 `postgresql://…`；仅启动 live 健康接口允许不配置，不代表 ready |
| `BATFISH_HOST` / `BATFISH_PORT` | `localhost` / `9996`；端口 1～65535 |
| `BATFISH_API_KEY` / `BATFISH_TLS` | 空 / `false`；尚不创建 SDK Session |
| `SDK_REQUEST_TIMEOUT` | 120 秒，必须大于 0；后续 controller 显式传入 SDK |
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
