# LDR-04 跨网络总览读模型

- 状态：已完成；阶段：领导端；依赖：[LDR-03](ldr-03-business-concerns-ui.md)；预计 2.0 人天。
- 共享约束：[领导端设计](../../leader-design.md)、[架构](../../architecture.md)、[API 契约](../../api-contracts.md)。

## 需求与接口

`GET /api/v1/leader/overview?offset&limit` 返回共享网络总数、有明确口径的快照质量/检查状态汇总和每页网络卡。网络卡包含网络身份、最新就绪快照、最新快照状态、已配置业务关注项数量、最近相关任务及结果质量；没有就绪快照或检查结果返回“待准备/未检查”，不能伪造健康分。最新就绪按完成时间与 ID 稳定排序，不用客户端单页数据推算组织总量。

leader api 只校验分页和可信 actor；leader service 汇总 network、snapshot、jobs、results、business concern **service** 的有界只读投影，不能跨模块访问 repository。结果范围与快照身份一致，历史任务不因最新快照改变而被套用。单次请求有界，不触发 SDK 工作。

## 改动位置与步骤

- `web/backend/app/modules/leader/`：overview api/service/DTO；各来源模块按需提供批量 service 只读方法，避免逐网络 N+1。
- 先写零网络、分页、同时间快照、旧结果、质量受限、成员/管理员共享与权限测试，再实现聚合和 OpenAPI。

## 验收

真实 PostgreSQL 下总量准确、卡片分页稳定；失败/中断不算成功，有限覆盖和截断保留；最新快照未就绪时仍可指明上一份就绪版本且提示差异。后端目标/累计测试、Ruff、迁移兼容、类型生成及真实 HTTP 两用户读取通过。

## 非目标与完成记录

不运行新分析、不给业务健康评分。记录性能采样口径、命令和限制，LDR-05 仅消费通过的读模型。

2026-09-28 已完成。`web/backend/app/modules/leader/` 增加 API、service 与 DTO；networks、snapshots、jobs、results、business_concerns 各自 service/repository 提供有界只读批量投影，总览不跨模块直读 repository。最新就绪快照和旧结果隔离、失败/中断、有限覆盖/截断、双用户权限、分页总数及 SQL 查询规模在真实 PostgreSQL 验证；OpenAPI 类型已生成。全量后端 374、双拓扑冒烟 13、前端单测 96、已有领导端浏览器 5 均通过，Ruff、构建、格式通过。真实 HTTP 两身份返回相同事实；性能样本与限制见[本篇证据](../../evidence/ldr-04-verification.md)。LDR-05 可继续。
