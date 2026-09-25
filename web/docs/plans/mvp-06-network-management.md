# MVP-06 网络管理实施计划

依据 MVP-06、架构和 API 契约；保持既有身份、模块边界和累计验收。

- [x] 测试先行：不同用户共享应用网络；同显示名不同 UUID/engine_name；同用户同幂等键相同请求复用、冲突返回409；列表不导入外部网络。
- [x] 最小 JobsService 幂等预留入口：复用 MVP-03 的 jobs 内部幂等表，只经 service 传共享事务；MVP-08 再扩展任务提交，避免网络模块越界访问 jobs ORM。
- [x] NetworksService 先事务提交 pending 映射与幂等记录，再调用 controller，最后写 ready/failed；SDK 成功但写回失败时保留固定身份并提供安全诊断；同键重试以同一内部名对账。
- [x] infrastructure 提供数据库级非阻塞引擎锁和持久占用槽位；SDK factory 每次独占会话，不复用可变上下文。controller 用公开 set_network 实现幂等创建/选择。
- [x] busy 返回503，保留 pending。SDK 调用结果未知或进程失联后保守阻塞，槽位保留 unknown；MVP-09 接入 worker 及管理员对账，不在本篇假装远端已停止。正常 SDK 完成后释放槽位，数据库资源写回故障可安全按原名重试。
- [x] 真实引擎测试和 HTTP 冒烟；故障注入仅用于写回失败/忙碌分支，不替代真实 SDK 创建；验证两实例不能同时进入 SDK 区域。
- [x] 独立审查、MVP-01～06 累计回归、脱敏证据/文档回写、提交后进入 MVP-07。

POST 最小 body 为 display_name，Idempotency-Key 可选、成功/业务错误响应回传有效键（提供时受用户/路由/资源作用域约束，至少保留24小时）。成功201 NetworkDTO，列表 items/offset/limit/total，详情404不存在。sync_error 仅为可公开的错误码，避免暴露 SDK/数据库异常内容。引擎锁的持久状态属于基础设施，业务 ORM 仍归各模块。
