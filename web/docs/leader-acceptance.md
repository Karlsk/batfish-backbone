# 领导端整体验收（LDR-12）

日期：2026-09-28。状态：通过。本报告只评价固定 Batfish 版本、合成配置和 Web 工作流；不证明真实设备转发，也不对 Java 仿真精度或约 100 台设备容量作承诺。

## MVP/ADV 覆盖矩阵

| 已交付能力 | 领导端结论入口 | 更深证据与技术操作 |
| --- | --- | --- |
| MVP 身份、共享网络、上传/快照、解析诊断、任务、结果、导出和删除 | `/leader/overview`、`/leader/networks/:id` 显示最新就绪来源、解析质量、未检查/任务状态和证据入口；登录后可切换双入口 | 网络上传与管理员删除、配置行、任务/结果及导出进入原技术端；未就绪不显示健康结论 |
| MVP 设备、接口、路由、LPM、虚拟 traceroute | `/leader/checks` 按问题引导，固定网络/快照和必要范围；详情展示结果、覆盖和警告 | `/results/:id`、任务及原技术检查页给出完整行、逐跳和高级参数 |
| ADV 拓扑、BGP、ACL、登记式专家能力 | 同一检查入口给出模型关系、会话/兼容性、指定流量与 ACL 的局部判断；专家目录仅展示已登记能力 | 原拓扑、BGP、ACL 和专家工作台展示完整字段与参数；范围外模板不自动开放 |
| ADV 双快照比较、配置/路由/可达性差异、故障派生 | `/leader/changes`、`/leader/faults` 固定基线→候选方向、显式分析范围和派生状态 | 原变更/故障工作台、文件行、路由行、双侧 trace 和派生诊断继续保留 |
| 业务关注项与固定汇报 | `/leader/concerns` 保存网络归属与映射版本；`/leader/briefings` 把已完成结果冻结为报告，全屏会议页分离系统事实与人工备注 | 结果 ID 深链到技术详情；来源失效时原始链接关闭，固定事实仍可读 |

## 口径与异常

总览跨全部共享网络分页，不用单页推断总数；每张卡只绑定最新**就绪**快照。没有检查即“未检查”，失败/中断与空结果分开显示。检查和汇报显示模型覆盖、截断、解析警告和引擎/SDK 版本；流量和业务影响只在明确范围及映射下解读，不生成全网健康分。业务关注项更新后，旧汇报继续显示创建时的映射版本。会议页和打印保留来源、时间、版本、警告，主题可切换并尊重减少动效设置。

早前截图中的“服务尚未就绪”缺少原 URL、网络与快照上下文，不能归因于已修复的某个请求。当前浏览器测试主动模拟 `NOT_READY` 并验证提示与重试可见，未以隐藏错误作为通过条件。

## 本轮环境与证据

隔离运行 `84a19621afb6` 使用 r1/r2 与 Cisco 四设备合成配置、Batfish `0.36.0`（revision `7d0deeeac4a09973b3876327f6aef721ee12f955`、JAR SHA-256 `0927de7c740bc72f999870e842605baad9a7cb6ea66e4b01fb9a6037bea00193`）、Pybatfish `2026.9.17.3748`、Python `3.12.12` 和 PostgreSQL 迁移 `0013`。管理员首次登录改密后，通过真实 Web API 上传并初始化两套配置；检查任务由独立 worker 执行。

| 门槛 | 本轮结果 |
| --- | --- |
| 后端全量 | `web/backend/.venv/bin/python web/scripts/lab.py verify`：392 passed，0 fail/skip；证据 `web/.runtime/test-lab/84a19621afb6/checks/7039a12ad3f9`。 |
| 真实引擎冒烟 | `web/backend/.venv/bin/python web/scripts/lab.py smoke`：13 passed，379 项按 smoke 标记有意筛选；证据 `web/.runtime/test-lab/84a19621afb6/checks/0a701bfbcdd0`。 |
| 前端 OpenAPI、单测、类型、构建、格式 | `pnpm check:api && pnpm test && pnpm typecheck && pnpm build && pnpm format:check`：119 passed，契约、类型、构建、格式通过；生产构建仍有现存的大块提示。 |
| 全部 MVP/ADV/LDR 与技术端 Chromium | `python3 /private/tmp/ldr03-run.py tests`：46 passed，0 fail/skip；真实 PG/API/worker/Batfish 上使用两套配置及双用户。 |
| 全新 HTTPS、未知状态栅栏、备份与新卷恢复 | `web/scripts/verify_deployment.py --state web/.runtime/deploy-ldr12`：通过；证据 `web/.runtime/deploy-ldr12/verification.json`。验证 API 重启、运行中 worker 丢失的未知状态栅栏及恢复、离线备份和新卷恢复。 |
| 恢复后生产明暗主题与双用户 | 对 `web/.runtime/deploy-ldr12-restored` 执行 `playwright.deployment.config.ts`：明/暗各 4 passed；`playwright.acceptance.config.ts`：明/暗各 1 passed。固定汇报在关注项升级至第 2 版后仍保留第 1 版事实，打印样式和双入口正常。 |
| 静态与源码身份 | Ruff lint/format、离线锁文件、Git 空白检查通过；源码指纹见机器证据。 |

机器可读结果、源码指纹和部署产物路径在 [LDR-12 证据](evidence/ldr-12-verification.json) 固定。隔离运行的日志、截图、凭据和报告原文保留在本地忽略目录，不提交账号密码或设备配置原文。
