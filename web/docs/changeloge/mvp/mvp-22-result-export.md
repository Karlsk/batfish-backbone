# MVP-22 结果导出与下载入口

- 状态：已完成
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

- [x] 实现流式 JSON/CSV 响应与安全文件名，不读客户端指定路径。
- [x] 绑定结果访问权限和来源元数据，不导出完整服务器日志。
- [x] 在公共结果组件添加下载入口和格式支持说明。
- [x] 运行下述验证，记录实际命令与结果，更新本文及索引状态。

## 测试与验收

- test_export_preserves_context：导出与页面 result ID、来源、参数一致。
- test_csv_formula_and_unicode：公式前缀安全，中文和换行正确。
- test_trace_csv_rejected：复杂路径不伪装为无损 CSV。

后端测试在 `web/backend` 下使用 `uv run pytest` 指定上述测试文件；集成测试连接版本固定的隔离 Batfish 测试网络，不操作团队生产网络。

验收成功同时要求：契约与文档一致、失败行为可解释、无跨层/跨模块越界、没有把 mock 验证宣称为真实 SDK 验证。共享约束中的身份、版本、模型覆盖和结果截断规则均适用。

## 非目标与实施边界

- 不做 PDF 报告、Excel 模板或定时邮件发送。

## 完成记录

2026-09-26 完成带认证的保存结果下载接口与统一ResultExport入口。JSON包含完整ResultEnvelope metadata和保存data（columns/rows/flows），CSV仅表格、首条metadata记录携带完整来源；默认JSON，路径CSV返回409，未知格式422。UUID安全文件名、no-store/nosniff，无客户端文件路径、日志或SDK重算。下载全部已保存数据，不受页面筛选或分页影响。

CSV使用UTF8 BOM和标准引号，中文/换行/结构化JSON完整保留；公式前缀包括前导空白/控制字符以单引号转义，JSON原值保持不变。JSON/CSV迭代编码后合并64KiB块，避免逐token线程切换；前导字符线性扫描。服务端沿用默认100MiB保存上限，解析文件内存有界但并非常量内存；浏览器完整Blob后保存。

实际文件：results/export.py、api/service.py、tests/test_exports.py、ResultExport.tsx及测试、生成OpenAPI类型、双拓扑浏览器下载helper。分层规则显式允许service调用本模块纯export编码，仍禁止API直接调用编码和编码依赖service/SDK，增加反向断言。独立只读审查提出流分片与前缀扫描性能问题，已修复并复核无阻塞。

累计验收：仓库根lab.py smoke/verify为12项冒烟、275项后端全部通过；前端33项单测、10项真实Chromium流程全部通过，均0skip。两套配置分别下载真实表格JSON/CSV与路径JSON，比对固定result/快照/参数、确认过滤空表仍导出保存数据。OpenAPI、类型、构建、格式、Ruff、锁、链接检查通过。见 [验收证据](../../evidence/mvp-22-verification.json)。共享UI816.53kB体积提示保留；无容量或设备精度背书。满足MVP-23依赖。
