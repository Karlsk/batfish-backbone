# MVP-22 结果导出与下载入口

- 状态：待开发
- 阶段：1
- 依赖：[MVP-21](../mvp/mvp-21-frontend-traceroute.md)
- 预计工作量：1.0 人天（实现/验证 0.5 + 测试 0.25 + 文档/自检 0.25），依赖就绪后计；超过 2 人天先拆分。
- 共享约束：[架构](../../architecture.md)、[API 契约](../../api-contracts.md)、[前端规范](../../frontend.md)、[运行设计](../../operations.md)、[验收](../../validation.md)。

## 需求与目标

团队成员可带来源信息导出已有分析结果。

- JSON 导出所有结果类型、CSV 导出表格、页面统一下载入口。

## 设计与接口

- GET /results/{id}/export?format=json|csv；只导出已保存结果，不重新运行 SDK。
- 带结果版本、快照、有效参数及截断说明；CSV 使用 companion metadata 字段/头说明清楚记录来源。
- CSV 单元格以 =、+、-、@ 等公式前缀开头时安全转义，原始 JSON 不变。

沿用 api → service → controller；所有跨业务模块调用经过 service。非 SDK 存储由本模块 repository 负责。浏览器不接触 SDK 会话或连接参数。

## 预期改动位置

以下是实现时的目标路径，本次文档编写不创建代码文件：

- `web/backend/app/modules/results/export.py`
- `web/backend/app/modules/results/api.py`
- `web/frontend/src/components/ResultExport.tsx`
- `web/backend/tests/test_exports.py`

## 实施步骤

- [ ] 实现流式 JSON/CSV 响应与安全文件名，不读客户端指定路径。
- [ ] 绑定结果访问权限和来源元数据，不导出完整服务器日志。
- [ ] 在公共结果组件添加下载入口和格式支持说明。
- [ ] 运行下述验证，记录实际命令与结果，更新本文及索引状态。

## 测试与验收

- test_export_preserves_context：导出与页面 result ID、来源、参数一致。
- test_csv_formula_and_unicode：公式前缀安全，中文和换行正确。
- test_trace_csv_rejected：复杂路径不伪装为无损 CSV。

后端测试在 `web/backend` 下使用 `uv run pytest` 指定上述测试文件；集成测试连接版本固定的隔离 Batfish 测试网络，不操作团队生产网络。

验收成功同时要求：契约与文档一致、失败行为可解释、无跨层/跨模块越界、没有把 mock 验证宣称为真实 SDK 验证。共享约束中的身份、版本、模型覆盖和结果截断规则均适用。

## 非目标与实施边界

- 不做 PDF 报告、Excel 模板或定时邮件发送。

## 完成记录

当前尚未开发或运行本 spec 的产品测试。实施者完成后在本节记录实际文件、验证命令、结果、引擎/SDK版本（如涉及）和剩余限制；存在验收失败时保持未通过状态。
