# ADV-09 登记式专家查询入口

- 状态：待开发
- 阶段：2
- 依赖：[ADV-08](../advance/adv-08-acl-search-ui.md)
- 预计工作量：1.5 人天（实现/验证 1.0 + 测试 0.25 + 文档/自检 0.25），依赖就绪后计；超过 2 人天先拆分。
- 共享约束：[架构](../../architecture.md)、[API 契约](../../api-contracts.md)、[前端规范](../../frontend.md)、[运行设计](../../operations.md)、[验收](../../validation.md)。

## 需求与目标

专家可以统一访问已经适配的能力，而无需为每个参数另写页面。

- 通用查询入口、JSON Schema 表单、专家 options JSON 编辑、服务端复核。

## 设计与接口

- POST S/analyses/query：question_id、parameters；只接受已登记 enabled 能力，调用同一 AnalysisService。
- GET /capabilities 为唯一能力目录；query 不能动态导入 SDK 方法，不能新增网络/文件操作。
- 每个问题使用已有专用 schema 校验，结果仍为统一 ResultEnvelope。

沿用 api → service → controller；所有跨业务模块调用经过 service。非 SDK 存储由本模块 repository 负责。浏览器不接触 SDK 会话或连接参数。

## 预期改动位置

以下是实现时的目标路径，本次文档编写不创建代码文件：

- `web/backend/app/modules/analysis/api.py`
- `web/backend/app/modules/analysis/service.py`
- `web/frontend/src/features/expert/`
- `web/backend/tests/test_expert_query.py`
- `web/frontend/src/features/expert/expert.test.tsx`

## 实施步骤

- [ ] 实现目录查询与注册表分派，对 disabled/未知问题返回明确错误。
- [ ] 生成基础参数/高级 options 表单，JSON 编辑支持错误路径展示。
- [ ] 验证专用入口和专家入口对等，不扩大本阶段问题集合。
- [ ] 运行下述验证，记录实际命令与结果，更新本文及索引状态。

## 测试与验收

- test_expert_equivalent_to_dedicated：相同有效参数得到相同结果。
- test_arbitrary_method_rejected：__import__、连接参数、未登记问题都无法调用。
- expert.test.tsx：JSON错误不丢输入，基础模式能查看有效高级条件。

后端测试在 `web/backend` 下使用 `uv run pytest` 指定上述测试文件；集成测试连接版本固定的隔离 Batfish 测试网络，不操作团队生产网络。

前端组件测试在 `web/frontend` 下使用 `pnpm exec vitest run` 指定上述 `.test.tsx` 文件；页面交互同时按前端规范人工检查。

验收成功同时要求：契约与文档一致、失败行为可解释、无跨层/跨模块越界、没有把 mock 验证宣称为真实 SDK 验证。共享约束中的身份、版本、模型覆盖和结果截断规则均适用。

## 非目标与实施边界

- 不宣称已经覆盖完整 SDK；未登记能力保持后续范围。

## 完成记录

当前尚未开发或运行本 spec 的产品测试。实施者完成后在本节记录实际文件、验证命令、结果、引擎/SDK版本（如涉及）和剩余限制；存在验收失败时保持未通过状态。
