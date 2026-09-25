# MVP-09 独立执行与保守恢复计划

基线MVP-08已提交；真实服务累计170项通过。沿用单worker/单SDK槽位、10秒心跳、60秒失联；超时不代表引擎停止。

- [x] 先以受控虚拟handler验证真实PostgreSQL原子领取、心跳/终态、双worker互斥、停用身份、旧任务不变与新重试身份；再加入真实子进程终止恢复和真实SDK轻量探测。
- [x] JobsService新增claim/heartbeat/finish/recover等内部入口，原子状态与lease_owner约束；ExecutionService通过jobs/auth/audit服务编排执行、管理员对账和登记handler重试，jobs不反向导入业务。
- [x] worker入口只调用composition装配的runner；长期进程独立于API，单worker进程锁、轮询领取、独立心跳线程、优雅停止不再领取。未知SDK占用阻止调度，失联running转interrupted/unknown，不重放。
- [x] 基础设施记录worker/引擎最近观测；空闲时通过controller公开SDK轻量版本探测，health只读观测与数据库，过期/未知不能ready。与现有网络创建共用EngineGate；管理员只在确认无持锁执行者后、带处理依据并审计解除unknown。
- [x] 重试经composition登记的业务service handler，重新检查身份/资源/引擎、仅允许已失败/中断/取消且可重试类型，旧记录不改写；未登记的未来业务返回明确冲突，初始化新快照由MVP-10 handler负责。
- [x] 测试环境加入独立worker并验证实际心跳、退出/重启、API管理员接口；SDK基线与应用引擎调用串行协调。完整累计验收、独立审查、证据回写后提交。

MVP-09不提前实现快照或分析业务handler；测试虚拟handler和真实SDK探测分别记录，不把虚拟执行称为分析功能。未登记操作明确失败或拒绝重试。遇到未知引擎状态保留占用，不清空状态以让测试假绿。
