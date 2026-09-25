# MVP-17 登录与用户管理界面

- 状态：已完成
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

- [x] 实现登录和强制改密路由，引导重新登录。
- [x] 创建管理员用户表及详情抽屉，显示 API 的最后管理员冲突。
- [x] 处理 401/403、CSRF 刷新及登录失败限流说明。
- [x] 运行下述验证，记录实际命令与结果，更新本文及索引状态。

## 测试与验收

- auth.test.tsx：改密前不能进入业务页面，退出后缓存清空。
- users.test.tsx：成员无管理入口，后端403仍被正确呈现。
- 用户停用后另一个浏览器会话下次请求失效。

前端组件测试在 `web/frontend` 下使用 `pnpm exec vitest run` 指定上述 `.test.tsx` 文件；页面交互同时按前端规范人工检查。

验收成功同时要求：契约与文档一致、失败行为可解释、无跨层/跨模块越界、没有把 mock 验证宣称为真实 SDK 验证。共享约束中的身份、版本、模型覆盖和结果截断规则均适用。

## 非目标与实施边界

- 不做注册、邮件验证、SSO 或角色自定义。

## 完成记录

2026-09-25 完成 features/auth、features/users 及受保护路由：登录、首次/重置后强制改密、主动改密、退出与会话恢复；Cookie会话通过/me恢复内存CSRF，窗口聚焦和30秒检查撤销，401清理身份/缓存返回登录。权限仍由服务端决定，成员无管理导航，直接路由明确403；管理员用户列表分页、创建、详情、启停、角色及密码重置完整。最后管理员冲突给出可解释提示。

密码只在表单内存；创建/重置成功或取消清空，Form key+initialValues和preserve=false保证默认角色与用户切换正确且无密码残留。真实浏览器发现提前写未挂载表单导致默认角色丢失，修复后完整复验。权限选择器仅两项，关闭虚拟列表以提供完整可访问选项。用户页按需加载，顶栏长用户名省略并保留title。

实验环境显式允许15173前端Origin，保留Origin/CSRF校验，重启归属明确的服务后重新seed两个配置快照。仓库根 `lab.py seed/smoke/verify`：真实HTTP/worker双拓扑冒烟 **12 passed**；累计后端 **259 passed、0 skipped**。前端 `pnpm test`：**12 passed、0 skipped**；`check:api`、类型/构建、格式通过。`pnpm test:e2e`：**3 passed、0 skipped**；真实双用户浏览器完成创建、首次改密拦截与重新登录、角色编辑、成员无入口/403、管理员停用使另一个浏览器下次请求失效、重新启用与重置/退出；继续保留MVP-16两种宽度/键盘/滚动/渐进组件检查。已查看登录/用户列表截图。

独立只读审查及修复增量复核无阻断；Ruff、锁文件、文档与Git检查通过。见 [验收证据](../../evidence/mvp-17-verification.json)。构建初始包仍有体积提示，用户页已独立分包，不据此宣称容量达标。本篇未实现网络/快照页面，满足MVP-18前置并继续执行。
