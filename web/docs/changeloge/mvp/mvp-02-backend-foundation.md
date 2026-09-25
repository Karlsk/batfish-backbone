# MVP-02 后端骨架与分层约束

- 状态：已完成
- 阶段：1
- 依赖：[MVP-01](../mvp/mvp-01-sdk-compatibility.md)
- 预计工作量：1.0 人天（实现/验证 0.5 + 测试 0.25 + 文档/自检 0.25），依赖就绪后计；超过 2 人天先拆分。
- 共享约束：[架构](../../architecture.md)、[API 契约](../../api-contracts.md)、[前端规范](../../frontend.md)、[运行设计](../../operations.md)、[验收](../../validation.md)。

## 需求与目标

建立可启动、可测试、层次清晰的 FastAPI 工程。

- 独立 Python 依赖与锁文件、应用配置、健康接口、统一错误、公共 DTO。
- 导入约束测试；明确 controller 命名和 composition 装配例外。

## 设计与接口

- 版本输入以 [MVP-01 实测报告](../../sdk-compatibility.md) 为准：Python 3.12、Pybatfish 2026.9.17.3748；不可安装文档版本号 `pybatfish==0.36.0`。本篇生成应用锁文件。

- GET /api/v1/health/live 返回存活；GET /api/v1/health/ready 仅在依赖就绪后 ready（沿用共享前缀）。
- 错误对象统一 code/message/field_errors/request_id/retryable。
- 公共契约遵循 api-contracts.md；不在 api/service 导入 pybatfish。

沿用 api → service → controller；所有跨业务模块调用经过 service。非 SDK 存储由本模块 repository 负责。浏览器不接触 SDK 会话或连接参数。

## 预期改动位置

已实现以下基础路径，完整启动/配置/测试说明见 [后端 README](../../../backend/README.md)：

- `web/backend/pyproject.toml`
- `web/backend/app/main.py`
- `web/backend/app/composition.py`
- `web/backend/app/contracts/`
- `web/backend/app/infrastructure/settings.py`
- `web/backend/tests/test_architecture.py`

## 实施步骤

- [x] 建立最小包与开发测试命令，依据兼容性报告锁定 SDK。
- [x] 定义 Actor、AnalysisContext、JobDTO、ResultEnvelope 和异常类型。
- [x] 实现健康路由、错误映射、request_id；敏感配置不参与日志输出。
- [x] 添加禁止跨模块 repository/controller 导入及跨层 SDK 导入的检查。
- [x] 运行下述验证，记录实际命令与结果，更新本文及索引状态。

## 测试与验收

- test_live_without_batfish：引擎不可用不影响 liveness。
- test_error_shape：校验错误保持字段路径，无堆栈/凭证。
- test_import_boundaries：故意违规的小样例能被约束检测。

后端测试在 `web/backend` 下使用 `uv run pytest` 指定上述测试文件；集成测试连接版本固定的隔离 Batfish 测试网络，不操作团队生产网络。

验收成功同时要求：契约与文档一致、失败行为可解释、无跨层/跨模块越界、没有把 mock 验证宣称为真实 SDK 验证。共享约束中的身份、版本、模型覆盖和结果截断规则均适用。

## 非目标与实施边界

- 不实现账号、数据库业务表或分析执行。

## 完成记录

完成日期：2026-09-25。证据：[MVP-02 验证记录](../../evidence/mvp-02-backend-foundation.json)，计划与决策：[实施计划](../../plans/mvp-02-backend-foundation.md)。

- `web/backend/pyproject.toml`、`uv.lock`、`.gitignore`、`README.md`：独立 Python 3.12 工程、固定依赖、配置及开发命令。
- `app/main.py`、`composition.py`、`infrastructure/settings.py`、`infrastructure/http.py`：工厂启动、依赖装配、环境配置、统一错误和服务端请求 ID；校验输入/异常消息不进入错误和普通日志。
- `app/contracts/{base,dto,errors}.py`：公共 DTO、深层不可变 JSON、UTC 时间、错误类型；`modules/health/{api,service,schemas}.py`：存活与依赖快照新鲜度判断，无 SDK 操作，未创建空 controller。
- `tests/test_foundation.py`、`test_architecture.py`、`architecture_rules.py`：健康、脱敏、请求关联、DTO、绝对/相对/别名导入、跨模块 service 循环及动态导入检查；MVP-01 测试新增 integration 标记，显式区分需引擎的验证。

实际验证（除来源核对外，工作目录均为 `web/backend`）：

1. 先编写测试，应用尚未实现时收集失败：缺少 `app` 和 `tests.architecture_rules`；实现后目标 47 项全部通过。
2. `.venv/bin/python -m pytest -m 'not integration' -q --junitxml=/private/tmp/batfish-mvp02-aw54q7ok/unit-pytest.xml`：47 passed，显式排除 7 项集成测试，0 failed。Starlette/httpx 有 1 条上游弃用提示，不是测试跳过。
3. `.venv/bin/ruff check app tests`、新建 Python 文件的 `ruff format --check`：通过。`uv lock --check --offline`、`uv sync --locked --offline`：通过，43 个解析包，40 个当前平台安装包；首次受缓存权限限制，获准访问已有缓存后完成验证。
4. 临时本机启动 `.venv/bin/python -m uvicorn app.main:create_app --factory --host 127.0.0.1 --port <空闲端口> --no-access-log`；通过真实 HTTP 检查 live=200、ready=503、未知路径=404、OpenAPI=200，均有请求 ID；随后关闭 API 进程。
5. 复用 MVP-01 的精确 JAR（SHA-256 `0927de7c740bc72f999870e842605baad9a7cb6ea66e4b01fb9a6037bea00193`），核对引擎源码/问题模板无变更，使用全新隔离存储和本机空闲端口启动；按兼容性报告设置 BATFISH_TEST_* 后运行 `.venv/bin/python -m pytest tests/integration/test_sdk_baseline.py -q --junitxml=/private/tmp/batfish-mvp02-aw54q7ok/sdk-pytest.xml`：7 passed，0 skipped，6.79 秒。保留引擎 revision `7d0deeeac4a09973b3876327f6aef721ee12f955`，Python 3.12.12、Pybatfish 2026.9.17.3748；此次未重建/修改 Java。测试进程及引擎已关闭。
6. 独立审查完成，无需修复项；另行验证 47 项通过。`git diff --check` 和变更文档本地链接检查通过。

实施决策与限制：当前状态生产者尚未接入，ready 默认 503；注入状态接口将在持久化/worker spec 接入，不能用固定绿灯代替依赖探测。DATABASE_URL 在骨架中可空，持久化接入后成为必需。普通日志只记异常类型/请求 ID，受控堆栈采集留给后续运行设计。静态导入检查是研发约束，不是任意 Python 代码沙箱。当前 TestClient 的 httpx 弃用提示留待测试依赖升级处理。

本篇验收已满足，MVP-03 的后端骨架前置就绪；账号、业务表、worker、分析与前端尚未实现。没有自动进入下一篇或提交 Git。
