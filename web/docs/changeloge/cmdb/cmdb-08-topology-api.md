# CMDB-08 物理拓扑与模型叠层 API

- 状态：待开发；阶段：采集一期；依赖：[CMDB-07](cmdb-07-config-enrichment.md)；预计：2.5 人天。

## 交付与接口

`GET /api/v1/networks/{id}/cmdb/snapshots/{sid}/topology?layers=physical,layer3,bgp,ospf,isis` 返回稳定设备 ID、物理双端接口、来源、采集时间及每个图层的状态/截断。物理层只来自验证后的 Layer-1 输入；L3/协议层复用 analysis/results service 的既有异步结果，未缓存时返回 `not_run` 和可提交的分析入口，GET 不直连 SDK。支持节点焦点、跳数、分页/上限；节点缺配置或外部端点明确标注。图层语义区分物理连接、模型邻接与真实会话观测，不把协议边当光纤。

## 验收

同两节点多链路、单端缺失、孤立设备、跨快照切换、无 L1 旧快照、异步图层尚未就绪和结果截断均有 API/真实引擎验证；同一 `device_id` 在所有图层可关联，不能混合两个快照的边。
