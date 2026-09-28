# SIM-12 业务连通性变化

- 状态：待开发；阶段：推演二期；依赖：[SIM-01](sim-01-intent-v2.md)、[SIM-05](sim-05-candidate-snapshot.md)；预计：3 人天。

## 交付与接口

以固定 business concern 版本及 comparison 的 baseline → candidate 方向，复用现有差异可达性分析 service，按源/目标网段、协议/端口及起点逐项查询。输出 `lost/gained/unchanged_within_scope/unknown`、示例流、范围、覆盖和两版结果引用；TCP/UDP 端口及方向按契约映射。没有见证只表示查询约束内未发现成功/失败变化；超时、截断或模型覆盖不足必须为 `unknown`。不由该结果推断路径不变。

## 验收

可达变不可达、反向、两版仍可达但路径变化、网段限制、IP 协议/端口、旧意图版本与 SDK 原始示例一致；缓存键含快照、意图版本和有效参数。
