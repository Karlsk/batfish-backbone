# MVP-13 设备与接口分析接口

- 状态：已完成
- 阶段：1
- 依赖：[MVP-12](../mvp/mvp-12-analysis-results.md)
- 预计工作量：1.5 人天（实现/验证 1.0 + 测试 0.25 + 文档/自检 0.25），依赖就绪后计；超过 2 人天先拆分。
- 共享约束：[架构](../../architecture.md)、[API 契约](../../api-contracts.md)、[前端规范](../../frontend.md)、[运行设计](../../operations.md)、[验收](../../validation.md)。

## 需求与目标

通过首批专用接口验证分析管道，并支持页面设备选择。

- nodeProperties/interfaceProperties、节点/接口/属性筛选、结果字段展示映射。

## 设计与接口

- POST S/analyses/nodes、POST S/analyses/interfaces → 202 JobDTO。
- nodes/interfaces 支持显式字面选择或专家表达式，模式清晰，字面值需安全转义。
- 仅支持模型已有属性，不将解析出的 IPv6 地址等同于可做 IPv6 仿真。

沿用 api → service → controller；所有跨业务模块调用经过 service。非 SDK 存储由本模块 repository 负责。浏览器不接触 SDK 会话或连接参数。

## 预期改动位置

以下是实现时的目标路径，本次文档编写不创建代码文件：

- `web/backend/app/modules/analysis/api.py`
- `web/backend/app/modules/analysis/schemas/inventory.py`
- `web/backend/app/modules/analysis/controllers/inventory.py`
- `web/backend/tests/test_inventory.py`

## 实施步骤

- [x] 登记两类问题的参数、展示列和 result_kind。
- [x] 实现 controller 映射，service 判断快照状态与能力。
- [x] 用结果接口分页返回；用于选择器的数据仍来源于绑定快照的结果。
- [x] 运行下述验证，记录实际命令与结果，更新本文及索引状态。

## 测试与验收

- test_inventory_matches_sdk：稳定列与直接 SDK 一致。
- test_literal_node_names：带特殊字符的设备名称可被正确选择。
- test_no_matching_nodes：正常空结果，有明确说明。

后端测试在 `web/backend` 下使用 `uv run pytest` 指定上述测试文件；集成测试连接版本固定的隔离 Batfish 测试网络，不操作团队生产网络。

验收成功同时要求：契约与文档一致、失败行为可解释、无跨层/跨模块越界、没有把 mock 验证宣称为真实 SDK 验证。共享约束中的身份、版本、模型覆盖和结果截断规则均适用。

## 非目标与实施边界

- 不做拓扑、BGP 专页或设备实时状态。

## 完成记录

2026-09-25 完成两个202分析接口、inventory类型/属性目录、固定SDK映射与能力登记。schemas改为包以容纳后续专用参数；默认精简列，专家属性由固定引擎白名单约束。字面名称编码为逐字符十六进制的锚定Java正则，含逗号/方括号/正则字符/数字前缀的名称仍完整匹配；遵循Batfish不区分大小写规则。高级表达式显式选择，不混用模式。空结果成功返回稳定列与No matching rows，保留模型覆盖警告。

API/worker使用相同生产登记；真实HTTP冒烟从MVP-12测试专用query替换为正式nodes/interfaces提交和CLI worker执行，仍保留共享结果/能力开关/版本缓存验收，未删减旧业务约束。补齐CSRF/未知参数/上下文覆盖拒绝、幂等与错误资源身份检查。

独立审查发现错误专家表达式会冻结引擎：先真实复现，再改用已验证的公开background/get_work_status/get_answer。同一Session内等待，当前question PUT400只证明参数被拒绝，可释放占用；已知终态失败返回ENGINE_QUERY_FAILED。SDK本地校验返回VALIDATION_ERROR；传输/工作提交不确定/非终态超时仍unknown，不读取私有方法或解析异常字符串。补齐TERMINATEDBYUSER；测试先红后绿。独立复审无剩余阻断。

仓库根执行 `web/backend/.venv/bin/python web/scripts/lab.py seed`、`smoke`、`verify`：真实HTTP冒烟 **12 passed**；MVP-01～13累计 **246 passed、0 skipped**。新增15项库存验收：两套配置SDK逐行/列对照、接口名称过滤、四种特殊节点、空结果、权限/幂等、两类畸形语法/正则失败后正常查询、两种不确定提交保持占用、三种终态/超时处理。Ruff、锁文件、文档链接与Git空白检查通过。见 [验收证据](../../evidence/mvp-13-verification.json)。

固定Batfish0.36.0/Pybatfish2026.9.17.3748/JAR，新增requests直接依赖声明但锁定包集合未变。未修改Java；只验证模型已有属性和Web功能，不将IPv6属性解读为IPv6仿真支持。MVP-14依赖就绪。
