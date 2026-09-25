# MVP-08 任务记录实施计划

基线MVP-07已提交，累计159项、真实HTTP冒烟8项通过。仅实现持久任务与排队取消，不提前运行worker。

- [x] 测试先行：相同用户/资源/键返回同任务、不同正文冲突、上下文与参数深度不可变；并发排队限额、取消与领取竞态、所有权/删除任务限制。
- [x] 定义内部ExecutionContext（快照可空，名称/版本为服务器映射）与JobDTO新增context/retry_of可空字段；迁移0004持久化上下文及历史重试父记录。状态转换表仅允许queued→running/cancelled，running→succeeded/failed/interrupted，终态不复活。
- [x] JobsService保留MVP-06资源幂等入口，新增submit/list/get/cancel；重新读取身份。跨模块调用只经service，jobs不反向导入networks/snapshots。提交方业务service负责资源授权与上下文映射，jobs负责身份与持久任务规则；不新增任意任务提交HTTP接口。
- [x] 以全局短事务锁原子核对默认每用户10/全局100排队限额；幂等重放先于限额判断；失败回滚任务和幂等记录。参数按规范JSON摘要，作用域含用户/kind/资源。
- [x] 共享分页历史支持status/network_id/created_by筛选；取消只允许所有者/管理员，queued且非deletion，原子条件更新防止领取后伪取消；cancel_allowed按当前kind/status派生。
- [x] 真实PostgreSQL/HTTP验证，独立只读审查，MVP-01～08累计验收、文档证据与提交。

通用重试入口、实际领取与worker在MVP-09接入；本篇只保留父任务关系和不可变历史所需元数据。没有后台执行不显示虚假成功。
