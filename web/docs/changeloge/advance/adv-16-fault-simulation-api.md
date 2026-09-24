# ADV-16 节点与接口故障派生快照

- 状态：待开发
- 阶段：3
- 依赖：[ADV-15](../advance/adv-15-comparison-ui.md)
- 预计工作量：1.5 人天（实现/验证 1.0 + 测试 0.25 + 文档/自检 0.25），依赖就绪后计；超过 2 人天先拆分。
- 共享约束：[架构](../../architecture.md)、[API 契约](../../api-contracts.md)、[前端规范](../../frontend.md)、[运行设计](../../operations.md)、[验收](../../validation.md)。

## 需求与目标

以不可变基线创建节点或接口停用的候选快照。

- fork_snapshot、节点/接口存在性校验、派生来源、初始化质量和引用保护。

## 设计与接口

- POST S/fault-scenarios：display_name、deactivate_nodes 或 deactivate_interfaces 至少一项 → {snapshot_id,job_id}。
- service 使用快照/设备公共服务校验；controller 调用 fork_snapshot，overwrite=false。
- 未知对象422；基线不变；新快照通过同样质量门后才允许创建 comparison。
- 通过 ResourceLifecycleService 检查未删除派生快照对基线的引用，和快照删除共享锁；不能边派生边把基线删掉。

沿用 api → service → controller；所有跨业务模块调用经过 service。非 SDK 存储由本模块 repository 负责。浏览器不接触 SDK 会话或连接参数。

## 预期改动位置

以下是实现时的目标路径，本次文档编写不创建代码文件：

- `web/backend/app/modules/changes/api.py`
- `web/backend/app/modules/changes/service.py`
- `web/backend/app/modules/changes/controller.py`
- `web/backend/tests/test_fault_scenarios.py`

## 实施步骤

- [ ] 登记故障方案请求和派生关系，使用全新内部名称。
- [ ] 调用 SDK fork，处理返回 None/异常/未知状态，不标假成功。
- [ ] 复用初始化质量与引擎占用语义，新增基线引用删除保护。
- [ ] 运行下述验证，记录实际命令与结果，更新本文及索引状态。

## 测试与验收

- test_base_immutable：派生后原始配置/快照标识与结果不改变。
- test_node_and_interface_targets：合法对象有效，未知对象拒绝。
- test_fork_failure：失败保留方案和错误，无 ready 半成品。

后端测试在 `web/backend` 下使用 `uv run pytest` 指定上述测试文件；集成测试连接版本固定的隔离 Batfish 测试网络，不操作团队生产网络。

验收成功同时要求：契约与文档一致、失败行为可解释、无跨层/跨模块越界、没有把 mock 验证宣称为真实 SDK 验证。共享约束中的身份、版本、模型覆盖和结果截断规则均适用。

## 非目标与实施边界

- 不接受任意 add_files、配置补丁、自动N-1枚举或真实设备停用。

## 完成记录

当前尚未开发或运行本 spec 的产品测试。实施者完成后在本节记录实际文件、验证命令、结果、引擎/SDK版本（如涉及）和剩余限制；存在验收失败时保持未通过状态。
