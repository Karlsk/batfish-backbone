# LDR-02 业务关注项接口与版本

- 状态：已完成；阶段：领导端；依赖：[LDR-01](ldr-01-dual-entry.md)；预计 2.0 人天。
- 共享约束：[领导端设计](../../leader-design.md)、[架构](../../architecture.md)、[API 契约](../../api-contracts.md)。

## 需求与接口

新增网络级业务关注项：名称、说明、重要程度（high/medium/low）、1～10 条关键流量，每条含起点与规范目的 IPv4，源地址/协议/目的端口可选且按现有 flow 规则校验。创建和修改仅管理员，成员可读取；所有登录成员共享。记录版本、创建者、修改时间和归档状态；修改生成新版本，旧版本用于冻结汇报。关注项不包含快照 ID，运行检查时才绑定当前就绪快照。

`GET/POST /api/v1/business-concerns`、`GET/PATCH /api/v1/business-concerns/{id}` 使用分页、严格 Pydantic DTO 和 Cookie/CSRF；PATCH 不接受任意 SDK kwargs、引擎名称或跨网络修改。管理员归档后默认列表不显示，旧汇报版本仍可追溯。错误区分无权限、无网络、无效 flow 与版本冲突。

## 改动位置与步骤

- `web/backend/app/modules/business_concerns/`：api 只校验/映射，service 管权限、版本和生命周期，repository 只服务本模块；无需 SDK controller。
- Alembic 迁移：当前版本与不可变历史版本、网络关联、唯一约束和归档字段；不改现有网络/快照身份。
- 先写权限、版本、并发冲突、跨网络和流量校验测试，再实现最小 API 并生成 OpenAPI 类型。

## 验收

管理员创建/修改/归档与成员读取通过；普通成员写入为 403；版本变更不改变旧版内容；非法地址、端口/协议组合、超过上限与未知字段为 422；归档后旧版可由汇报引用。隔离 PostgreSQL 迁移、目标及累计后端测试、Ruff、OpenAPI 生成类型和真实 HTTP 权限/会话检查通过。

## 非目标与完成记录

不自动推断业务依赖或设备影响，不接入外部 CMDB。记录版本、迁移与实测结果；后续 LDR-03 依赖本篇接口通过。

2026-09-28 已完成。新增 `web/backend/app/modules/business_concerns/` 的严格 DTO、api/service/repository/ORM；`composition.py` 装配路由与模型；`0011_business_concerns.py` 增加当前和历史表，更新持久化迁移测试、OpenAPI 前端类型、API/后端文档。管理员写入、普通成员共享读取、版本冲突、并发唯一胜出、归档历史和非法流量拒绝在独立 PostgreSQL 上通过；临时真实 HTTP API 复核双用户会话与 CSRF。全量后端 372、真实冒烟 13、前端单测 94、LDR-01 浏览器回归 3 均通过，Ruff/类型/构建/格式/锁文件通过。环境固定 Batfish revision `7d0deeeac4a09973b3876327f6aef721ee12f955`、Pybatfish `2026.9.17.3748`、Python `3.12.12`，迁移 `0011`；详见[本篇证据](../../evidence/ldr-02-verification.md)。本篇没有分析或前端管理页，LDR-03 可继续。
