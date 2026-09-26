# ADV-09 登记式专家查询入口

- 状态：已完成
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

- [x] 实现目录查询与注册表分派，对 disabled/未知问题返回明确错误。
- [x] 生成基础参数/高级 options 表单，JSON 编辑支持错误路径展示。
- [x] 验证专用入口和专家入口对等，不扩大本阶段问题集合。
- [x] 运行下述验证，记录实际命令与结果，更新本文及索引状态。

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

2026-09-26 已完成：`analysis/api.py` 增加严格外层 `ExpertQueryRequest` 的 `POST S/analyses/query`；`AnalysisService.submit_query` 调用同一个注册表校验、资源权限、任务与结果路径，不增加 controller 的 SDK 分派。能力目录增加对应请求模型完整 `parameters_schema`，与已有 `options_schema`、默认值和启用状态共同驱动 `features/expert/` 页面。基础字段按 JSON Schema 顶层生成，复杂对象用 JSON 字段输入，高级 options 折叠编辑；错误保留输入并显示 `body.parameters...` 路径，基础视图可查看包含默认值的预期有效参数。未知、禁用及未登记问题不会进入 SDK。

真实 Cisco 四设备快照上，专家 `nodes` 查询与专用 `nodes` 查询命中同一规范化结果；`host`、上下文覆盖和任意问题名被拒绝。后端 `test_expert_query.py`、前端 `expert.test.tsx`、真实浏览器 `tests/expert.spec.ts` 通过。本篇及此前 MVP-01～25、ADV-01～09 累计回归：后端329项、真实服务冒烟12项、前端81项、浏览器22项；全新 HTTPS 部署、worker 失联对账、离线备份/新卷恢复及恢复后的明暗主题、双用户验收均通过。运行 `lab.py verify/smoke`、`pnpm test/build/check:api/format:check`、`pnpm exec playwright test`、`verify_deployment.py` 和生产浏览器配置。固定 Batfish revision `7d0deeeac4a09973b3876327f6aef721ee12f955`、JAR SHA-256 `0927de7c740bc72f999870e842605baad9a7cb6ea66e4b01fb9a6037bea00193`、Pybatfish `2026.9.17.3748`、Python `3.12.12`，迁移0008。详见[ADV-09验收](../../evidence/adv-09-verification.md)。仅登记当前已有 11 项分析能力；复杂嵌套字段仍需专家输入 JSON，不承诺完整 SDK 自动表单或现场转发一致性。ADV-10 的依赖已满足。
