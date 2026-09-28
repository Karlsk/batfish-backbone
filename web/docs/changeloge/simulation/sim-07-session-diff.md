# SIM-07 Underlay 协议邻接差异与真实观测分列

- 状态：待开发；阶段：推演二期；依赖：[SIM-05](sim-05-candidate-snapshot.md)；预计：2.5 人天。

## 交付与接口

固定 comparison 上复用 analysis service，分别查询基线/候选的 BGP、OSPF、ISIS 模型邻接并按稳定端点/协议归一化为新增、消失和属性变化。真实会话观测设独立字段 `observed_status/observed_at/source`，只有确有同步数据才展示，未同步时为 `not_observed`，绝不从模型边填充。解析警告、协议不支持和结果截断附到每条结论。结果由 worker 缓存，GET 仅读结果。

## 验收

四设备派生邻接变化与原 SDK 行核对；模型正常但真实观测缺失、未知邻居、方向重复、多 VRF 与截断均有断言；不能显示“真实邻居正常”的无依据结论。
