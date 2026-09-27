# LDR-10 固定汇报接口验收

日期：2026-09-28；基线提交 `8309a814d3`（LDR-09）。隔离环境运行 ID `8a53df3cb24f`；Batfish revision `7d0deeeac4a09973b3876327f6aef721ee12f955`、Pybatfish `2026.9.17.3748`、Python `3.12.12`。仅验证合成配置上的 Web 工作流和固定版本模型。

| 检查 | 结果 |
| --- | --- |
| 目标集成 | `web/backend` 设置 `BATFISH_LAB_MANIFEST=/Users/gaorenjie/Documents/Coding/JAVA/batfish-dev/web/.runtime/test-lab/current.json` 后执行 `.venv/bin/python -m pytest tests/test_leader_briefings.py -q`：5 passed。覆盖已完成结果来源、跨快照/网络拒绝、结果与关注项版本冻结、警告/覆盖/截断、标题备注新版本、旧版本读取、成员创建/读取、管理员归档、同键并发幂等、结果元数据和文件消失后保留事实并关闭证据入口。 |
| 后端累计 | `web/backend/.venv/bin/python web/scripts/lab.py verify`（仓库根目录）：392 passed，2 个既有依赖警告；机器证据 `web/.runtime/test-lab/8a53df3cb24f/checks/0872596c47f3/pytest.xml` 和 `result.json`。首次运行的 2 项失败来自新增文件未登记在分层检查器和空库迁移表清单；补齐后全量重跑为 0 fail。 |
| 迁移与架构 | PostgreSQL 空 schema 上的 Alembic `0013` 升级通过；当前源码 API 启动时也在隔离库升级到 `0013`。`ruff check app tests migrations` 全通过；本篇改动的 13 个 Python 文件 `ruff format --check` 全通过。仓库历史 `tests/integration/test_sdk_baseline.py` 仍不符合当前 Ruff 格式，留在 LDR-12 全局格式收口中处理。 |
| OpenAPI 与前端回归 | `web/frontend` 执行 `pnpm generate:api`、`pnpm check:api`、`pnpm test`、`pnpm typecheck`、`pnpm build`、`pnpm format:check`：生成契约一致，115 passed，类型、生产构建与格式通过。构建保留既有大包体积提示。 |
| 真实浏览器累计 | `python3 /private/tmp/ldr03-run.py tests/leader-changes.spec.ts tests/leader-advanced-checks.spec.ts tests/leader-mvp-checks.spec.ts tests/leader-checks-api.spec.ts tests/leader-overview.spec.ts tests/leader-entry.spec.ts tests/leader-concerns.spec.ts tests/auth-users.spec.ts tests/changes.spec.ts tests/faults.spec.ts`（`web/frontend`）：20 passed，覆盖 LDR-01～09 和技术端比较/故障页面。独立运行 `tests/leader-briefings-api.spec.ts`：1 passed；当前 API、worker 与 PostgreSQL 上完成汇报创建、同键重放、修订和旧版读取。 |

汇报仅保存结果 envelope 的摘要、有效参数、来源 ID、警告、模型覆盖/截断及版本；不保存设备配置原文或分析 payload。不可变修订以独立 ID 读取，标题与人工备注由新修订承载。来源状态在读取时动态核对；来源失效时系统事实保留，证据入口标为不可用。归档不会删除历史修订。早前“服务尚未就绪”的原请求上下文仍未知，本篇不能宣称定位或修复那次截图的问题。
