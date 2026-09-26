# MVP-20 设备、接口与路由界面

- 状态：已完成
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

- [x] 复用表格/详情组件实现设备接口视图，关键列固定。
- [x] 实现路由筛选与 LPM 模式，明确 exact 和 longest match。
- [x] 以 job/result ID 绑定结果，呈现 NextHop 多种类型。
- [x] 运行下述验证，记录实际命令与结果，更新本文及索引状态。

## 测试与验收

- routing.test.tsx：过滤/分页/快照切换不会混合结果。
- LPM 与普通 prefix 查询发送不同且正确的参数。
- 空结果、超限和部分解析提示清晰。

前端组件测试在 `web/frontend` 下使用 `pnpm exec vitest run` 指定上述 `.test.tsx` 文件；页面交互同时按前端规范人工检查。

验收成功同时要求：契约与文档一致、失败行为可解释、无跨层/跨模块越界、没有把 mock 验证宣称为真实 SDK 验证。共享约束中的身份、版本、模型覆盖和结果截断规则均适用。

## 非目标与实施边界

- 不做交互拓扑、协议专页或所有路由属性默认铺满屏幕。

## 完成记录

2026-09-25 完成设备、接口、普通路由前缀和LPM四类表单，分别使用已登记专用API。设备/接口/VRF可从当前快照的后台nodes任务加载真实候选并分页，或输入完整字面名称；专家表达式显式切换。高级参数保留并显示生效数量；属性目录、白名单及默认值由OpenAPI生成并参与契约检查。CIDR须主机位为零，LPM只接受IPv4地址，不混用请求字段。

提交冻结参数、来源和稳定幂等键，同步防双击；不确定响应保留同一请求标识。草稿离开/切换上下文先提示，取消保留，提交成功才绕过阻止器进入固定job。任务完成提供固定result链接，刷新可恢复。结果首层显示快照来源、解析问题/模型限制/截断；分页、文本筛选、关键列/全部列与原始行详情按需加载。NextHop IP/接口/丢弃/VRF分别呈现；未知结构保留JSON，LPM只展示SDK提供的匹配计数，不编造下一跳。

实际文件：frontend/features/inventory、routing、results及useDraftGuard、ResultSummary、路由/任务入口和OpenAPI生成脚本。独立审查要求真实候选及按列类型筛选，均已修正并复核。筛选仅支持String/Ip/Prefix，结构化设备/接口和数值条件使用查询表单，避免无依据空结果。累计浏览器暴露MVP-18只搜索首屏网络的问题，ContextPicker现可在无匹配时逐页加载，仍提供手动加载；测试等待实际候选后选择，不依赖响应恰好先于回车。

实际检查：仓库根 `lab.py smoke/verify` 冒烟 **12 passed**，累计后端 **260 passed、0 skipped**；前端 `pnpm test` **28 passed、0 skipped**，OpenAPI/types/属性目录、类型、构建、格式、Ruff及锁检查通过。`pnpm test:e2e` **8 passed、0 skipped**，两套配置真实四类分析、候选选择、草稿取消保留、刷新来源、Cisco分页、文本空筛选、原始行和LPM计数，保留01～19所需流程。见 [验收证据](../../evidence/mvp-20-verification.json)。

已检查实际路由/LPM截图，来源和模型限制可见。共享UI包816kB仍有体积提示，业务路由分包；仅验证两套配置和功能，不作设备转发精度或容量背书。满足MVP-21依赖。

### 2026-09-26 累计复验

已完成全25篇复核及实际环境累计验收。修正分析/路径表单429队列拒绝后的恢复行为，未知提交仍保留原幂等键。后端289、前端47、双主题浏览器各14、生产部署各3及双用户各1通过。详见[本轮证据](../../evidence/mvp-recheck-2026-09-26.md)。
