# MVP-12 分析目录与结果标准化

- 状态：已完成
- 阶段：1
- 依赖：[MVP-11](../mvp/mvp-11-initialization-diagnostics.md)
- 预计工作量：2.0 人天（实现/验证 1.25 + 测试 0.5 + 文档/自检 0.25），依赖就绪后计；超过 2 人天先拆分。
- 共享约束：[架构](../../architecture.md)、[API 契约](../../api-contracts.md)、[前端规范](../../frontend.md)、[运行设计](../../operations.md)、[验收](../../validation.md)。

## 需求与目标

建立所有分析复用的受控参数目录和可分页结果契约。

- 能力元数据、typed options、标准表格/Trace 序列化、结果持久化、来源和截断。
- 已登记种类的 handler 装配；具体问题执行在后续 spec。

## 设计与接口

- GET /capabilities；GET /results/{id}、/rows、/flows、/flows/{flow_id}/traces。
- AnalysisService.submit/execute、AnalysisController.run 和 ResultsService.publish 遵循公共契约。
- 结果与任务成功共同发布；结果缓存包含版本/快照/基线/归一化参数。

沿用 api → service → controller；所有跨业务模块调用经过 service。非 SDK 存储由本模块 repository 负责。浏览器不接触 SDK 会话或连接参数。

## 预期改动位置

以下是实现时的目标路径，本次文档编写不创建代码文件：

- `web/backend/app/modules/analysis/service.py`
- `web/backend/app/modules/analysis/registry.py`
- `web/backend/app/modules/results/api.py`
- `web/backend/app/modules/results/service.py`
- `web/backend/app/modules/results/repository.py`
- `web/backend/tests/test_results.py`

## 实施步骤

- [x] 定义能力 schema 和分阶段开关，未知 options 拒绝并给字段路径。
- [x] 归一化 NaN→null、集合确定顺序、嵌套 SDK 值→普通结构，不把 Trace 字符串化。
- [x] 实现结果原子发布、稳定分页、行/字节上限和截断元数据。
- [x] 添加版本化缓存键；缓存命中仍记录当前发起人的 job。
- [x] 运行下述验证，记录实际命令与结果，更新本文及索引状态。

## 测试与验收

- test_unknown_options_rejected：未登记/上下文覆盖参数 422。
- test_structured_serialization：嵌套 Flow/Trace、空集合、NaN 保持语义。
- test_stable_pagination_and_truncation：分页不重不漏，超限明确标记。
- test_cache_context_versions：不同快照/SDK 版本不共用答案。

后端测试在 `web/backend` 下使用 `uv run pytest` 指定上述测试文件；集成测试连接版本固定的隔离 Batfish 测试网络，不操作团队生产网络。

验收成功同时要求：契约与文档一致、失败行为可解释、无跨层/跨模块越界、没有把 mock 验证宣称为真实 SDK 验证。共享约束中的身份、版本、模型覆盖和结果截断规则均适用。

## 非目标与实施边界

- 不做任意问题入口、CSV 导出或复杂跨结果搜索。

## 完成记录

2026-09-25 完成analysis registry/service/controller和公共结构化结果DTO、results API/service/缓存及文件发布、迁移0007、composition登记analysis handler。目录中的五类具体查询本篇保持disabled；SDK测试通过明确测试登记启用query，产品专用接口由MVP-13～15交付。

嵌套Flow/Trace/NextHop保留JSON结构，NaN/无穷→null、集合稳定排序。表格/Flow/Trace分页保留来源、模型覆盖和截断，支持登记列排序/eq/contains过滤。持久化默认100MiB/100000行上限，可配置；不声称约束SDK/引擎构造答案的内存。缓存键包含上下文/内容摘要/问题版本/有效参数/输出限额，命中仍保留当前用户新任务。

Handler新增可选publish阶段，worker在SDK与预算检查后，在同一数据库事务发布结果元数据/缓存及job成功；期间发生中断或成功写入失败则一起回滚。已原子发布而未引用的文件保留待核对，不能作为API可见结果。JobsService.finish支持公共共享事务，保留原handler兼容。旧虚拟analysis任务缺少目录参数时重试返回409。

仓库根执行 `web/backend/.venv/bin/python web/scripts/lab.py seed`、`smoke`、`verify`：真实HTTP冒烟 **12 passed**；MVP-01～12累计 **231 passed、0 skipped**。9项结果测试覆盖结构标准化/未知options/缓存上下文、行字节与trace截断/稳定数值分页、共同发布回滚、发布中断、两套真实node/trace结果、跨用户缓存任务归属、运行时升级禁止旧答案。分层守卫新增registry仅依赖schemas的边界（4项允许/拒绝用例），未放宽跨模块规则。Ruff、锁文件、文档链接和Git空白检查通过。见 [验收证据](../../evidence/mvp-12-verification.json)。

独立审查发现缓存版本只使用初始化记录的问题：先复现升级后错误缓存命中，再增加worker缓存前真实版本核验；不一致时CONFLICT并明确要求重新初始化，旧结果仍可读。复审无阻断。环境为固定Batfish0.36.0/Pybatfish2026.9.17.3748/JAR，未修改Java；MVP-13依赖就绪。
