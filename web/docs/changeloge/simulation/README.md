# 第二阶段：多设备拟变更与影响检查

以 [CMDB-11](../cmdb/cmdb-11-acceptance.md) 验收过的不可变快照为基线，构建候选快照，按“差异 → Underlay → 业务/路径/隔离 → 证据”下钻。参考 [共享设计](../../cmdb-simulation-design.md)。单篇 2–3 人天；下面工作量包含目标测试与文档，不包含无法预测的 Java 引擎新能力研发。

| 规格 | 可独立验收的交付 | 估算 | 前置 |
| --- | --- | ---: | --- |
| [SIM-01](sim-01-intent-v2.md) | 版本化业务/隔离/路径意图 | 3 | CMDB-11 |
| [SIM-02](sim-02-change-drafts.md) | 多设备变更草稿与审计 | 2.5 | SIM-01 |
| [SIM-03](sim-03-full-config.md) | 完整配置编辑、版本冲突、差异 | 2.5 | SIM-02 |
| [SIM-04](sim-04-command-scripts.md) | 配置脚本受限转换与预览 | 3 | SIM-03 |
| [SIM-05](sim-05-candidate-snapshot.md) | 候选快照/固定比较/worker | 3 | SIM-04 |
| [SIM-06](sim-06-change-ui.md) | 拓扑多设备注入与推演入口 | 3 | SIM-05 |
| [SIM-07](sim-07-session-diff.md) | BGP/OSPF/ISIS 模型邻接差异与观测分列 | 2.5 | SIM-05 |
| [SIM-08](sim-08-link-pair-rules.md) | 两端链路配置一致性 | 3 | SIM-07 |
| [SIM-09](sim-09-loops.md) | 模型环路见证 | 2.5 | SIM-05 |
| [SIM-10](sim-10-scoped-blackholes.md) | 限定范围的黑洞/不可达见证 | 3 | SIM-09 |
| [SIM-11](sim-11-ip-conflicts.md) | 地址冲突分类 | 2 | SIM-08 |
| [SIM-12](sim-12-business-reachability.md) | 业务连通性变化 | 3 | SIM-01、05 |
| [SIM-13](sim-13-path-policy.md) | 代表流路径变化与路径意图 | 3 | SIM-12 |
| [SIM-14](sim-14-isolation.md) | 双向网段隔离验证 | 2.5 | SIM-12 |
| [SIM-15](sim-15-run-summary.md) | 幂等检查编排与固定版本摘要 | 3 | SIM-08、10、11、13、14 |
| [SIM-16](sim-16-results-ui.md) | 分层推演结果及证据下钻 | 3 | SIM-06、15 |
| [SIM-17](sim-17-acceptance.md) | 第二阶段真实环境累计验收 | 2.5 | SIM-16 |

脚本模式以经验证的厂商/命令子集为能力门槛；不支持时报告精确原因并引导完整配置模式。模型结果、真实观测和人工意图始终分列。未知或截断不可计为“通过”。
