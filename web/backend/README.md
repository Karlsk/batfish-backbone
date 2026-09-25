# Batfish Web 后端

MVP-02 提供 FastAPI 工厂、健康接口、统一错误、公共 DTO 和分层检查；MVP-03 增加 PostgreSQL 迁移、业务初始表及受控文件存储。Python 3.12；实际依赖由 `uv.lock` 固定，Pybatfish 为 MVP-01 实测的 `2026.9.17.3748`。

## 安装与启动

在 `web/backend` 执行：

```bash
uv sync --locked
uv run --locked uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000 --no-access-log
```

访问 `/docs` 查看 OpenAPI 文档。当前仅有健康接口，尚无登录、worker 或分析入口。日志关闭默认访问记录，避免后续含敏感参数的 URL 被记录。

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
