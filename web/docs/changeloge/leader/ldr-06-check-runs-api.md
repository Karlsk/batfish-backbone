# LDR-06 检查模板与可恢复运行记录

- 状态：待开发；阶段：领导端；依赖：[LDR-05](ldr-05-overview-ui.md)；预计 2.0 人天。
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
