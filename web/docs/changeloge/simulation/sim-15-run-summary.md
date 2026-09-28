# SIM-15 幂等检查编排与固定版本结论

- 状态：待开发；阶段：推演二期；依赖：[SIM-08](sim-08-link-pair-rules.md)、[SIM-10](sim-10-scoped-blackholes.md)、[SIM-11](sim-11-ip-conflicts.md)、[SIM-13](sim-13-path-policy.md)、[SIM-14](sim-14-isolation.md)；预计：3 人天。

## 交付与接口

`POST /change-drafts/{id}/check-runs` 对已就绪 candidate 创建幂等检查运行，固定草稿版本、两快照、意图版本、规则/转换器/引擎版本和任务清单。按现有引擎串行约束执行；先汇总配置/协议 Underlay，再继续业务、路径、隔离（Underlay 有失败仍执行后续以呈现影响，但警告不消失）。子项独立 `pass/fail/unknown/not_run`，部分失败可重试，不能整体假绿。提供状态、阶段、摘要和证据引用 API；系统结论不可人工改写，旧运行不随新采集变化。

## 验收

重复提交、worker 重启/失联、个别 SDK 错误、引擎未知占用、意图更新、源快照暂不可打开及结果截断下，运行记录和固定结论稳定；审计与现有固定汇报服务只通过 service 对接。
