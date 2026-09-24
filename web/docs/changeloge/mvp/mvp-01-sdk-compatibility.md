# MVP-01 SDK 兼容性与能力基线

- 状态：待开发
- 阶段：1
- 依赖：无
- 预计工作量：1.0 人天（实现/验证 0.5 + 测试 0.25 + 文档/自检 0.25），依赖就绪后计；超过 2 人天先拆分。
- 共享约束：[架构](../../architecture.md)、[API 契约](../../api-contracts.md)、[前端规范](../../frontend.md)、[运行设计](../../operations.md)、[验收](../../validation.md)。

## 需求与目标

先验证当前分支服务与固定 Pybatfish 的真实调用契约，为后续封装提供可复现依据。

- 覆盖版本、模板、网络/快照、初始化诊断、nodes/interfaces/routes/lpmRoutes/traceroute。
- 只使用合成/仓库公开样例；记录 Session 公开 API 的阻塞、超时和结果结构。

## 设计与接口

- 产出兼容性报告：engine git revision、SDK/Python 版本、模板集合、参数与结果 schema 摘要。
- 确认 set_network 是否创建资源、init_snapshot 的返回/告警行为，以及是否存在公开任务句柄；不能假设支持取消或恢复。
- 若未拿到引擎执行证据，状态为未通过；后续 SDK 适配项不能据此开始验收。

沿用 api → service → controller；所有跨业务模块调用经过 service。非 SDK 存储由本模块 repository 负责。浏览器不接触 SDK 会话或连接参数。

## 预期改动位置

以下是实现时的目标路径，本次文档编写不创建代码文件：

- `web/backend/tests/integration/test_sdk_baseline.py`
- `web/backend/tests/fixtures/small_network/`
- `web/docs/sdk-compatibility.md`

## 实施步骤

- [ ] 记录服务构建来源，固定候选 SDK 版本；用独立测试网络执行最小调用。
- [ ] 保存结构化字段清单并验证实验模板已加载，不把 experimental 自动视为禁用。
- [ ] 验证两个独占 Session 在同名显示标签、不同内部快照下不串用，并记录超时限制。
- [ ] 更新能力覆盖表和部署版本基线；失败项回写受影响 spec。
- [ ] 运行下述验证，记录实际命令与结果，更新本文及索引状态。

## 测试与验收

- test_minimal_questions_match_expected：节点/路由/路径得到可解释结果。
- test_session_context_isolation：交错执行返回各自 network/snapshot 数据。
- test_unsupported_or_missing_question：能力缺失可检测，不伪装成功。

此时后端骨架尚未建立，先在 `web/backend` 下用临时依赖环境验证，不依赖后续 pyproject。首个候选组合为 Python 3.12 + Pybatfish 0.36.0（根据当前仓库和官方命令文档），执行示例：

```bash
uv run --no-project --python 3.12 --with pybatfish==0.36.0 --with pytest pytest tests/integration/test_sdk_baseline.py
```

测试前显式配置隔离测试引擎地址及唯一网络前缀；不可使用团队生产网络。若候选组合不兼容，记录失败证据后更换候选并重跑，最终报告固定实际验证的完整版本；MVP-02 再形成应用锁文件。此命令是后续实施说明，本次没有执行。

验收成功同时要求：契约与文档一致、失败行为可解释、无跨层/跨模块越界、没有把 mock 验证宣称为真实 SDK 验证。共享约束中的身份、版本、模型覆盖和结果截断规则均适用。

## 非目标与实施边界

- 不安装生产服务、不修改 Java 引擎、不实现 Web API。

## 完成记录

当前尚未开发或运行本 spec 的产品测试。实施者完成后在本节记录实际文件、验证命令、结果、引擎/SDK版本（如涉及）和剩余限制；存在验收失败时保持未通过状态。
