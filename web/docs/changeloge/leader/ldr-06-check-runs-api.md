# LDR-06 检查模板与可恢复运行记录

- 状态：已完成；阶段：领导端；依赖：[LDR-05](ldr-05-overview-ui.md)；预计 2.0 人天。
- 共享约束：[领导端设计](../../leader-design.md)、[架构](../../architecture.md)、[API 契约](../../api-contracts.md)。

## 需求与接口

登记可执行模板，分为无需额外范围的配置质量/设备清单/拓扑/BGP 和需要显式范围的路由/LPM/连通性/ACL/变更/故障。模板返回标题、必要输入 schema、所用已有能力和模型限制。`POST /api/v1/leader/check-runs` 接收 `template_id`、`network_id`、`snapshot_id`、按模板校验的 `scope`、可选 `options`；用 `Idempotency-Key` 固定一次运行。`GET` 列表/详情返回模板版本、有效参数、子 job/result ID、状态和错误；不同用户共享可读。

leader service 验证就绪快照和业务关注项版本，只调用各模块 service 提交既有持久任务；独立 worker 继续串行 SDK。对于比较或故障必须固定双快照方向/派生关系。拒绝未知模板、跨网络资源、缺范围、重复键冲突和绕过白名单的参数。失败与未知引擎状态保留原样，不能自动重放。

## 改动位置与步骤

- `web/backend/app/modules/leader/`：模板目录、运行 service/api/repository/DTO，新增迁移保存运行及 job 关系；不创建 SDK controller。
- 先写权限、默认/高级参数、并发幂等、跨模块边界、任务终态/中断与来源冻结测试，再实现最小编排；补 OpenAPI 类型。

## 验收

同键同请求仅一组任务、不同请求冲突；长任务经独立 worker，可在刷新后查询；未知状态不重复调度；错误不变成空结论。隔离 PG/Batfish 目标与累计后端测试、Ruff、迁移、真实 API/worker 和双用户读取通过。

## 非目标与完成记录

不自动穷举全部网络、ACL 或故障组合；不新增任意 SDK 方法。记录实际模板列表、版本、命令与未覆盖能力。

### 2026-09-28 实施与验收

新增 `leader/checks_*` 分层、迁移 `0012`、OpenAPI 类型与 13 个版本 1 模板。配置质量固定现有解析事实；设备、接口、路由、LPM、traceroute、拓扑、BGP、ACL、三种变更与故障只经现有业务 service 提交任务。持久化运行绑定快照质量、引擎/SDK版本、关注项版本、有效参数、子 job/result 与故障派生快照。运行详情呈现阶段和引擎未知状态，同键并发只使用既有任务，中断/失败不自动重放。领导模块不直连 SDK、其他模块 repository 或 schema；本模块输入经白名单及目标 service 双重校验。技术端 API 保持原契约。

隔离 Batfish/PostgreSQL 上的本篇与迁移目标测试 12 passed；架构静态测试 55 passed；真实 API/独立 worker 和 LDR-01～05 累计浏览器回归 9 passed。前端 98 单测、OpenAPI 类型检查、TypeScript/构建/格式、Ruff check 与变更文件格式通过。`web/backend/.venv/bin/python web/scripts/lab.py verify`：385 passed；`web/backend/.venv/bin/python web/scripts/lab.py smoke`：13 passed。详细命令、运行目录和证据见[验收记录](../../evidence/ldr-06-verification.md)。引擎 revision `7d0deeeac4a09973b3876327f6aef721ee12f955`，Pybatfish `2026.9.17.3748`，Python `3.12.12`。LDR-07 前置已满足。

限制：用户需明确提供路由前缀、连通性起点/目标、ACL过滤器或比较/故障范围；模板不会枚举所有业务路径。模型结果不能证明现场转发或 Java 仿真精度。此前“服务尚未就绪”截图没有原请求地址和资源上下文，暂不能认定为同一故障已修复；浏览器已验证错误可见且可重试。
