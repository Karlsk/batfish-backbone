# 本机功能测试环境

目标：实际运行 Batfish、FastAPI 和 PostgreSQL，使用两套配置快照验证 Web 功能链路。设备均为配置文件输入，无需真实设备、虚拟路由器或厂商镜像；不做设备实测与仿真结果的一致性验证，后者属于 Java 核心范围。

当前已接入MVP-03～20的数据库、认证、网络、上传、任务、独立worker、快照、诊断及五类分析API，以及账号/网络/快照/任务/诊断页面。两套配置经过真实上传初始化和分析API，浏览器验证页面流程；SDK基线保留兼容性回归。设备/接口/路由/LPM页面已有双拓扑浏览器验收；逐跳路径、导出、删除与部署验收继续按后续spec执行，不得将当前结果标为MVP-25验收完成。

## 服务和隔离

| 服务 | 本机地址 | 版本/用途 |
| --- | --- | --- |
| Batfish | 127.0.0.1:19996 | 本仓库已验证 JAR，独立存储，不连接其他引擎 |
| FastAPI | http://127.0.0.1:18000 | 当前工作树中的应用，文档入口 `/docs` |
| PostgreSQL | 127.0.0.1:15439 | 固定 postgres:17-alpine 镜像摘要，独立临时容器 |

`web/scripts/lab.py` 固定 MVP-01 的引擎 revision/JAR SHA-256，启动前核对摘要；固定 PostgreSQL 镜像摘要。版本变更需重新验证来源，不能随意忽略摘要检查。需要已构建 JAR、Java 25、Docker 及 `web/backend` 的锁定 Python 环境。Python 脚本使用 POSIX 文件锁，支持本项目当前 macOS/Linux 开发环境。

默认端口已避开本机现有服务。冲突时明确失败，可通过 serve 的 `--engine-port`、`--api-port`、`--database-port` 指定空闲端口；不会接管或停止占用端口的其他服务。

仅监听 127.0.0.1。PostgreSQL 数据为临时 tmpfs，停止后清空；每次 serve 都是新实例，适合空库迁移与功能测试，不是团队持久部署。账号为 batfish_test，密码随机生成，只保存在忽略提交且权限受限的运行目录。`database.env` 供后续迁移/worker 测试读取，不输出其内容到日志。

## 两套配置

| 名称 | 配置来源 | 设备与用途 |
| --- | --- | --- |
| r1-r2 | [现有 r1](../backend/tests/fixtures/small_network/configs/r1.cfg)、[r2](../backend/tests/fixtures/small_network/configs/r2.cfg) | Huawei/H3C，单链路、静态路由、两台设备 |
| cisco-four | [拓扑与地址表](../backend/tests/fixtures/cisco_four/README.md) | Cisco IOS，c1/c2/c3/c4，OSPF 菱形双路径 |

两套快照使用独立 network；名称带本次 run ID，snapshot 名称带输入内容摘要。重复 seed 复用未改变的快照；修改输入会创建新快照，始终 overwrite=false。两个独占 Session 交错查询，检验两个快照的结果不会串用。

## 启动、导入和验证

在仓库根目录执行一次安装，然后保持服务终端运行：

```bash
uv sync --locked --project web/backend
web/backend/.venv/bin/python web/scripts/lab.py serve
```

在第二个终端、同一仓库根目录执行：

```bash
web/backend/.venv/bin/python web/scripts/lab.py seed
web/backend/.venv/bin/python web/scripts/lab.py status
web/backend/.venv/bin/python web/scripts/lab.py smoke
web/backend/.venv/bin/python web/scripts/lab.py verify
```

- `serve`：启动并监管三个服务，对本次临时 PostgreSQL 执行 Alembic 升级并初始化随机测试管理员；凭证仅在运行目录 `auth.json`（0600）。只允许一个管理进程。Ctrl-C 关闭本次 API/JVM 和本次 PostgreSQL 容器，不影响其他容器。
- `seed`：导入/选择两套不可变快照，生成可用于上传页面的 `r1-r2.zip` 和 `cisco-four.zip`。
- `status`：读取实际 API/引擎 HTTP 状态及快照身份，不展示数据库密码。
- `smoke`：API live、真实数据库迁移版本、两套快照节点清单，以及真实 HTTP 双会话登录/改密/撤销/退出及创建/停用/启用/重置成员、创建/重放/共享查询网络；显式只运行 smoke 标记测试。改密后同步更新受保护测试凭证，支持重复运行。
- `verify`：当前后端全部测试，包含单元测试、分层检查、原 MVP-01 SDK 基线及两套快照集成测试；不排除 integration、不允许缺环境时静默跳过。

seed/smoke/verify 使用同一排他锁，防止多个入口同时向引擎提交工作。手动 SDK 操作也应保持串行。每次 verify 生成全新证据目录，SDK 基线会创建独立随机名称的测试网络，不覆盖 seed 的快照。

环境清单位于 `web/.runtime/test-lab/current.json`；其中包含本次运行目录和 ZIP 路径。日志、引擎数据、SQL连接文件、JUnit、原始 SDK 证据均保存在该运行目录，整个 `.runtime/` 被 Git 忽略。每轮需要交付的脱敏摘要单独复制到 `web/docs/evidence/`。

只运行不依赖服务的单元测试时：

```bash
cd web/backend
uv run --locked pytest -m "not integration" -q
uv run --locked ruff check app tests ../scripts/lab.py
```

## 测试边界及后续累计回归

当前检查覆盖：合法配置解析/诊断、节点与接口查询、routes/LPM 查询、结构化 traceroute、上下文隔离、原始输入打包和配置身份、并发测试入口排他。这些是已知合成输入下的功能断言，不采集真实设备路由或对照实际报文转发。

MVP-09已接入真实观测：正常运行且观测新鲜时ready=200；累计测试暂停worker期间ready=503。独立worker生命周期冒烟覆盖启停后的200/503，仍保留MVP-02依赖缺失或过期不能假绿的测试。

| 后续阶段 | 两套配置如何进入验收 |
| --- | --- |
| MVP-03～09 | 已加入真实 PostgreSQL 迁移/事务、认证、账号管理与真实 SDK 网络创建；MVP-07 已加入两套配置真实 HTTP 上传与字节/摘要核对；MVP-08已加入真实HTTP任务历史/取消、数据库限额与并发；MVP-09已加入独立worker、真实SDK探测/进程终止恢复和unknown对账 |
| MVP-10～15 | 通过 Web API 上传同一 ZIP，初始化、查询诊断、节点/接口、routes/LPM、traceroute；对应用字段与来源做检查 |
| MVP-16～21 | 页面可运行后添加浏览器测试，执行上传、快照选择、基础/高级参数、详情和刷新；页面变更补视觉检查 |
| MVP-22～25 | 加入导出、删除互斥、本机完整部署与双用户闭环；两套配置均纳入累计回归 |

MVP-16起已有前端及真实浏览器测试，MVP-17增加真实双用户认证。前端在15173端口同源代理API，实验环境显式允许该Origin且不绕过CSRF。后续流程要求“当前 MVP + 之前所有 MVP 验收通过才 commit”，这里提供环境和当前后端检查入口，前端/部署检查需随所属 spec 明确接入，不能只保留后端 pytest 就声称全部回归通过。

## 本次实测记录

2026-09-25，代码基于已提交的 MVP-02；结构化记录见 [测试环境基线](evidence/test-lab-baseline.json)。

- Python 3.12.12、Pybatfish 2026.9.17.3748、PostgreSQL 17.10；JAR 与 MVP-01 摘要一致。
- 实际执行 serve → seed → smoke → verify；首次环境关闭后重新 serve，连续两次 seed 均使用相同内容快照名，没有 overwrite。
- 最终 `lab.py verify`：69 passed，0 failed/error/skipped，9.10 秒；其中 52 项无服务单元/分层检查、17 项真实服务集成检查。
- 最终 `lab.py smoke`：3 passed，0.90 秒；显式不运行其余 66 项。3 项均包含在上述完整回归中，不重复计算为新增测试。
- `uv lock --check --offline`、Ruff、格式检查、`git diff --check` 和变更 Markdown 本地链接检查通过。测试有 1 条现有 Starlette/httpx 弃用提示。
- live=200、ready=503、OpenAPI=200；数据库确认仅映射到 127.0.0.1:15439。本轮留下环境运行，API 地址为 http://127.0.0.1:18000。
- 未运行浏览器、未接入尚未实现的应用业务入口、未采集/对照真实设备，未修改 Java 引擎或推进 MVP 完成状态。

## MVP-09 worker 协调

serve现在启动独立worker并迁移0005，manifest记录worker_pid。seed/smoke/verify先向本轮manager请求优雅停止其worker并等待确认，防止SDK基线直接调用与后台探测重叠；超时则拒绝并发运行。命令结束后manager重新启动worker。这个控制只管理本轮测试进程，不作用于其他环境。

真实worker冒烟在暂停期间启动独立子进程，验证心跳/真实SDK版本探测、ready=200、第二worker被拒绝、优雅退出后ready=503。进程恢复测试使用独立schema、真实SDK GET后在持久完成前SIGKILL，确认interrupted/unknown及阻止领取；它证明Web恢复约束，不宣称完成了尚未实现的快照/分析业务。MVP-08任务元数据冒烟在worker暂停时验证queued/cancel语义，保留原验收覆盖。

## 前端累计验证

后端verify结束且worker恢复后，在 `web/frontend` 执行 `pnpm test`、`pnpm check:api`、`pnpm typecheck`、`pnpm build`、`pnpm format:check`、`pnpm test:e2e`。Playwright自启动15173开发服务器并在结束后关闭；不要同时手动占用该端口。初次运行先 `pnpm exec playwright install chromium`。浏览器读取当前实验清单下的auth.json，不在文档/仓库写密码；失败trace可能含测试凭证，必须留在忽略提交的运行目录。

MVP-18起浏览器将向真实worker提交两套配置的初始化任务，因此浏览器验收与直接SDK/后端累计测试串行执行，避免争用单引擎。
