# MVP-05 账号管理与基础审计

- 状态：已完成
- 阶段：1
- 依赖：[MVP-04](../mvp/mvp-04-authentication.md)
- 预计工作量：1.5 人天（实现/验证 1.0 + 测试 0.25 + 文档/自检 0.25），依赖就绪后计；超过 2 人天先拆分。
- 共享约束：[架构](../../architecture.md)、[API 契约](../../api-contracts.md)、[前端规范](../../frontend.md)、[运行设计](../../operations.md)、[验收](../../validation.md)。

## 需求与目标

管理员可维护共享团队成员，变更权限立即生效。

- 创建用户、分页列表、启停/角色变更、临时密码重置、关键操作审计。

## 设计与接口

- GET/POST /users；PATCH /users/{id}；POST /users/{id}/reset-password。
- users.service 承担角色和最后管理员约束；API 不接受客户端声明的 actor_id。
- 停用/重置撤销全部会话；普通成员访问管理接口返回 403。

沿用 api → service → controller；所有跨业务模块调用经过 service。非 SDK 存储由本模块 repository 负责。浏览器不接触 SDK 会话或连接参数。

## 预期改动位置

以下是实现时的目标路径，本次文档编写不创建代码文件：

- `web/backend/app/modules/users/api.py`
- `web/backend/app/modules/users/service.py`
- `web/backend/app/modules/users/repository.py`
- `web/backend/app/infrastructure/audit.py`
- `web/backend/tests/test_users.py`

## 实施步骤

- [x] 扩展用户 service 管理操作并写审计。
- [x] 实现重复用户名、最后管理员、自己停用/降级的明确规则。
- [x] 验证停用/重置对旧会话和用户查询的影响。
- [x] 运行下述验证，记录实际命令与结果，更新本文及索引状态。

## 测试与验收

- test_member_cannot_administer：直接请求亦被禁止。
- test_disable_revokes_sessions：所有设备上的旧会话失效。
- test_last_admin_guard：并发降级不能使有效管理员数变成零。
- test_audit_redaction：记录结果但不记录临时密码。

后端测试在 `web/backend` 下使用 `uv run pytest` 指定上述测试文件；集成测试连接版本固定的隔离 Batfish 测试网络，不操作团队生产网络。

验收成功同时要求：契约与文档一致、失败行为可解释、无跨层/跨模块越界、没有把 mock 验证宣称为真实 SDK 验证。共享约束中的身份、版本、模型覆盖和结果截断规则均适用。

## 非目标与实施边界

- 不做项目授权、多角色权限编辑或用户物理删除。

## 完成记录

2026-09-25 完成。交付 users API、service/repository/schemas 扩展与 composition 认证注入，复用 MVP-04 审计 service（实际位置为 `app/modules/audit/`，遵循跨模块 service 规则，因此不另建 infrastructure 中的业务审计模块）。支持创建、分页、启停/角色更新和临时密码重置，公开 DTO 排除凭证；管理权限在数据库中重新核对。

所有管理变更共用 PostgreSQL 事务锁，保证最后一个 enabled admin 不能被并发停用/降级。自己停用/降级也遵循同一规则。停用和重置递增会话版本，启用不会复活旧 Cookie；角色读取即时生效。成功变更与审计同事务，审计失败回滚业务；进入管理 service 的拒绝记录 failed，不保存密码或完整请求。

验证（仓库根）：`web/backend/.venv/bin/python web/scripts/lab.py serve` → `seed` → `verify`，新启动当前应用、PostgreSQL 17.10 和固定 Batfish，使用 r1/r2 与 Cisco 四设备配置。MVP-01～05 累计 **107 passed、0 failed/errors/skipped**；新增 8 项账号管理测试和 1 项真实 HTTP 管理冒烟，前序 98 项保留。覆盖普通成员拒绝、分页/重名/未知字段、双会话停用、重新启用不复活、重置和首次改密、角色即时变化、并发停用/降级、审计请求 ID/脱敏及失败回滚。

backend 中 Ruff、`uv lock --check`（54 包）、Markdown 本地链接与 Git 空白检查通过。独立只读审查无可操作缺陷。版本沿用 MVP-04，未改 Java；[脱敏验收证据](../../evidence/mvp-05-verification.json) 记录实际命令、107 项测试、环境和源码指纹。

没有失败或跳过的必需检查。保留既有 Starlette/httpx 弃用警告；尚无前端，未执行浏览器。审计暂无页面，用户不做物理删除、项目授权或多角色编辑；这些并非本项交付。满足 MVP-06 依赖。
