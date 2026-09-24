# MVP-20 设备、接口与路由界面

- 状态：待开发
- 阶段：1
- 依赖：[MVP-13](../mvp/mvp-13-inventory.md)、[MVP-14](../mvp/mvp-14-routing.md)、[MVP-19](../mvp/mvp-19-frontend-jobs-diagnostics.md)
- 预计工作量：2.0 人天（实现/验证 1.25 + 测试 0.5 + 文档/自检 0.25），依赖就绪后计；超过 2 人天先拆分。
- 共享约束：[架构](../../architecture.md)、[API 契约](../../api-contracts.md)、[前端规范](../../frontend.md)、[运行设计](../../operations.md)、[验收](../../validation.md)。

## 需求与目标

用户通过简洁表格和高级筛选查询设备、接口及路由。

- 设备/接口列表与详情、路由查询、最长前缀匹配、分页和原始行详情。

## 设计与接口

- 提交 nodes/interfaces/routes/lpm-routes 专用 API，结果统一通过 results 接口读取。
- 基础设备选择与专家 specifier 输入显式切换，保留所有生效条件。

沿用 api → service → controller；所有跨业务模块调用经过 service。非 SDK 存储由本模块 repository 负责。浏览器不接触 SDK 会话或连接参数。

## 预期改动位置

以下是实现时的目标路径，本次文档编写不创建代码文件：

- `web/frontend/src/features/inventory/`
- `web/frontend/src/features/routing/`
- `web/frontend/src/features/routing/routing.test.tsx`

## 实施步骤

- [ ] 复用表格/详情组件实现设备接口视图，关键列固定。
- [ ] 实现路由筛选与 LPM 模式，明确 exact 和 longest match。
- [ ] 以 job/result ID 绑定结果，呈现 NextHop 多种类型。
- [ ] 运行下述验证，记录实际命令与结果，更新本文及索引状态。

## 测试与验收

- routing.test.tsx：过滤/分页/快照切换不会混合结果。
- LPM 与普通 prefix 查询发送不同且正确的参数。
- 空结果、超限和部分解析提示清晰。

前端组件测试在 `web/frontend` 下使用 `pnpm exec vitest run` 指定上述 `.test.tsx` 文件；页面交互同时按前端规范人工检查。

验收成功同时要求：契约与文档一致、失败行为可解释、无跨层/跨模块越界、没有把 mock 验证宣称为真实 SDK 验证。共享约束中的身份、版本、模型覆盖和结果截断规则均适用。

## 非目标与实施边界

- 不做交互拓扑、协议专页或所有路由属性默认铺满屏幕。

## 完成记录

当前尚未开发或运行本 spec 的产品测试。实施者完成后在本节记录实际文件、验证命令、结果、引擎/SDK版本（如涉及）和剩余限制；存在验收失败时保持未通过状态。
