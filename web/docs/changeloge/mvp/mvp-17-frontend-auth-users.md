# MVP-17 登录与用户管理界面

- 状态：待开发
- 阶段：1
- 依赖：[MVP-05](../mvp/mvp-05-user-administration.md)、[MVP-16](../mvp/mvp-16-frontend-foundation.md)
- 预计工作量：1.5 人天（实现/验证 1.0 + 测试 0.25 + 文档/自检 0.25），依赖就绪后计；超过 2 人天先拆分。
- 共享约束：[架构](../../architecture.md)、[API 契约](../../api-contracts.md)、[前端规范](../../frontend.md)、[运行设计](../../operations.md)、[验收](../../validation.md)。

## 需求与目标

普通成员能够登录改密，管理员能够完成成员管理。

- 登录、首次/主动改密、退出、用户列表、创建/启停/角色/重置密码。

## 设计与接口

- 使用 /auth 与 /users 已有契约；权限以服务端为准。
- 会话失效显示登录入口并清理本地请求缓存；临时密码不存储在浏览器历史。

沿用 api → service → controller；所有跨业务模块调用经过 service。非 SDK 存储由本模块 repository 负责。浏览器不接触 SDK 会话或连接参数。

## 预期改动位置

以下是实现时的目标路径，本次文档编写不创建代码文件：

- `web/frontend/src/features/auth/`
- `web/frontend/src/features/users/`
- `web/frontend/src/features/auth/auth.test.tsx`
- `web/frontend/src/features/users/users.test.tsx`

## 实施步骤

- [ ] 实现登录和强制改密路由，引导重新登录。
- [ ] 创建管理员用户表及详情抽屉，显示 API 的最后管理员冲突。
- [ ] 处理 401/403、CSRF 刷新及登录失败限流说明。
- [ ] 运行下述验证，记录实际命令与结果，更新本文及索引状态。

## 测试与验收

- auth.test.tsx：改密前不能进入业务页面，退出后缓存清空。
- users.test.tsx：成员无管理入口，后端403仍被正确呈现。
- 用户停用后另一个浏览器会话下次请求失效。

前端组件测试在 `web/frontend` 下使用 `pnpm exec vitest run` 指定上述 `.test.tsx` 文件；页面交互同时按前端规范人工检查。

验收成功同时要求：契约与文档一致、失败行为可解释、无跨层/跨模块越界、没有把 mock 验证宣称为真实 SDK 验证。共享约束中的身份、版本、模型覆盖和结果截断规则均适用。

## 非目标与实施边界

- 不做注册、邮件验证、SSO 或角色自定义。

## 完成记录

当前尚未开发或运行本 spec 的产品测试。实施者完成后在本节记录实际文件、验证命令、结果、引擎/SDK版本（如涉及）和剩余限制；存在验收失败时保持未通过状态。
