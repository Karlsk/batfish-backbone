# SIM-05 多设备候选快照与固定比较

- 状态：待开发；阶段：推演二期；依赖：[SIM-04](sim-04-command-scripts.md)；预计：3 人天。

## 交付与接口

`POST /change-drafts/{id}/candidates` 仅在所有已选设备有完整候选配置、脚本转换已保存且基线/草稿版本仍有效时，提交幂等 worker 任务。先在固定 SDK/引擎上证明 `fork_snapshot(add_files=...)` 对同名配置的替换语义与基线不变性；若不能安全替换，改由受控文件卷组装完整候选包并 `init_snapshot(overwrite=false)`，不得靠未验证的文件覆盖假设。controller 只调用公开 SDK，并验证最终文件、初始解析质量和设备集合。成功后建立 baseline → candidate 的现有 comparison，保存草稿版本/脚本摘要/引擎版本。失败、超时或占用未知时保留诊断和草稿，不能发布 ready 候选或复用错误快照；重试新内部名称。禁止下发真实设备。

## 验收

在真实 Batfish 上对 Cisco 四设备同时变更两台，比较文件内容与模型解析；单台失败、缺配置、并发提交、任务重试/重启恢复、基线删除引用和旧比较不变均通过。
