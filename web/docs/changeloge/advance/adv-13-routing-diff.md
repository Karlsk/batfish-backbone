# ADV-13 路由差异分析接口

- 状态：已完成（累计验收通过，待提交）
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

- [x] 登记比较限定的 routes 差异入口，将比较上下文传给独占 Session。
- [x] 逐条保留 SDK 路由行及多路径，不用简单的前缀字典覆盖。
- [x] 保存两侧值与原始差异字段，复用分页/导出。
- [x] 运行下述验证，记录实际命令与结果，更新本文及索引状态。

## 测试与验收

- test_route_added_removed_direction：已知变化方向正确。
- test_ecmp_route_change：同前缀多下一跳不会丢失。
- test_no_differences：只在所选范围内报告无差异。

后端测试在 `web/backend` 下使用 `uv run pytest` 指定上述测试文件；集成测试连接版本固定的隔离 Batfish 测试网络，不操作团队生产网络。

验收成功同时要求：契约与文档一致、失败行为可解释、无跨层/跨模块越界、没有把 mock 验证宣称为真实 SDK 验证。共享约束中的身份、版本、模型覆盖和结果截断规则均适用。

## 非目标与实施边界

- 不做 BGP 策略等价证明或自动判定变更可上线。

## 完成记录

基于 `daffc4a41c` 实现。变更位于公共有类型选择器与 routes 请求契约、`analysis` 的注册路由 service/controller、`changes/route_analysis.py` 与比较 API、composition 分派，以及 `test_route_diff.py` 和真实 API/独立 worker 冒烟。单快照 routes 与双快照 routes-diff 复用同一请求模型；后者固定候选为 SDK snapshot、基线为 reference_snapshot。结果为现有 table，保留 `Entry_Presence`、`Snapshot_*`/`Reference_*` 原始列，新增 `Change`；按行保留 ECMP，不覆盖相同前缀。直接 SDK 实测方向：`Only in Snapshot`=added，`Only in Reference`=removed，`Changed`=changed；混入的 `Unchanged` 行从变化列表过滤。虽然本仓库静态 routes 问题模板的 `differential` 字段为 false，锁定 SDK+引擎的双快照调用实际返回上述列；升级版本需要复验。

真实 Batfish/PostgreSQL 环境累计后端 351 项、冒烟 13 项、前端 81 项、浏览器 23 项、新 HTTPS 部署恢复及浅色/深色双用户验收均通过；Ruff、锁文件、类型、构建、格式和 OpenAPI 类型检查通过。引擎 revision `7d0deeeac4a09973b3876327f6aef721ee12f955`，JAR SHA-256 `0927de7c740bc72f999870e842605baad9a7cb6ea66e4b01fb9a6037bea00193`，Pybatfish `2026.9.17.3748`，迁移 0009。实际命令与证据见[ADV-13 验收](../../evidence/adv-13-verification.md)。空结果仅针对所选范围；路由变化不证明配置策略等价或现场转发效果。第三阶段下一依赖 ADV-14 已可开始。
