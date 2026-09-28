# 领导端规格：LDR-01～12

状态：LDR-01～11 已完成，LDR-12 待开发。前置为 [ADV-18](../advance/adv-18-phase-three-acceptance.md) 全部通过。公共契约见[领导端设计](../../leader-design.md)，仍遵守 [web/AGENTS.md](../../../AGENTS.md)。每份目标不超过 2 人天；按编号串行。已完成篇的实现与真实验证证据必须随本篇记录，再推进下一篇。

| Spec | 依赖 | 人天 | 状态 |
| --- | --- | ---: | --- |
| [LDR-01 双入口与壳层](ldr-01-dual-entry.md) | ADV-18 | 1.5 | 已完成 |
| [LDR-02 业务关注项接口](ldr-02-business-concerns-api.md) | LDR-01 | 2.0 | 已完成 |
| [LDR-03 业务关注项页面](ldr-03-business-concerns-ui.md) | LDR-02 | 1.5 | 已完成 |
| [LDR-04 跨网络总览接口](ldr-04-overview-api.md) | LDR-03 | 2.0 | 已完成 |
| [LDR-05 日常总览页面](ldr-05-overview-ui.md) | LDR-04 | 2.0 | 已完成 |
| [LDR-06 检查模板与运行记录](ldr-06-check-runs-api.md) | LDR-05 | 2.0 | 已完成 |
| [LDR-07 MVP 自主检查页面](ldr-07-mvp-guided-checks.md) | LDR-06 | 2.0 | 已完成 |
| [LDR-08 ADV 排障检查页面](ldr-08-adv-guided-checks.md) | LDR-07 | 2.0 | 已完成 |
| [LDR-09 变更与故障领导视图](ldr-09-change-fault-ui.md) | LDR-08 | 2.0 | 已完成 |
| [LDR-10 固定汇报接口](ldr-10-briefings-api.md) | LDR-09 | 2.0 | 已完成 |
| [LDR-11 汇报与会议页面](ldr-11-briefings-ui.md) | LDR-10 | 2.0 | 已完成 |
| [LDR-12 领导端整体验收](ldr-12-acceptance.md) | LDR-11 | 1.5 | 待开发 |

预计合计 22.5 人天，含各篇实现、必要测试与文档，不是日历工期或容量承诺。
