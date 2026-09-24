# MVP-04 登录、改密与可撤销会话

- 状态：待开发
- 阶段：1
- 依赖：[MVP-03](../mvp/mvp-03-persistence.md)
- 预计工作量：2.0 人天（实现/验证 1.25 + 测试 0.5 + 文档/自检 0.25），依赖就绪后计；超过 2 人天先拆分。
- 共享约束：[架构](../../architecture.md)、[API 契约](../../api-contracts.md)、[前端规范](../../frontend.md)、[运行设计](../../operations.md)、[验收](../../validation.md)。

## 需求与目标

实现团队成员身份认证，使后续业务拥有可信 Actor。

- 一次性管理员初始化、密码哈希、登录/退出/me/改密、会话过期与 CSRF。
- 用户身份查询的最小 UsersService，后续管理操作在 MVP-05。

## 设计与接口

- POST /auth/login、/auth/logout、/auth/password；GET /auth/me。
- AuthService.require_actor(session_token) → Actor；UsersService.get_identity(user_id) → UserIdentity。
- 首次改密限制、8 小时过期、Argon2id、失败限流和 Cookie 规则按共享契约。

沿用 api → service → controller；所有跨业务模块调用经过 service。非 SDK 存储由本模块 repository 负责。浏览器不接触 SDK 会话或连接参数。

## 预期改动位置

以下是实现时的目标路径，本次文档编写不创建代码文件：

- `web/backend/app/modules/auth/api.py`
- `web/backend/app/modules/auth/service.py`
- `web/backend/app/modules/auth/repository.py`
- `web/backend/app/modules/users/service.py`
- `web/backend/app/bootstrap_admin.py`
- `web/backend/tests/test_auth.py`

## 实施步骤

- [ ] 实现初始化管理员和用户身份读取，不使用默认密码。
- [ ] 实现随机会话 token、token 哈希存储、密码校验与撤销。
- [ ] 加入 CSRF/Origin、统一登录失败和限流；限定首次改密会话权限。
- [ ] 验证退出、改密、过期及失败限流后 API 行为。
- [ ] 运行下述验证，记录实际命令与结果，更新本文及索引状态。

## 测试与验收

- test_login_cookie_and_csrf：正确登录后写请求需 CSRF；无 Origin/非法 Origin 按环境策略拒绝。
- test_logout_and_password_revoke：旧 cookie 随撤销失效。
- test_initial_password_restriction：改密前不能读取业务资源。
- test_no_user_enumeration：用户名不存在与密码错误响应一致。

后端测试在 `web/backend` 下使用 `uv run pytest` 指定上述测试文件；集成测试连接版本固定的隔离 Batfish 测试网络，不操作团队生产网络。

验收成功同时要求：契约与文档一致、失败行为可解释、无跨层/跨模块越界、没有把 mock 验证宣称为真实 SDK 验证。共享约束中的身份、版本、模型覆盖和结果截断规则均适用。

## 非目标与实施边界

- 不做 SSO、注册、邮件找回或 JWT 刷新体系。

## 完成记录

当前尚未开发或运行本 spec 的产品测试。实施者完成后在本节记录实际文件、验证命令、结果、引擎/SDK版本（如涉及）和剩余限制；存在验收失败时保持未通过状态。
