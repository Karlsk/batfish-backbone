# MVP-02 实施与验证计划

日期：2026-09-25。依据：[MVP-02](../changeloge/mvp/mvp-02-backend-foundation.md)，前置 MVP-01 已提交并保存 7 项实测证据。

本会话按 writing-plans / executing-plans 方法完成本篇，已有范围内直接推进；不提交、不实现账号、业务表或分析执行。

## 交付与验证顺序

- [x] 依赖：`web/backend/pyproject.toml`、`uv.lock`，Python 3.12，Pybatfish 固定 MVP-01 版本；开发依赖使用 pytest/httpx/ruff。
- [x] 先写行为测试：live 不访问 SDK，ready 缺失/过期/失败不假绿；422/404/500 的固定错误信封、字段路径与 request_id；错误和配置不泄露输入/凭证。
- [x] 公共契约：Actor、AnalysisContext、JobDTO、ResultEnvelope 与错误类型；拒绝未知字段、非 JSON 参数、无时区时间；任务参数深层冻结并能序列化。
- [x] 应用：`app/main.py` 工厂、`composition.py` 装配；基础设施 settings/http；`modules/health/api.py` 只映射 HTTP，`service.py` 判断就绪。无 SDK 操作，不造空 controller。
- [x] 导入约束：AST 检查绝对/相对/别名导入、跨模块仅 service、SDK 仅 controller/SDK factory、反向依赖和循环；用违规小样例证明检查有判别力。
- [x] 验证红灯后完成最小实现；运行目标 pytest、ruff、锁文件一致性及临时本机 HTTP 启动烟测；用新锁文件复跑 MVP-01 真实 SDK 基线。
- [x] 独立审查、修复实际问题后复验；回写 spec、索引和启动文档。

接口以共享 `/api/v1` 前缀为准：`/api/v1/health/live`、`/api/v1/health/ready`。ready 读取注入的依赖状态快照（数据库、worker、引擎），要求三者都健康且未过期；MVP-02 默认未接入，因此返回 503。后续持久化和 worker spec 负责状态生产者，本篇不伪造它们。

关注：未处理异常和 Pydantic 输入不能泄密；错误响应也有请求 ID；就绪状态过期与 provider 异常必须失败关闭；frozen 模型的嵌套参数不能被篡改；导入检查不能只扫描关键字而漏掉相对导入。

## 完成记录与实施决策

2026-09-25：测试先红（缺少 app/architecture_rules），实现后 47 项通过；真实 HTTP 启动检查 4 个响应通过；新锁文件真实 SDK 回归 7 项通过、0 跳过。ruff、离线 lock/sync 检查通过。独立审查无修复项。具体命令和证据见 MVP-02 spec。

- Ruling：ready 使用注入的观测快照，默认 503 — 本篇明确排除数据库/worker 业务实现，不能伪造 ready；代价是后续接入状态生产者之前无法用 readiness 判定完整系统可用。
- Ruling：DATABASE_URL 在骨架可空，MVP-03 接入持久化后要求必填 — 允许无需依赖即可验证 live；配置必需性随持久化接入收紧。
- Ruling：错误日志只输出异常类型和 request_id — 尚无受控堆栈收集设施，防止异常文本携带凭证；代价是当前故障排查信息有限。
- 保留小项：上游 Starlette/httpx TestClient 弃用提示；锁定依赖后测试和实际 HTTP 均通过，后续升级测试客户端时迁移。

未自动提交、未进入 MVP-03。
