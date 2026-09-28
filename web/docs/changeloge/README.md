# 分阶段研发规格索引

日期：2026-09-28。MVP-01～25、ADV-01～18 和领导端 LDR-01～12 已完成，四阶段验收通过。新增 CMDB-01～11 与 SIM-01～17 为待开发规划，既有验收不等于新功能可用。以下为分阶段 RDP spec；“RDP”沿用用户称呼，不额外假定某种公司模板。

## 阶段门槛与顺序

1. [首版规格](mvp/README.md)：先完成 MVP-01 兼容性验证，按依赖推进，MVP-25 真实验收通过后进入第二阶段。
2. [进阶规格](advance/README.md)：ADV-01～10 是第二阶段，ADV-11～18 是第三阶段；第三阶段以 ADV-10 验收通过为前提。
3. [领导端规格](leader/README.md)：LDR-01～12 建立双入口、业务关注项、引导检查和固定汇报；以前三阶段验收完成为前提。
4. [采集一期](cmdb/README.md)：CMDB-01～11 建立版本化设备/链路、统一 ZIP、分段推送、物理拓扑和配置历史；以 LDR-12 为前置。
5. [推演二期](simulation/README.md)：SIM-01～17 建立多设备候选和 Underlay/业务/隔离检查；以 CMDB-11 为阶段门槛。
6. 编号提供默认串行顺序；并行并非本次要求。若将来并行，必须先满足依赖、冻结接口并明确文件所有权，不靠编号相邻判断可同时开发。

MVP 只包含阶段1，不能因为 advance spec 已写好就提前实现其功能。目录名固定为用户指定的 changeloge。

## 工作量说明

| 范围 | Spec 数 | 预计人天 |
| --- | ---: | ---: |
| 阶段1 MVP | 25 | 40.0 |
| 阶段2 日常排障增强 | 10 | 14.5 |
| 阶段3 变更验证 | 8 | 13.0 |
| 领导端 | 12 | 22.5 |
| 已完成合计 | 55 | 90.0 |
| CMDB 采集一期（待开发） | 11 | 30.0 |
| SIM 推演二期（待开发） | 17 | 47.0 |
| 全部规划合计 | 83 | 167.0 |

旧批次单份 1～2 人天；新批次单份 2～3 人天。1 人天=8小时，包括该增量实现、必要测试、文档与自检，不是日历工期保证。估算假定真实引擎和开发环境可用、开发者熟悉对应技术。公共实现复用、串行 SDK 及已有 SDK 能力是估算前提；遇到版本不兼容、要改 Java 引擎或超预算，先拆分修订 spec，不挤占验收。

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
| [MVP-16 前端骨架与渐进展示组件](mvp/mvp-16-frontend-foundation.md) | MVP-12 | 1.5 | 已完成 |
| [MVP-17 登录与用户管理界面](mvp/mvp-17-frontend-auth-users.md) | MVP-05、MVP-16 | 1.5 | 已完成 |
| [MVP-18 网络、快照与上传向导界面](mvp/mvp-18-frontend-networks-snapshots.md) | MVP-10、MVP-17 | 2.0 | 已完成 |
| [MVP-19 任务记录与解析诊断界面](mvp/mvp-19-frontend-jobs-diagnostics.md) | MVP-11、MVP-18 | 1.5 | 已完成 |
| [MVP-20 设备、接口与路由界面](mvp/mvp-20-frontend-inventory-routing.md) | MVP-13、MVP-14、MVP-19 | 2.0 | 已完成 |
| [MVP-21 连通性表单与逐跳路径界面](mvp/mvp-21-frontend-traceroute.md) | MVP-15、MVP-20 | 2.0 | 已完成 |
| [MVP-22 结果导出与下载入口](mvp/mvp-22-result-export.md) | MVP-21 | 1.0 | 已完成 |
| [MVP-23 管理员资源删除与任务互斥](mvp/mvp-23-resource-deletion.md) | MVP-22 | 1.5 | 已完成 |
| [MVP-24 单机团队部署与运行手册](mvp/mvp-24-deployment.md) | MVP-23 | 1.5 | 已完成 |
| [MVP-25 首版双用户验收与规模校准](mvp/mvp-25-mvp-acceptance.md) | MVP-24 | 1.5 | 已完成 |
| [ADV-01 三层与协议拓扑分析接口](advance/adv-01-topology-api.md) | MVP-25 | 1.5 | 已完成 |
| [ADV-02 可交互拓扑与设备联动](advance/adv-02-topology-ui.md) | ADV-01 | 2.0 | 已完成 |
| [ADV-03 BGP 模型状态与兼容性接口](advance/adv-03-bgp-api.md) | ADV-02 | 1.0 | 已完成 |
| [ADV-04 BGP 状态列表与异常详情](advance/adv-04-bgp-ui.md) | ADV-03 | 1.0 | 已完成 |
| [ADV-05 ACL 流量测试接口](advance/adv-05-acl-test-api.md) | ADV-04 | 1.5 | 已完成 |
| [ADV-06 ACL 流量测试页面](advance/adv-06-acl-test-ui.md) | ADV-05 | 1.5 | 已完成 |
| [ADV-07 ACL 条件搜索与无效规则接口](advance/adv-07-acl-search-api.md) | ADV-06 | 2.0 | 已完成 |
| [ADV-08 ACL 高级诊断与证据分层](advance/adv-08-acl-search-ui.md) | ADV-07 | 1.5 | 已完成 |
| [ADV-09 登记式专家查询入口](advance/adv-09-expert-catalog.md) | ADV-08 | 1.5 | 已完成 |
| [ADV-10 第二阶段整体验收](advance/adv-10-phase-two-acceptance.md) | ADV-09 | 1.0 | 已完成 |
| [ADV-11 双快照对比上下文与记录](advance/adv-11-comparison-context.md) | ADV-10 | 1.0 | 已完成 |
| [ADV-12 配置文件差异分析](advance/adv-12-configuration-diff.md) | ADV-11 | 2.0 | 已完成 |
| [ADV-13 路由差异分析接口](advance/adv-13-routing-diff.md) | ADV-12 | 1.5 | 已完成 |
| [ADV-14 差异可达性分析接口](advance/adv-14-differential-reachability.md) | ADV-13 | 2.0 | 已完成 |
| [ADV-15 变更对比工作台](advance/adv-15-comparison-ui.md) | ADV-14 | 2.0 | 已完成 |
| [ADV-16 节点与接口故障派生快照](advance/adv-16-fault-simulation-api.md) | ADV-15 | 1.5 | 已完成 |
| [ADV-17 故障方案向导与影响分析](advance/adv-17-fault-simulation-ui.md) | ADV-16 | 1.5 | 已完成 |
| [ADV-18 第三阶段整体验收](advance/adv-18-phase-three-acceptance.md) | ADV-17 | 1.5 | 已完成 |
| [LDR-01 双入口与壳层](leader/ldr-01-dual-entry.md) | ADV-18 | 1.5 | 已完成 |
| [LDR-02 业务关注项接口](leader/ldr-02-business-concerns-api.md) | LDR-01 | 2.0 | 已完成 |
| [LDR-03 业务关注项页面](leader/ldr-03-business-concerns-ui.md) | LDR-02 | 1.5 | 已完成 |
| [LDR-04 跨网络总览接口](leader/ldr-04-overview-api.md) | LDR-03 | 2.0 | 已完成 |
| [LDR-05 日常总览页面](leader/ldr-05-overview-ui.md) | LDR-04 | 2.0 | 已完成 |
| [LDR-06 检查模板与运行记录](leader/ldr-06-check-runs-api.md) | LDR-05 | 2.0 | 已完成 |
| [LDR-07 MVP 自主检查页面](leader/ldr-07-mvp-guided-checks.md) | LDR-06 | 2.0 | 已完成 |
| [LDR-08 ADV 排障检查页面](leader/ldr-08-adv-guided-checks.md) | LDR-07 | 2.0 | 已完成 |
| [LDR-09 变更与故障领导视图](leader/ldr-09-change-fault-ui.md) | LDR-08 | 2.0 | 已完成 |
| [LDR-10 固定汇报接口](leader/ldr-10-briefings-api.md) | LDR-09 | 2.0 | 已完成 |
| [LDR-11 汇报与会议页面](leader/ldr-11-briefings-ui.md) | LDR-10 | 2.0 | 已完成 |
| [LDR-12 领导端整体验收](leader/ldr-12-acceptance.md) | LDR-11 | 1.5 | 已完成 |
| [CMDB-01 稳定身份与资产版本模型](cmdb/cmdb-01-identity-revisions.md) | LDR-12 | 3.0 | 待开发 |
| [CMDB-02 快照级资产与历史只读 API](cmdb/cmdb-02-read-api.md) | CMDB-01 | 2.5 | 待开发 |
| [CMDB-03 人工设备、链路与配置草稿 CRUD](cmdb/cmdb-03-manual-drafts.md) | CMDB-02 | 3.0 | 待开发 |
| [CMDB-04 统一 ZIP、node.json 与物理链路校验](cmdb/cmdb-04-bundle-contract.md) | CMDB-01 | 2.5 | 待开发 |
| [CMDB-05 分段推送与采集会话](cmdb/cmdb-05-chunked-push.md) | CMDB-04 | 3.0 | 待开发 |
| [CMDB-06 原子组装、初始化与最新快照晋升](cmdb/cmdb-06-publish-snapshot.md) | CMDB-03、05 | 3.0 | 待开发 |
| [CMDB-07 配置派生信息与模块索引](cmdb/cmdb-07-config-enrichment.md) | CMDB-06 | 2.5 | 待开发 |
| [CMDB-08 物理拓扑与模型叠层 API](cmdb/cmdb-08-topology-api.md) | CMDB-07 | 2.5 | 待开发 |
| [CMDB-09 快照物理拓扑中心](cmdb/cmdb-09-topology-ui.md) | CMDB-08 | 3.0 | 待开发 |
| [CMDB-10 设备配置、模块与历史页面](cmdb/cmdb-10-config-history-ui.md) | CMDB-09 | 3.0 | 待开发 |
| [CMDB-11 第一期真实环境累计验收](cmdb/cmdb-11-acceptance.md) | CMDB-10 | 2.0 | 待开发 |
| [SIM-01 业务关注项升级为版本化意图](simulation/sim-01-intent-v2.md) | CMDB-11 | 3.0 | 待开发 |
| [SIM-02 多设备拟变更草稿与审计](simulation/sim-02-change-drafts.md) | SIM-01 | 2.5 | 待开发 |
| [SIM-03 完整候选配置与前后差异](simulation/sim-03-full-config.md) | SIM-02 | 2.5 | 待开发 |
| [SIM-04 配置脚本输入、受限转换与预览](simulation/sim-04-command-scripts.md) | SIM-03 | 3.0 | 待开发 |
| [SIM-05 多设备候选快照与固定比较](simulation/sim-05-candidate-snapshot.md) | SIM-04 | 3.0 | 待开发 |
| [SIM-06 拓扑多设备变更交互](simulation/sim-06-change-ui.md) | SIM-05 | 3.0 | 待开发 |
| [SIM-07 Underlay 协议邻接差异与真实观测分列](simulation/sim-07-session-diff.md) | SIM-05 | 2.5 | 待开发 |
| [SIM-08 物理互联链路两端配置规则](simulation/sim-08-link-pair-rules.md) | SIM-07 | 3.0 | 待开发 |
| [SIM-09 转发环路见证](simulation/sim-09-loops.md) | SIM-05 | 2.5 | 待开发 |
| [SIM-10 有界黑洞与不可达见证](simulation/sim-10-scoped-blackholes.md) | SIM-09 | 3.0 | 待开发 |
| [SIM-11 设备接口 IP 冲突](simulation/sim-11-ip-conflicts.md) | SIM-08 | 2.0 | 待开发 |
| [SIM-12 业务连通性变化](simulation/sim-12-business-reachability.md) | SIM-01、05 | 3.0 | 待开发 |
| [SIM-13 代表流路径变化与路径策略](simulation/sim-13-path-policy.md) | SIM-12 | 3.0 | 待开发 |
| [SIM-14 网段隔离一致性](simulation/sim-14-isolation.md) | SIM-12 | 2.5 | 待开发 |
| [SIM-15 幂等检查编排与固定版本结论](simulation/sim-15-run-summary.md) | SIM-08、10、11、13、14 | 3.0 | 待开发 |
| [SIM-16 变更推演结果页面](simulation/sim-16-results-ui.md) | SIM-06、15 | 3.0 | 待开发 |
| [SIM-17 第二期真实环境累计验收](simulation/sim-17-acceptance.md) | SIM-16 | 2.5 | 待开发 |

## 每次开发的阅读与交付规则

- 先读 [总览](../README.md)、[架构](../architecture.md)、[API 契约](../api-contracts.md) 和当前 spec 的依赖。
- spec 的相对路径在文件系统上指向相邻规格；“预期改动位置”是未来代码目标，不表示已经生成。
- 以测试/验收描述为证据完成增量；记录真实命令、版本与结果，不能只写“已完成”。
- 功能失败、真实引擎环境缺失或契约未验证时保持未通过，后续门槛不能跳过。
- 修订共享接口时同步受影响 spec 和能力表；对新增功能创建新编号，保留历史决定，避免偷偷扩大当前单元。
