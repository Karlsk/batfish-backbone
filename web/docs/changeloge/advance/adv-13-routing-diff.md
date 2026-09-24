# ADV-13 路由差异分析接口

- 状态：待开发
- 阶段：3
- 依赖：[ADV-12](../advance/adv-12-configuration-diff.md)
- 预计工作量：1.5 人天（实现/验证 1.0 + 测试 0.25 + 文档/自检 0.25），依赖就绪后计；超过 2 人天先拆分。
- 共享约束：[架构](../../architecture.md)、[API 契约](../../api-contracts.md)、[前端规范](../../frontend.md)、[运行设计](../../operations.md)、[验收](../../validation.md)。

## 需求与目标

用户能查看候选相对基线新增、消失及发生变化的路由。

- SDK routes differential、节点/VRF/前缀/协议筛选、差异列归一化。

## 设计与接口

- POST /comparisons/{id}/analyses/routes-diff → job，参数复用 routes schema。
- 使用 snapshot=candidate、reference_snapshot=baseline；保留 SDK 原始差异标记并映射 added/removed/changed。
- 每个标记的方向必须用已知增删路由样例实证，不能靠列名猜测。

沿用 api → service → controller；所有跨业务模块调用经过 service。非 SDK 存储由本模块 repository 负责。浏览器不接触 SDK 会话或连接参数。

## 预期改动位置

以下是实现时的目标路径，本次文档编写不创建代码文件：

- `web/backend/app/modules/changes/service.py`
- `web/backend/app/modules/changes/controller.py`
- `web/backend/tests/test_route_diff.py`

## 实施步骤

- [ ] 登记差异 routes 能力，将比较上下文传给独占 Session。
- [ ] 以完整路由键处理多路径，不用简单的前缀字典覆盖。
- [ ] 保存两侧值与原始差异字段，复用分页/导出。
- [ ] 运行下述验证，记录实际命令与结果，更新本文及索引状态。

## 测试与验收

- test_route_added_removed_direction：已知变化方向正确。
- test_ecmp_route_change：同前缀多下一跳不会丢失。
- test_no_differences：只在所选范围内报告无差异。

后端测试在 `web/backend` 下使用 `uv run pytest` 指定上述测试文件；集成测试连接版本固定的隔离 Batfish 测试网络，不操作团队生产网络。

验收成功同时要求：契约与文档一致、失败行为可解释、无跨层/跨模块越界、没有把 mock 验证宣称为真实 SDK 验证。共享约束中的身份、版本、模型覆盖和结果截断规则均适用。

## 非目标与实施边界

- 不做 BGP 策略等价证明或自动判定变更可上线。

## 完成记录

当前尚未开发或运行本 spec 的产品测试。实施者完成后在本节记录实际文件、验证命令、结果、引擎/SDK版本（如涉及）和剩余限制；存在验收失败时保持未通过状态。
