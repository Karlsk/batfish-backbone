# 第二、三阶段：进阶能力

状态：ADV-01～17 已完成，第二阶段验收通过；ADV-18 待验收。先通过 [MVP-25](../mvp/mvp-25-mvp-acceptance.md)，再执行本目录。第二阶段结论见[验收报告](../../advance-phase2-acceptance.md)。

## 第二阶段：日常排障增强

拓扑、BGP、ACL与已登记能力的专家入口；10份，预计14.5人天。

| Spec | 依赖 | 工作量（人天） | 状态 |
| --- | --- | ---: | --- |
| [ADV-01 三层与协议拓扑分析接口](adv-01-topology-api.md) | MVP-25 | 1.5 | 已完成 |
| [ADV-02 可交互拓扑与设备联动](adv-02-topology-ui.md) | ADV-01 | 2.0 | 已完成 |
| [ADV-03 BGP 模型状态与兼容性接口](adv-03-bgp-api.md) | ADV-02 | 1.0 | 已完成 |
| [ADV-04 BGP 状态列表与异常详情](adv-04-bgp-ui.md) | ADV-03 | 1.0 | 已完成 |
| [ADV-05 ACL 流量测试接口](adv-05-acl-test-api.md) | ADV-04 | 1.5 | 已完成 |
| [ADV-06 ACL 流量测试页面](adv-06-acl-test-ui.md) | ADV-05 | 1.5 | 已完成 |
| [ADV-07 ACL 条件搜索与无效规则接口](adv-07-acl-search-api.md) | ADV-06 | 2.0 | 已完成 |
| [ADV-08 ACL 高级诊断与证据分层](adv-08-acl-search-ui.md) | ADV-07 | 1.5 | 已完成 |
| [ADV-09 登记式专家查询入口](adv-09-expert-catalog.md) | ADV-08 | 1.5 | 已完成 |
| [ADV-10 第二阶段整体验收](adv-10-phase-two-acceptance.md) | ADV-09 | 1.0 | 已完成 |

## 第三阶段：变更验证

前置条件为ADV-10验收通过。配置/路由/可达性差异及节点/接口故障模拟；8份，预计13.0人天。

| Spec | 依赖 | 工作量（人天） | 状态 |
| --- | --- | ---: | --- |
| [ADV-11 双快照对比上下文与记录](adv-11-comparison-context.md) | ADV-10 | 1.0 | 已完成 |
| [ADV-12 配置文件差异分析](adv-12-configuration-diff.md) | ADV-11 | 2.0 | 已完成 |
| [ADV-13 路由差异分析接口](adv-13-routing-diff.md) | ADV-12 | 1.5 | 已完成 |
| [ADV-14 差异可达性分析接口](adv-14-differential-reachability.md) | ADV-13 | 2.0 | 已完成 |
| [ADV-15 变更对比工作台](adv-15-comparison-ui.md) | ADV-14 | 2.0 | 已完成 |
| [ADV-16 节点与接口故障派生快照](adv-16-fault-simulation-api.md) | ADV-15 | 1.5 | 已完成 |
| [ADV-17 故障方案向导与影响分析](adv-17-fault-simulation-ui.md) | ADV-16 | 1.5 | 已完成 |
| [ADV-18 第三阶段整体验收](adv-18-phase-three-acceptance.md) | ADV-17 | 1.5 | 待开发 |

两阶段共18份，单份≤2人天。范围以具体spec为准，不代表适配全部SDK私有或公共能力。总规则见 [规格索引](../README.md)。
