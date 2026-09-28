# 全新部署默认管理员与首次改密验证

日期：2026-09-28。范围：现有认证流程的后续需求修订，不改变已有数据库凭据。空用户数据库首次使用 `admin/admin` 登录时，在同一 PostgreSQL 锁保护下创建唯一管理员及一条脱敏审计；登录返回 `must_change_password=true`。改密前业务接口拒绝访问；改成 12～128 字符密码后撤销旧会话，默认密码失效。

验证环境为隔离测试实验室 `84a19621afb6`（固定 Batfish `0.36.0`、Pybatfish `2026.9.17.3748`、PostgreSQL）和两套全新本地 HTTPS 容器部署。真实浏览器在第二套部署 `web/.runtime/deploy-default-admin-retest` 上完成默认登录、强制改密页、业务接口 403、改密后旧密码 401、新密码登录及管理接口 200；数据库确认仅 1 个用户和 1 条 `admin.bootstrap` 审计，改密标志清除。临时新密码仅保存在该部署忽略提交的 `auth.json`（0600），未写入源代码或本文。

- 后端 `tests/test_auth.py`：14 passed。新增测试先观察到空库默认登录 401，实施后通过；移除已有用户保护条件的突变验证按预期失败，恢复后通过。
- 累计后端：按 `lab.py verify` 的独占操作锁、worker 暂停和 `mvp01-` SDK 前缀运行，排除与本次改动无关的未跟踪 `tests/test_filters 2.py`，**395 passed，0 failed/error/skip**。JUnit 与 SDK 基线在 `web/.runtime/test-lab/84a19621afb6/checks/default-admin-correct-f0810b9b2743/`。
- 前端：认证组件 2 passed；全量 119 passed，OpenAPI 类型检查、TypeScript 检查和生产构建通过；Ruff lint/format、离线锁文件检查通过。生产构建保留既有大块提示。
- 首次手写累计命令没有暂停实验室 worker，且未使用要求的 `mvp01-` 前缀，出现 13 fail/7 error；修正运行条件后的完整 395 项重跑通过。第一套浏览器脚本断言了错误文案，第二套脚本最后一次授权检查早于登录完成；改用真实提示文案并等待已登录工作台后，默认登录、旧密码拒绝和新密码可用的各步骤均得到验证。上述中间失败均不计入通过数。

不对真实设备转发或 Java 仿真精度作结论。两个测试部署仅监听本机 HTTPS，验收后均已停止且保留隔离卷；第二套的密码已轮换，不能再用 `admin/admin` 登录。
