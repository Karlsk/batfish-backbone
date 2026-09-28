# 第一阶段：采集、物理拓扑、配置与历史

目标是以已有采集平台的定时推送建立版本化 CMDB，不改变现有手工上传和技术/领导入口。共享设计见 [版本化资产与推演设计](../../cmdb-simulation-design.md)。每篇 2–3 人天，按编号单篇实现、验收、提交；本阶段全通过才进入 SIM。

| 规格 | 交付 | 估算 | 前置 |
| --- | --- | ---: | --- |
| [CMDB-01](cmdb-01-identity-revisions.md) | 稳定身份、版本模型与迁移 | 3 | LDR-12 |
| [CMDB-02](cmdb-02-read-api.md) | 快照级资产与历史只读 API | 2.5 | CMDB-01 |
| [CMDB-03](cmdb-03-manual-drafts.md) | 人工设备/链路/配置草稿 CRUD | 3 | CMDB-02 |
| [CMDB-04](cmdb-04-bundle-contract.md) | node.json 与物理拓扑 ZIP 契约 | 2.5 | CMDB-01 |
| [CMDB-05](cmdb-05-chunked-push.md) | 分段推送、认证、幂等与恢复 | 3 | CMDB-04 |
| [CMDB-06](cmdb-06-publish-snapshot.md) | 组装、初始化、原子晋升 | 3 | CMDB-03、05 |
| [CMDB-07](cmdb-07-config-enrichment.md) | 配置派生字段、模块索引与来源 | 2.5 | CMDB-06 |
| [CMDB-08](cmdb-08-topology-api.md) | 物理图和模型叠层读取 | 2.5 | CMDB-07 |
| [CMDB-09](cmdb-09-topology-ui.md) | 快照拓扑中心及设备交互 | 3 | CMDB-08 |
| [CMDB-10](cmdb-10-config-history-ui.md) | 设备配置、模块和历史页面 | 3 | CMDB-09 |
| [CMDB-11](cmdb-11-acceptance.md) | 第一阶段真实环境验收 | 2 | CMDB-10 |

完整性和来源是门槛：没有物理输入时标“未提供物理拓扑”；没有配置或不支持的配置只能展示原文和警告。`node.json` 不交给 SDK。规模上限以配置和测试证据为准，分段不等于无限制。
