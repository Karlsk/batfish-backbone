# 分阶段研发规格索引

日期：2026-09-25。MVP-01～15 已完成，其余28份待开发。以下为分阶段 RDP spec；“RDP”沿用用户称呼，不额外假定某种公司模板。每份规格包含需求、设计/接口、改动位置、实施步骤、测试与验收、非目标和完成记录。

## 阶段门槛与顺序

1. [首版规格](mvp/README.md)：先完成 MVP-01 兼容性验证，按依赖推进，MVP-25 真实验收通过后进入第二阶段。
2. [进阶规格](advance/README.md)：ADV-01～10 是第二阶段，ADV-11～18 是第三阶段；第三阶段以 ADV-10 验收通过为前提。
3. 编号提供默认串行顺序；并行并非本次要求。若将来并行，必须先满足依赖、冻结接口并明确文件所有权，不靠编号相邻判断可同时开发。

MVP 只包含阶段1，不能因为 advance spec 已写好就提前实现其功能。目录名固定为用户指定的 changeloge。

## 工作量说明

| 范围 | Spec 数 | 预计人天 |
| --- | ---: | ---: |
| 阶段1 MVP | 25 | 40.0 |
| 阶段2 日常排障增强 | 10 | 14.5 |
| 阶段3 变更验证 | 8 | 13.0 |
| 总计 | 43 | 67.5 |

单份 1～2 人天，1 人天=8小时；包括该增量实现、必要测试、文档与自检，不是完整项目两天完成，也不是日历工期保证。估算假定真实引擎和开发环境可用、开发者熟悉对应技术。公共实现复用、串行 SDK 及已有 SDK 能力是估算前提；遇到版本不兼容、要改 Java 引擎或超预算，先新增小型修订/验证 spec，不挤占验收。

## 完整清单

| Spec | 依赖 | 工作量（人天） | 状态 |
| --- | --- | ---: | --- |
| [MVP-01 SDK 兼容性与能力基线](mvp/mvp-01-sdk-compatibility.md) | 无 | 1.0 | 已完成 |
| [MVP-02 后端骨架与分层约束](mvp/mvp-02-backend-foundation.md) | MVP-01 | 1.0 | 已完成 |
| [MVP-03 业务持久化与迁移基础](mvp/mvp-03-persistence.md) | MVP-02 | 1.5 | 已完成 |
| [MVP-04 登录、改密与可撤销会话](mvp/mvp-04-authentication.md) | MVP-03 | 2.0 | 已完成 |
| [MVP-05 账号管理与基础审计](mvp/mvp-05-user-administration.md) | MVP-04 | 1.5 | 已完成 |
| [MVP-06 网络创建与共享查询](mvp/mvp-06-network-management.md) | MVP-05 | 1.0 | 已完成 |
| [MVP-07 配置上传与输入校验](mvp/mvp-07-configuration-upload.md) | MVP-06 | 2.0 | 已完成 |
| [MVP-08 任务记录、幂等与排队取消](mvp/mvp-08-job-records.md) | MVP-07 | 1.5 | 已完成 |
| [MVP-09 独立执行进程与中断恢复](mvp/mvp-09-worker-recovery.md) | MVP-08 | 2.0 | 已完成 |
| [MVP-10 快照初始化与不可变生命周期](mvp/mvp-10-snapshot-initialization.md) | MVP-09 | 2.0 | 已完成 |
| [MVP-11 解析质量与原始文件查看](mvp/mvp-11-initialization-diagnostics.md) | MVP-10 | 1.5 | 已完成 |
| [MVP-12 分析目录与结果标准化](mvp/mvp-12-analysis-results.md) | MVP-11 | 2.0 | 已完成 |
| [MVP-13 设备与接口分析接口](mvp/mvp-13-inventory.md) | MVP-12 | 1.5 | 已完成 |
| [MVP-14 路由与最长前缀匹配接口](mvp/mvp-14-routing.md) | MVP-13 | 1.5 | 已完成 |
| [MVP-15 IPv4 单向虚拟 traceroute 接口](mvp/mvp-15-traceroute.md) | MVP-14 | 2.0 | 已完成 |
| [MVP-16 前端骨架与渐进展示组件](mvp/mvp-16-frontend-foundation.md) | MVP-12 | 1.5 | 待开发 |
| [MVP-17 登录与用户管理界面](mvp/mvp-17-frontend-auth-users.md) | MVP-05、MVP-16 | 1.5 | 待开发 |
| [MVP-18 网络、快照与上传向导界面](mvp/mvp-18-frontend-networks-snapshots.md) | MVP-10、MVP-17 | 2.0 | 待开发 |
| [MVP-19 任务记录与解析诊断界面](mvp/mvp-19-frontend-jobs-diagnostics.md) | MVP-11、MVP-18 | 1.5 | 待开发 |
| [MVP-20 设备、接口与路由界面](mvp/mvp-20-frontend-inventory-routing.md) | MVP-13、MVP-14、MVP-19 | 2.0 | 待开发 |
| [MVP-21 连通性表单与逐跳路径界面](mvp/mvp-21-frontend-traceroute.md) | MVP-15、MVP-20 | 2.0 | 待开发 |
| [MVP-22 结果导出与下载入口](mvp/mvp-22-result-export.md) | MVP-21 | 1.0 | 待开发 |
| [MVP-23 管理员资源删除与任务互斥](mvp/mvp-23-resource-deletion.md) | MVP-22 | 1.5 | 待开发 |
| [MVP-24 单机团队部署与运行手册](mvp/mvp-24-deployment.md) | MVP-23 | 1.5 | 待开发 |
| [MVP-25 首版双用户验收与规模校准](mvp/mvp-25-mvp-acceptance.md) | MVP-24 | 1.5 | 待开发 |
| [ADV-01 三层与协议拓扑分析接口](advance/adv-01-topology-api.md) | MVP-25 | 1.5 | 待开发 |
| [ADV-02 可交互拓扑与设备联动](advance/adv-02-topology-ui.md) | ADV-01 | 2.0 | 待开发 |
| [ADV-03 BGP 模型状态与兼容性接口](advance/adv-03-bgp-api.md) | ADV-02 | 1.0 | 待开发 |
| [ADV-04 BGP 状态列表与异常详情](advance/adv-04-bgp-ui.md) | ADV-03 | 1.0 | 待开发 |
| [ADV-05 ACL 流量测试接口](advance/adv-05-acl-test-api.md) | ADV-04 | 1.5 | 待开发 |
| [ADV-06 ACL 流量测试页面](advance/adv-06-acl-test-ui.md) | ADV-05 | 1.5 | 待开发 |
| [ADV-07 ACL 条件搜索与无效规则接口](advance/adv-07-acl-search-api.md) | ADV-06 | 2.0 | 待开发 |
| [ADV-08 ACL 高级诊断与证据分层](advance/adv-08-acl-search-ui.md) | ADV-07 | 1.5 | 待开发 |
| [ADV-09 登记式专家查询入口](advance/adv-09-expert-catalog.md) | ADV-08 | 1.5 | 待开发 |
| [ADV-10 第二阶段整体验收](advance/adv-10-phase-two-acceptance.md) | ADV-09 | 1.0 | 待开发 |
| [ADV-11 双快照对比上下文与记录](advance/adv-11-comparison-context.md) | ADV-10 | 1.0 | 待开发 |
| [ADV-12 配置文件差异分析](advance/adv-12-configuration-diff.md) | ADV-11 | 2.0 | 待开发 |
| [ADV-13 路由差异分析接口](advance/adv-13-routing-diff.md) | ADV-12 | 1.5 | 待开发 |
| [ADV-14 差异可达性分析接口](advance/adv-14-differential-reachability.md) | ADV-13 | 2.0 | 待开发 |
| [ADV-15 变更对比工作台](advance/adv-15-comparison-ui.md) | ADV-14 | 2.0 | 待开发 |
| [ADV-16 节点与接口故障派生快照](advance/adv-16-fault-simulation-api.md) | ADV-15 | 1.5 | 待开发 |
| [ADV-17 故障方案向导与影响分析](advance/adv-17-fault-simulation-ui.md) | ADV-16 | 1.5 | 待开发 |
| [ADV-18 第三阶段整体验收](advance/adv-18-phase-three-acceptance.md) | ADV-17 | 1.5 | 待开发 |

## 每次开发的阅读与交付规则

- 先读 [总览](../README.md)、[架构](../architecture.md)、[API 契约](../api-contracts.md) 和当前 spec 的依赖。
- spec 的相对路径在文件系统上指向相邻规格；“预期改动位置”是未来代码目标，不表示已经生成。
- 以测试/验收描述为证据完成增量；记录真实命令、版本与结果，不能只写“已完成”。
- 功能失败、真实引擎环境缺失或契约未验证时保持未通过，后续门槛不能跳过。
- 修订共享接口时同步受影响 spec 和能力表；对新增功能创建新编号，保留历史决定，避免偷偷扩大当前单元。
