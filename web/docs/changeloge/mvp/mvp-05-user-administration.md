# MVP-05 账号管理与基础审计

- 状态：待开发
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

- [ ] 扩展用户 service 管理操作并写审计。
- [ ] 实现重复用户名、最后管理员、自己停用/降级的明确规则。
- [ ] 验证停用/重置对旧会话和用户查询的影响。
- [ ] 运行下述验证，记录实际命令与结果，更新本文及索引状态。

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

当前尚未开发或运行本 spec 的产品测试。实施者完成后在本节记录实际文件、验证命令、结果、引擎/SDK版本（如涉及）和剩余限制；存在验收失败时保持未通过状态。
