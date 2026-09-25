# MVP-25 首版验收报告

日期：2026-09-26。状态：通过。后端 289 项、前端 37 项、浏览器 10+1+1 项全部通过，0 失败、0 跳过；smoke 12 项、Ruff/锁文件/OpenAPI/类型/构建/格式/文档检查通过。范围：MVP-01～25；不包含 ADV 或真实设备转发精度验证。

## 环境和样本

- 测试分支 `codex/mvp-integration-lab`，本篇基线 `9cbc173354`。最终源码摘要、命令和逐项结果见 [机器证据](evidence/mvp-25-verification.json)，逐篇提交见 [连续实施记录](plans/mvp-rollout.md)。
- Batfish 0.36.0，仓库引擎 revision `7d0deeeac4a09973b3876327f6aef721ee12f955`；JAR SHA256 `0927de7c740bc72f999870e842605baad9a7cb6ea66e4b01fb9a6037bea00193`。Pybatfish `2026.9.17.3748`，数据库迁移 `0008`。
- 主机 Python 3.12.12、Java 25；部署镜像 Python 3.12.13、Temurin 25.0.4、PostgreSQL 17.10、FastAPI 0.141.1。前端 Node 25.6.1（容器构建 25.9.0）、pnpm 11.19.0，依赖使用锁文件。
- r1/r2：两台华为/H3C 合成配置；Cisco：c1～c4 四台 OSPF 菱形。输入位于 `backend/tests/fixtures/small_network` 和 `cisco_four`；不使用现场配置或真实路由器。额外 ACL 故障样例是 Cisco 配置副本。
- 真实 API、独立 worker、PostgreSQL、当前分支 Batfish；部署验收额外使用同域 HTTPS、只读镜像和独立数据卷。单测中的故障注入不冒充真实引擎输出。

## 验收覆盖

| 范围 | 检查与结论 |
| --- | --- |
| 五类分析与 SDK 对照 | `tests/integration/test_mvp_acceptance.py` 在两套快照执行 nodes、interfaces、routes、lpm-routes、traceroute。独立 serializer 与公开 SDK question 参数比较完整保存数据；表格不依赖行顺序，trace 保留 flow、disposition、hop/step 顺序。两套均一致，无截断。 |
| 最小参数与高级参数 | 最小请求和显式默认值规范化为相同结果身份；断言命中同一 result_id。此项验证参数等价和缓存身份，不表示进行了第二次独立 SDK 计算。前端的高级参数保留、计数和上下文键由单测及常规浏览器回归覆盖。 |
| 双用户配置与结果 | `e2e/mvp.spec.ts` 使用两个独立浏览器 context。管理员创建成员、成员首次改密；交错上传/初始化/查询；分别核对完整文件名集合、SHA256、带行号原文，结果精确为 r1/r2 与 c1～c4。任务和结果刷新后可找回，切换顶部快照不改变历史结果来源。 |
| 权限与账号 | 成员无管理用户/删除入口；停用成员后旧会话失效。后端 auth/users/deletion 测试覆盖接口拒绝、管理员保护及删除与在途任务互斥。 |
| 解析和模型边界 | snapshots/diagnostics 测试与浏览器验证原始行定位、部分解析、未支持、乱码及模型限制；华为/H3C 的 IPv6/SRv6/EVPN/ACL 限制不标成已验证。 |
| 空结果与不可达 | routing/traceroute 测试覆盖空表、NO_ROUTE、混合 ACCEPTED/DENIED_IN、多 Flow、未知 disposition、max_traces 截断；页面区分业务空结果、不可达、错误和中断。 |
| 任务与恢复 | jobs/worker 测试及真实浏览器覆盖幂等、排队取消、不可变重试、刷新恢复。全新部署中实际终止在 SDK 请求等待中的 worker，unknown 阻止调度；只排队不执行，对账后才能恢复，原任务保持 interrupted。 |
| 上传、复杂结果与导出 | ZIP 路径穿越/膨胀/冲突、多根目录、附带 README；原始字节/哈希校验。NaN/集合/嵌套 trace、稳定分页、行数/字节截断、CSV 公式转义及 JSON 完整保存数据均有回归。 |
| 部署与备份 | 从新目录构建启动、初始化账号、HTTPS Cookie、两拓扑初始化、API 重启、失联与审计对账、三卷一致离线备份；恢复到另一项目空卷，原账号/任务/导出和新查询通过。恢复后的实际生产页面另跑浏览器验收。 |

## 规模记录和测量边界

本表取最终 289 项累计运行中的采样。耗时以测试进程的单次端到端调用计量：initialize 包括创建网络、测试基础上传、目标配置上传、入队和进程内 worker 执行；routes/traceroute 包括提交、进程内 worker、状态读取和 JSON 导出。不是单独 Batfish 计算耗时，也不是浏览器或生产排队延迟。

内存为约 100ms 一次 `ps` RSS 采样的观测峰值（采样间隔另含命令开销），计入首尾样本。Python 指测试进程内 worker，JVM 是已运行累计测试的暖引擎；不含整个部署栈，也不代表峰值分配或冷启动需求。完整六类操作数据、快照 UUID 和版本保存在机器证据。

| 样本 | 操作 | 耗时（秒） | Python RSS（MiB） | JVM RSS（MiB） | 导出字节 |
| --- | --- | ---: | ---: | ---: | ---: |
| r1/r2（2 台） | initialize | 0.845 | 223.8 | 911.4 | — |
| r1/r2（2 台） | routes | 0.405 | 226.1 | 915.1 | 4747 |
| r1/r2（2 台） | traceroute | 0.293 | 228.2 | 925.1 | 6134 |
| Cisco（4 台） | initialize | 0.811 | 230.8 | 931.1 | — |
| Cisco（4 台） | routes | 0.413 | 233.6 | 931.1 | 11022 |
| Cisco（4 台） | traceroute | 0.339 | 233.7 | 916.5 | 13734 |

本轮无需提高运行限额：保留单 worker/全局串行 SDK、请求超时 120 秒、结果上限 100 MiB、trace 默认最多 5 条，以及部署 JVM Xmx4g/5g 容器上限。数据没有支持降低这些保护值或增加并发的依据。仅验证 2/4 台；没有 100 台样本、压力测试、p95 或容量承诺。

## 实际验证入口

仓库根（已启动本任务 lab，执行 SDK 测试时暂停同引擎的其他任务）：

```bash
web/backend/.venv/bin/python web/scripts/lab.py smoke
web/backend/.venv/bin/python web/scripts/lab.py verify
web/backend/.venv/bin/ruff check web/backend web/scripts web/deploy
uv lock --check --project web/backend
```

`web/frontend` 下：

```bash
pnpm test
pnpm check:api
pnpm build
pnpm format:check
pnpm test:e2e
```

本轮部署根目录为 `web/.runtime/deploy-mvp25-release`，恢复目录加 `-restored`。先按 [部署 README](../README.md) prepare/build，再执行 `web/backend/.venv/bin/python web/scripts/verify_deployment.py --state web/.runtime/deploy-mvp25-release`。验证脚本管理该目录所属实例，不能复用团队环境；复验应选择新目录及空闲端口。

部署页面和双用户测试在 `web/frontend` 下运行：

```bash
export BFW_DEPLOYMENT_STATE="$PWD/../.runtime/deploy-mvp25-release-restored"
export BFW_DEPLOYMENT_EVIDENCE="$PWD/../.runtime/deploy-mvp25-release/verification.json"
pnpm exec playwright test --config playwright.deployment.config.ts
pnpm exec playwright test --config playwright.acceptance.config.ts
```

每次 Playwright 清理输出目录，因此报告和截图分别保存在 `.runtime/mvp-runner/mvp-25-browser`、`mvp-25-deployment-browser`、`mvp-25-acceptance-browser`。凭证只在权限受限的运行目录，不提交至 Git。浏览器针对本机自签证书允许访问；部署 HTTP 验证器实际校验证书 CA 和主机名。

## 当前服务和限制

本机部署入口为 `https://localhost:18444`，恢复项目 `bfw-1c23e5e71e49`；原始项目 `bfw-9422128b86f6` 备份后已停止。主机 lab API `http://127.0.0.1:18000` 保留，Vite 仅随浏览器测试临时启动。MVP-24 的上一轮恢复实例已停止，运行资料保留供诊断。

模型覆盖提示继续可见，traceroute 是单向配置模型推演。共享界面包仍有约 816.53 kB 构建警告；未实施 ADV、HA、在线增量备份或跨版本自动恢复。本批次只做本机验证与本地提交，下一阶段需要另行启动。
