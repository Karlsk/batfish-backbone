# MVP-04 登录、改密与可撤销会话

- 状态：已完成
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

- [x] 实现初始化管理员和用户身份读取，不使用默认密码。
- [x] 实现随机会话 token、token 哈希存储、密码校验与撤销。
- [x] 加入 CSRF/Origin、统一登录失败和限流；限定首次改密会话权限。
- [x] 验证退出、改密、过期及失败限流后 API 行为。
- [x] 运行下述验证，记录实际命令与结果，更新本文及索引状态。

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

2026-09-25 完成。交付 auth 的 API/service/repository/schemas、最小 UsersService、Argon2id 基础设施、bootstrap 命令、初始化审计、迁移 `0002`、配置与装配。会话数据库仅保存 token 哈希，Cookie 8 小时绝对过期；Origin/CSRF 强制校验，临时密码限制权限，改密与退出撤销会话。数据库失败计数与事务锁保证多实例限流和并发初始化一致，session_version 避免 users/auth 循环依赖。

验证：仓库根 `web/backend/.venv/bin/python web/scripts/lab.py serve` → `seed` → `verify`。新启动真实 PostgreSQL 17.10/API/Batfish，自动迁移/随机管理员初始化，r1/r2 与 Cisco 四设备配置。MVP-01～04 累计 **98 passed，0 failed/errors/skipped**；前序 87 项保留，新增认证 10 项和真实 HTTP 1 项。覆盖 Cookie 安全属性、缺失/非法 Origin、CSRF、首次改密、未知用户统一失败、限流窗口/跨实例/并发、会话过期、改密全设备撤销、退出后旧 Cookie 重放、并发初始化以及审计脱敏。

backend 的 Ruff、`uv lock --check`（54 包）、Markdown 本地链接和 Git 空白检查通过。独立只读审查通过，无阻断项。运行 Argon2-cffi 25.1.0；Python/SDK/引擎版本沿用 MVP-03。实际命令、98 项清单、版本、源码指纹及原始运行目录见 [脱敏验收证据](../../evidence/mvp-04-verification.json)。测试环境初次启动曾发现私有文件创建使用了不支持的 Path.open 参数，改用内置 open 后重新建环境并完整通过。

没有未通过或跳过的必需检查；保留一条既有 Starlette/httpx 弃用警告。无前端，未执行浏览器；实际 HTTP 已覆盖两个独立会话。ready 仍等待 worker/engine 观测，不宣称完整应用就绪。满足 MVP-05 依赖；没有实现用户管理、公开注册或 SSO。运行凭证留在忽略目录，不随证据提交。
