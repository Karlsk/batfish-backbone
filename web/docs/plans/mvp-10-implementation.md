# MVP-10 实施计划

依据已确认快照初始化 spec，保持 api → service → controller 与跨模块 service 边界。

1. 先测试原子消费、幂等、取消及新身份重试、质量判定和 options 白名单。
2. 增加快照保存的 manifest、版本与初始化诊断；迁移兼容已有数据。
3. UploadsService 支持共享事务消费及安全临时目录物化；原始文件保留。
4. SnapshotService 原子创建快照与任务；注册 API/worker 同一初始化和重试处理器。状态结合持久化 job 派生。
5. Controller 使用独占 Session、overwrite=False 和明确 SDK 参数映射，收集 fileParseStatus/initIssues、版本，服务层质量门决定可分析状态。
6. 两套配置经真实 API/worker/Batfish 初始化；并发、错误、权限、部分解析、取消重试与旧 MVP 累计验收。
7. 单独只读审查、修复、刷新环境、完整验收、回写并提交。

SDK 参数依据本仓库 Settings：ignoremanagementinterfaces 默认 true，parsereuse 默认 false；必须通过固定版本实际初始化验证。结果不作为与真实设备行为一致性的证明。
