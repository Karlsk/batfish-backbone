# MVP-23 实施计划

基线af6b929722，依赖22已通过累计275/33/10验收并提交。

1. 先测试真实快照删除/结果保留/权限/非空网络、删除与分析和初始化提交竞争、SDK成功后写回失败对账。
2. 复用JobsService的PostgreSQL队列事务锁建立共享资源边界；分析准入、初始化/重试与删除依赖检查+deleting同边界。活动queued/running依赖含reference snapshot，未知引擎不准删除。
3. migration0008为network/snapshot记录deletion_job_id，防止历史删除任务对账覆盖新删除；previous状态保存在固定删除Job参数。lifecycle service仅通过各域service编排，SDK删除/存在性检查留域controller；远端确认不存在才标deleted，输入文件在提交后且无存活manifest引用时清理，结果与来源墓碑保留。
4. 失败/中断不自动重试或恢复。管理员通过删除任务对账，仍存在恢复previous状态，不存在补记deleted，未知保留deleting/引擎围栏。unknown先遵循已有停worker/核验引擎/全局对账流程，不用列表存在性证明引擎空闲。删除、对账写审计。
5. 管理员确认具体资源及影响后提交，不级联；普通成员无入口。任务详情提供对账与解释。拒绝旧初始化快照删除后的重试。前端类型与单测，真实两拓扑删除/browser，独立审查、累计门槛、记录及提交。
