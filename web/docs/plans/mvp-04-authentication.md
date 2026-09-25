# MVP-04 登录与可撤销会话实施计划

依据已确认的 MVP-04 与 API/运行契约，沿用 spec-dev 的测试先行、串行实现、独立审查和累计验收。

- [x] 测试真实 PostgreSQL + TestClient：一次性初始化、登录 Cookie/Origin/CSRF、首次改密限制、退出/改密/过期撤销、未知用户统一失败、跨实例失败限流。
- [x] 建立 UsersService 身份/凭证验证、AuthService 会话与权限；跨模块只经 service，repository 留在本模块。
- [x] 加入 Argon2id、随机会话 token 的 SHA256 存储、8 小时绝对过期、常量时间 CSRF 比较、生产 Secure Cookie、精确 Origin 白名单；登录和写请求缺 Origin 一律拒绝，本机显式配置 HTTP 开发 Origin。
- [x] PostgreSQL 持久化失败计数（按客户端地址和用户名分别限流），并发串行校验避免绕过；用户名不存在也执行 Argon2 验证且返回同一错误。
- [x] 用户 session_version 与会话版本支持重置/停用撤销而不引入 users↔auth service 循环；本篇改密同时显式撤销现有会话。身份和停用状态每次读取。
- [x] 仅无管理员可执行 bootstrap 命令；密码用 getpass/受保护环境输入，初始化记脱敏审计。无默认密码、无公开注册。
- [x] 使用新迁移扩展会话版本/失败计数，更新 lab 测试账号及真实 HTTP 冒烟；完整回归 MVP-01～04 后回写提交。

默认失败阈值 5 次、窗口 15 分钟，可通过 settings 修改。API 只提取真实连接地址（不信任客户端 forwarded headers）、验证请求并映射 Cookie/响应；AuthService 决定权限和状态。数据库不可用时 live 可用，但认证不假成功；未部署数据库的原 MVP-02 工厂仍仅提供健康入口。

密码实现参考 [argon2-cffi 官方说明](https://argon2-cffi.readthedocs.io/en/stable/howto.html)。文件、结果和 SDK 行为沿用 MVP-03，不在本篇增加用户管理、worker 或业务分析接口。
