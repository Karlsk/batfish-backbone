# MVP-01 SDK 兼容性与能力基线

- 状态：已完成
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

本篇实现与验证文件：

- `web/backend/tests/integration/test_sdk_baseline.py`
- `web/backend/tests/fixtures/small_network/`
- `web/docs/sdk-compatibility.md`

## 实施步骤

- [x] 记录服务构建来源，固定候选 SDK 版本；用独立测试网络执行最小调用。
- [x] 保存结构化字段清单并验证实验模板已加载，不把 experimental 自动视为禁用。
- [x] 验证两个独占 Session 在同名显示标签、不同内部快照下不串用，并记录超时限制。
- [x] 更新能力覆盖表和部署版本基线；失败项回写受影响 spec。
- [x] 运行下述验证，记录实际命令与结果，更新本文及索引状态。

## 测试与验收

- test_minimal_questions_match_expected：节点/路由/路径得到可解释结果。
- test_session_context_isolation：交错执行返回各自 network/snapshot 数据。
- test_unsupported_or_missing_question：能力缺失可检测，不伪装成功。

后端骨架尚未建立，在 `web/backend` 下用临时依赖环境验证，不依赖后续 pyproject。原候选 Pybatfish 0.36.0 安装失败：文档/引擎版本号不是可安装的 Python 包发行号。2026-09-25 实测组合为 Python 3.12.12 + Pybatfish 2026.9.17.3748 + pytest 8.4.2，执行命令：

```bash
uv run --no-project --python 3.12 --with pybatfish==2026.9.17.3748 --with pytest==8.4.2 pytest tests/integration/test_sdk_baseline.py -q
```

测试前显式配置隔离测试引擎地址、唯一网络前缀、构建清单及新证据输出路径；不可使用团队生产网络。完整环境和启动步骤见 [兼容性报告](../../sdk-compatibility.md)。候选失败需保留证据后换版复验，MVP-02 再形成应用锁文件。

验收成功同时要求：契约与文档一致、失败行为可解释、无跨层/跨模块越界、没有把 mock 验证宣称为真实 SDK 验证。共享约束中的身份、版本、模型覆盖和结果截断规则均适用。

## 非目标与实施边界

- 不安装生产服务、不修改 Java 引擎、不实现 Web API。

## 完成记录

2026-09-25：已完成。新增上述集成测试、两份合成 Huawei/H3C fixture、[实施计划](../../plans/mvp-01-sdk-baseline.md)、[兼容性报告](../../sdk-compatibility.md) 和 [结构化证据](../../evidence/mvp-01-sdk-baseline.json)；同步能力表、运行设计及受影响 spec 说明。

- 构建：仓库根目录执行 `bazel build //projects/allinone:allinone_main_deploy.jar --jobs=6 --noshow_progress --distdir=/private/tmp/h3c-bazel.l0kCKY`，退出码 0。引擎 revision `7d0deeeac4a09973b3876327f6aef721ee12f955`，JAR 摘要见报告。
- 验证：`web/backend` 下执行上述命令并追加 `--junitxml=/private/tmp/batfish-mvp01-birscy6n/pytest-final.xml`；全部 7 项通过，0 跳过，6.14 秒。引擎独立监听 `127.0.0.1:19996`，使用全新临时存储。
- 75 个模板全部核验；核心问题输出、初始化警告、默认快照 A/B/A/B 隔离及后台任务状态/答案读取实测通过。超时测试单独使用受控 HTTP 服务，没有将其当作引擎取消测试。
- 独立审查指出的默认上下文断言和调用证据覆盖问题均修复并复验。没有修改 Java、实现 Web API 或引入应用骨架。
- 限制：仅两台合成设备；没有验证容量、引擎重启后句柄持久性或运行中取消。MVP-09 保留保守恢复策略。本篇满足 MVP-02 前置条件，后续篇目仍待开发。
